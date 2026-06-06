"""Integration test for semi-auto mode using real recording data.

Uses actual .f6rec.json recordings to verify the full pipeline:
  Recording -> ReferenceProfile -> ProfileMatcher -> SemiAutoController -> SimulatedOutput
"""

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest

import horizon6_autogear.config.config as constants
from horizon6_autogear.core.forza import Forza
from horizon6_autogear.core.reference_profile import ReferenceProfile
from horizon6_autogear.core.playback import PlaybackSource
from horizon6_autogear.shifting.simulated_output import SimulatedOutput
from horizon6_autogear.shifting.keyboard import KeyboardOutput
from horizon6_autogear.control.pid_controller import PIDController
from horizon6_autogear.control.semi_auto_controller import SemiAutoController
from horizon6_autogear.control.latency_metrics import LatencyCollector

RECORDING_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data2', 'recordings')


def _find_recordings():
    if not os.path.isdir(RECORDING_DIR):
        return []
    return sorted([
        os.path.join(RECORDING_DIR, f)
        for f in os.listdir(RECORDING_DIR)
        if f.endswith('.f6rec.json') or f.endswith('.f6rec.json.gz')
    ])


def pytest_generate_tests(metafunc):
    if 'recording_path' in metafunc.fixturenames:
        recs = _find_recordings()
        if recs:
            metafunc.parametrize('recording_path', recs,
                                 ids=[os.path.basename(r) for r in recs])
        else:
            metafunc.parametrize('recording_path', [], ids=['no-recordings'])


class TestRealRecordingProfileExtraction:

    def test_profile_has_frames(self, recording_path):
        profile = ReferenceProfile.from_recording(recording_path)
        assert len(profile.frames) > 100

    def test_brake_zones_have_entry_speed(self, recording_path):
        profile = ReferenceProfile.from_recording(recording_path)
        for bz in profile.segments.get('brake_zones', []):
            assert 'entry_speed' in bz
            assert bz['entry_speed'] >= 0

    def test_brake_zones_have_frame_index(self, recording_path):
        profile = ReferenceProfile.from_recording(recording_path)
        for bz in profile.segments.get('brake_zones', []):
            assert 'start_frame_idx' in bz
            assert isinstance(bz['start_frame_idx'], int)

    def test_brake_zones_have_start_pos(self, recording_path):
        profile = ReferenceProfile.from_recording(recording_path)
        for bz in profile.segments.get('brake_zones', []):
            assert 'start_pos' in bz
            assert len(bz['start_pos']) == 3

    def test_shift_points_extracted(self, recording_path):
        profile = ReferenceProfile.from_recording(recording_path)
        sp = profile.segments.get('shift_points', [])
        assert len(sp) > 0
        for pt in sp:
            assert 'type' in pt
            assert pt['type'] in ('up', 'down')

    def test_profile_save_load_roundtrip(self, recording_path):
        profile = ReferenceProfile.from_recording(recording_path)
        fd, path = tempfile.mkstemp(suffix='.ref.json')
        os.close(fd)
        try:
            profile.save(path)
            loaded = ReferenceProfile.load(path)
            assert len(loaded.frames) == len(profile.frames)
            assert len(loaded.segments.get('brake_zones', [])) == len(
                profile.segments.get('brake_zones', []))
            for orig, ld in zip(
                profile.segments.get('brake_zones', []),
                loaded.segments.get('brake_zones', [])
            ):
                assert ld['entry_speed'] == orig['entry_speed']
                assert ld['severity'] == orig['severity']
                assert ld['start_frame_idx'] == orig['start_frame_idx']
        finally:
            os.unlink(path)


class TestRealRecordingSemiAutoPipeline:

    def setup_method(self):
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='test')
        self.forza = Forza(self.pool, packet_format='fh6')
        self.forza.ordinal = 4341
        self.forza.car_class = 4
        self.forza.car_perf = 800
        self.forza.car_drivetrain = 1
        self.forza.minGear = 1
        self.forza.maxGear = 10
        self.forza.shift_point = {3: {'speed': 100, 'rpmo': 7000}}
        self.sim = SimulatedOutput()
        self.forza.set_output_device(self.sim)

    def teardown_method(self):
        self.forza.isRunning = False
        self.pool.shutdown(wait=False)

    def test_semi_auto_brakes_on_real_recording(self, recording_path):
        profile = ReferenceProfile.from_recording(recording_path)
        brake_zones = profile.segments.get('brake_zones', [])
        if not brake_zones:
            pytest.skip('No brake zones in this recording')

        fd, ref_path = tempfile.mkstemp(suffix='.ref.json')
        os.close(fd)
        profile.save(ref_path)
        try:
            self.forza.load_reference_profile(ref_path)

            pid = PIDController(
                kp=constants.PID_BRAKE_KP,
                ki=constants.PID_BRAKE_KI,
                kd=constants.PID_BRAKE_KD,
                integral_limit=constants.PID_INTEGRAL_LIMIT,
            )
            self.forza.semi_auto_controller = SemiAutoController(pid)
            self.forza.latency_collector = LatencyCollector()
            self.forza.mode = 'semi_auto'
            self.forza._init_shift_controller()

            source = PlaybackSource(recording_path)
            brake_frames = 0
            total_frames = 0

            for raw in source.packets:
                from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
                hex_str = raw['hex'] if isinstance(raw, dict) else raw
                fdp = ForzaDataPacket(bytes.fromhex(hex_str), packet_format='fh6')
                if not fdp.is_race_on or fdp.speed < 1.0:
                    continue
                if fdp.gear < 1 or fdp.gear > 10:
                    continue

                total_frames += 1
                self.forza._compute_reference_data(fdp)

                if not self.forza.shift_point or fdp.speed <= constants.SPEED_THRESHOLD:
                    continue
                if self.forza.shift_controller is None:
                    self.forza._init_shift_controller()

                self.sim.clear()
                self.forza._dispatch_controllers(0, fdp)

                if self.sim.last_brake > 0.01:
                    brake_frames += 1

            assert total_frames > 100, f'Only {total_frames} valid frames'
            print(f'Recording: {os.path.basename(recording_path)}')
            print(f'  Total valid frames: {total_frames}')
            print(f'  Brake zones: {len(brake_zones)}')
            print(f'  Brake frames: {brake_frames}/{total_frames}')
            print(f'  Brake ratio: {brake_frames/total_frames:.1%}')

            assert brake_frames > 0, (
                'Semi-auto mode produced zero brake output across '
                f'{total_frames} frames with {len(brake_zones)} brake zones'
            )
        finally:
            os.unlink(ref_path)

    def test_coach_mode_no_auto_brake(self, recording_path):
        self.forza._init_shift_controller()

        source = PlaybackSource(recording_path)
        brake_count = 0

        for raw in source.packets[:500]:
            from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
            hex_str = raw['hex'] if isinstance(raw, dict) else raw
            fdp = ForzaDataPacket(bytes.fromhex(hex_str), packet_format='fh6')
            if not fdp.is_race_on or fdp.speed < 1.0:
                continue
            if fdp.gear < 1 or fdp.gear > 10:
                continue

            self.sim.clear()
            self.forza._dispatch_controllers(0, fdp)
            if self.sim.last_brake > 0.01:
                brake_count += 1

        assert brake_count == 0, (
            f'Coach mode should not auto-brake, got {brake_count} brake frames'
        )


class TestSemiAutoModeSwitching:

    def setup_method(self):
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='test')
        self.forza = Forza(self.pool, packet_format='fh6')
        self.forza.ordinal = 1
        self.forza.car_class = 0
        self.forza.car_perf = 100
        self.forza.car_drivetrain = 1
        self.forza.minGear = 1
        self.forza.maxGear = 6
        self.sim = SimulatedOutput()
        self.forza.set_output_device(self.sim)

    def teardown_method(self):
        self.forza.isRunning = False
        self.pool.shutdown(wait=False)

    def test_default_mode_is_coach(self):
        assert self.forza.mode == 'coach'
        assert self.forza.semi_auto_controller is None

    def test_set_mode_coach_restores_keyboard(self):
        self.forza.mode = 'semi_auto'
        self.forza.semi_auto_controller = SemiAutoController(PIDController())
        self.forza.set_mode('coach')
        assert isinstance(self.forza.output_device, KeyboardOutput)
        assert self.forza.semi_auto_controller is None

    def test_set_mode_semi_auto_without_profile_raises(self):
        with pytest.raises(ValueError, match='reference profile'):
            self.forza.set_mode('semi_auto')

    def test_set_mode_unknown_raises(self):
        with pytest.raises(ValueError, match='Unknown mode'):
            self.forza.set_mode('full_auto')

    def test_gui_set_mode_api(self):
        from horizon6_autogear.gui import Api
        api = Api()
        api.engine = self.forza

        result = api.set_mode('coach')
        assert result['mode'] == 'coach'

        result = api.set_mode('semi_auto')
        assert 'error' in result
        assert result['mode'] == 'coach'

    def test_semi_auto_mode_uses_config_pid_gains(self):
        pid = PIDController(
            kp=constants.PID_BRAKE_KP,
            ki=constants.PID_BRAKE_KI,
            kd=constants.PID_BRAKE_KD,
            integral_limit=constants.PID_INTEGRAL_LIMIT,
        )
        assert pid._kp == 0.5
        assert pid._ki == 0.05
        assert pid._kd == 0.1
