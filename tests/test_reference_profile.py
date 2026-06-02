"""Tests for reference_profile module."""

import json
import os
import tempfile

import pytest

from horizon6_autogear.core.reference_profile import (
    ReferencePoint,
    ReferenceProfile,
    _fdp_to_reference_point,
    _select_best_lap,
    _split_laps,
)


class MockFDP:
    """Minimal mock of ForzaDataPacket for unit testing."""

    def __init__(self, **kwargs):
        self.is_race_on = kwargs.get('is_race_on', 1)
        self.dist_traveled = kwargs.get('dist_traveled', 100.0)
        self.lap_no = kwargs.get('lap_no', 1)
        self.position_x = kwargs.get('position_x', 1.0)
        self.position_y = kwargs.get('position_y', 2.0)
        self.position_z = kwargs.get('position_z', 3.0)
        self.speed = kwargs.get('speed', 50.0)
        self.current_engine_rpm = kwargs.get('current_engine_rpm', 5000.0)
        self.gear = kwargs.get('gear', 3)
        self.steer = kwargs.get('steer', 128)
        self.accel = kwargs.get('accel', 255)
        self.brake = kwargs.get('brake', 0)
        self.yaw = kwargs.get('yaw', 0.5)
        self.cur_lap_time = kwargs.get('cur_lap_time', 10.0)
        self.car_ordinal = kwargs.get('car_ordinal', 100)
        self.car_class = kwargs.get('car_class', 2)
        self.car_performance_index = kwargs.get('car_performance_index', 500)
        self.drivetrain_type = kwargs.get('drivetrain_type', 1)
        self.tire_combined_slip_FL = kwargs.get('tire_combined_slip_FL', 0.1)
        self.tire_combined_slip_FR = kwargs.get('tire_combined_slip_FR', 0.2)
        self.tire_combined_slip_RL = kwargs.get('tire_combined_slip_RL', 0.3)
        self.tire_combined_slip_RR = kwargs.get('tire_combined_slip_RR', 0.4)


class TestFdpToReferencePoint:
    """Test _fdp_to_reference_point normalization."""

    def test_steer_normalization_center(self):
        """Steer 0 (center) should be 0.0."""
        fdp = MockFDP(steer=0)
        rp = _fdp_to_reference_point(fdp)
        assert rp.steer == pytest.approx(0.0)

    def test_steer_normalization_full_right(self):
        """Steer 127 (max right) should be 127/128 = 0.9921875."""
        fdp = MockFDP(steer=127)
        rp = _fdp_to_reference_point(fdp)
        assert rp.steer == pytest.approx(127 / 128.0)

    def test_steer_normalization_full_left(self):
        """Steer -127 (max left) should be -127/128 = -0.9921875."""
        fdp = MockFDP(steer=-127)
        rp = _fdp_to_reference_point(fdp)
        assert rp.steer == pytest.approx(-127 / 128.0)

    def test_throttle_normalization(self):
        """Accel 255 -> throttle 1.0, accel 0 -> throttle 0.0."""
        fdp_full = MockFDP(accel=255)
        fdp_off = MockFDP(accel=0)
        assert _fdp_to_reference_point(fdp_full).throttle == pytest.approx(1.0)
        assert _fdp_to_reference_point(fdp_off).throttle == pytest.approx(0.0)

    def test_throttle_normalization_half(self):
        """Accel 128 -> throttle ~0.502."""
        fdp = MockFDP(accel=128)
        rp = _fdp_to_reference_point(fdp)
        assert rp.throttle == pytest.approx(128 / 255.0)

    def test_brake_normalization(self):
        """Brake 255 -> brake 1.0, brake 0 -> brake 0.0."""
        fdp_full = MockFDP(brake=255)
        fdp_off = MockFDP(brake=0)
        assert _fdp_to_reference_point(fdp_full).brake == pytest.approx(1.0)
        assert _fdp_to_reference_point(fdp_off).brake == pytest.approx(0.0)

    def test_avg_slip_calculation(self):
        """avg_slip = mean of 4 tire slip values."""
        fdp = MockFDP(
            tire_combined_slip_FL=0.1,
            tire_combined_slip_FR=0.2,
            tire_combined_slip_RL=0.3,
            tire_combined_slip_RR=0.4,
        )
        rp = _fdp_to_reference_point(fdp)
        assert rp.avg_slip == pytest.approx(0.25)

    def test_all_fields_populated(self):
        """Verify all ReferencePoint fields are populated from FDP."""
        fdp = MockFDP(
            dist_traveled=500.0,
            lap_no=3,
            position_x=10.0,
            position_y=20.0,
            position_z=30.0,
            speed=60.0,
            current_engine_rpm=7000.0,
            gear=4,
            steer=64,
            accel=200,
            brake=100,
            yaw=1.5,
            cur_lap_time=45.0,
        )
        rp = _fdp_to_reference_point(fdp)
        assert rp.dist == 500.0
        assert rp.lap_no == 3
        assert rp.pos_x == 10.0
        assert rp.pos_y == 20.0
        assert rp.pos_z == 30.0
        assert rp.speed == 60.0
        assert rp.rpm == 7000.0
        assert rp.gear == 4
        assert rp.steer == pytest.approx(64 / 128.0)
        assert rp.throttle == pytest.approx(200 / 255.0)
        assert rp.brake == pytest.approx(100 / 255.0)
        assert rp.yaw == 1.5
        assert rp.timestamp == 45.0


class TestSplitLaps:
    """Test _split_laps with synthetic lap_no sequences."""

    def test_single_lap(self):
        """All packets in same lap -> one lap returned."""
        fdps = [MockFDP(lap_no=1) for _ in range(5)]
        laps = _split_laps(fdps)
        assert len(laps) == 1
        assert len(laps[0]) == 5

    def test_two_laps(self):
        """lap_no goes 0->1->2 -> two full laps plus partial."""
        fdps = [MockFDP(lap_no=0)] * 3 + [MockFDP(lap_no=1)] * 5 + [MockFDP(lap_no=2)] * 4
        laps = _split_laps(fdps)
        # First boundary 0->1 appends lap_no=0 segment
        # Second boundary 1->2 appends lap_no=1 segment
        # Last lap appended at end
        assert len(laps) == 3
        assert len(laps[0]) == 3
        assert len(laps[1]) == 5
        assert len(laps[2]) == 4

    def test_lap_no_decrease(self):
        """Lap number decreasing (e.g., race restart) discards old segment."""
        fdps = [MockFDP(lap_no=3)] * 3 + [MockFDP(lap_no=1)] * 4
        laps = _split_laps(fdps)
        # 3->1 is not an increase, so lap_no=3 segment is NOT appended at boundary
        # The current_lap resets to lap_no=1, old segment is discarded
        # At end, only the lap_no=1 segment is appended
        assert len(laps) == 1
        assert len(laps[0]) == 4


class TestSelectBestLap:
    """Test _select_best_lap selection logic."""

    def test_single_lap_returns_it(self):
        """With one lap, return it directly."""
        lap = [MockFDP() for _ in range(20)]
        result = _select_best_lap([lap])
        assert result is lap

    def test_picks_lower_slip(self):
        """Between two equal-time laps, pick the one with lower avg slip."""
        clean_lap = [MockFDP(
            cur_lap_time=i * 0.1,
            tire_combined_slip_FL=0.1,
            tire_combined_slip_FR=0.1,
            tire_combined_slip_RL=0.1,
            tire_combined_slip_RR=0.1,
        ) for i in range(20)]
        messy_lap = [MockFDP(
            cur_lap_time=i * 0.1,
            tire_combined_slip_FL=1.0,
            tire_combined_slip_FR=1.0,
            tire_combined_slip_RL=1.0,
            tire_combined_slip_RR=1.0,
        ) for i in range(20)]
        result = _select_best_lap([clean_lap, messy_lap])
        assert result is clean_lap

    def test_picks_faster_lap(self):
        """Between two equal-slip laps, pick the shorter one."""
        fast_lap = [MockFDP(
            cur_lap_time=i * 0.5,
            tire_combined_slip_FL=0.5,
            tire_combined_slip_FR=0.5,
            tire_combined_slip_RL=0.5,
            tire_combined_slip_RR=0.5,
        ) for i in range(20)]
        slow_lap = [MockFDP(
            cur_lap_time=i * 1.0,
            tire_combined_slip_FL=0.5,
            tire_combined_slip_FR=0.5,
            tire_combined_slip_RL=0.5,
            tire_combined_slip_RR=0.5,
        ) for i in range(20)]
        result = _select_best_lap([fast_lap, slow_lap])
        assert result is fast_lap

    def test_skips_short_laps(self):
        """Laps with fewer than 10 packets are skipped."""
        short_lap = [MockFDP(cur_lap_time=i) for i in range(5)]
        good_lap = [MockFDP(
            cur_lap_time=i * 0.1,
            tire_combined_slip_FL=0.1,
            tire_combined_slip_FR=0.1,
            tire_combined_slip_RL=0.1,
            tire_combined_slip_RR=0.1,
        ) for i in range(20)]
        result = _select_best_lap([short_lap, good_lap])
        assert result is good_lap


class TestSaveLoadRoundTrip:
    """Test ReferenceProfile save and load round-trip."""

    def test_round_trip(self):
        """Save then load should preserve all frame data."""
        frames = [
            ReferencePoint(
                dist=100.0, lap_no=1,
                pos_x=1.0, pos_y=2.0, pos_z=3.0,
                speed=50.0, rpm=5000, gear=3,
                steer=0.0, throttle=1.0, brake=0.0,
                yaw=0.5, avg_slip=0.25, timestamp=10.0,
            ),
            ReferencePoint(
                dist=200.0, lap_no=1,
                pos_x=4.0, pos_y=5.0, pos_z=6.0,
                speed=60.0, rpm=6000, gear=4,
                steer=-0.5, throttle=0.8, brake=0.2,
                yaw=-0.3, avg_slip=0.15, timestamp=20.0,
            ),
        ]
        meta = {'car_ordinal': 100, 'lap_time': 10.0, 'frame_count': 2}
        profile = ReferenceProfile(metadata=meta, frames=frames, segments={'brake_zones': [1]})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'test_profile.json')
            profile.save(path)
            loaded = ReferenceProfile.load(path)

        assert loaded.metadata == meta
        assert len(loaded.frames) == 2
        assert loaded.segments == {'brake_zones': [1]}
        f0 = loaded.frames[0]
        assert f0.dist == pytest.approx(100.0)
        assert f0.speed == pytest.approx(50.0)
        assert f0.steer == pytest.approx(0.0)
        assert f0.throttle == pytest.approx(1.0)
        assert f0.gear == 3
        f1 = loaded.frames[1]
        assert f1.steer == pytest.approx(-0.5)
        assert f1.brake == pytest.approx(0.2)

    def test_save_creates_directory(self):
        """save() should create parent directories if missing."""
        frames = [ReferencePoint(
            dist=0, lap_no=0, pos_x=0, pos_y=0, pos_z=0,
            speed=0, rpm=0, gear=0, steer=0, throttle=0, brake=0,
            yaw=0, avg_slip=0, timestamp=0,
        )]
        profile = ReferenceProfile(metadata={}, frames=frames)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'sub', 'dir', 'profile.json')
            profile.save(path)
            assert os.path.exists(path)


class TestFromRecording:
    """Test ReferenceProfile.from_recording with real recording file."""

    RECORDING_PATH = os.path.join(
        os.path.dirname(__file__), '..', 'data2', 'recordings', '20260517_235830.f6rec.json'
    )

    @pytest.fixture
    def recording_path(self):
        """Skip test if recording file is not available."""
        path = os.path.abspath(self.RECORDING_PATH)
        pytest.importorskip('horizon6_autogear')
        if not os.path.exists(path):
            pytest.skip(f'Recording not found: {path}')
        return path

    def test_from_recording_extracts_frames(self, recording_path):
        """from_recording should produce frames with correct types."""
        profile = ReferenceProfile.from_recording(recording_path)
        assert len(profile.frames) > 0
        assert all(isinstance(f, ReferencePoint) for f in profile.frames)

    def test_from_recording_metadata_keys(self, recording_path):
        """from_recording metadata should contain all expected keys."""
        profile = ReferenceProfile.from_recording(recording_path)
        expected_keys = {
            'car_ordinal', 'car_class', 'car_performance_index',
            'drivetrain_type', 'lap_time', 'total_distance',
            'frame_count', 'sample_rate', 'source',
        }
        assert expected_keys.issubset(set(profile.metadata.keys()))

    def test_from_recording_car_ordinal(self, recording_path):
        """Car ordinal should match the recording."""
        profile = ReferenceProfile.from_recording(recording_path)
        assert profile.metadata['car_ordinal'] == 4341

    def test_from_recording_frame_values(self, recording_path):
        """Frame values should be within expected ranges."""
        profile = ReferenceProfile.from_recording(recording_path)
        for f in profile.frames:
            assert -1.0 <= f.steer <= 1.0, f'steer {f.steer} out of range'
            assert 0.0 <= f.throttle <= 1.0, f'throttle {f.throttle} out of range'
            assert 0.0 <= f.brake <= 1.0, f'brake {f.brake} out of range'
            assert f.speed >= 0, f'speed {f.speed} negative'
            assert f.rpm >= 0, f'rpm {f.rpm} negative'

    def test_from_recording_frame_count_matches(self, recording_path):
        """frame_count metadata should match actual frame count."""
        profile = ReferenceProfile.from_recording(recording_path)
        assert profile.metadata['frame_count'] == len(profile.frames)

    def test_from_recording_round_trip(self, recording_path):
        """Profile from recording should survive save/load round-trip."""
        profile = ReferenceProfile.from_recording(recording_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'roundtrip.json')
            profile.save(path)
            loaded = ReferenceProfile.load(path)

        assert len(loaded.frames) == len(profile.frames)
        for orig, load in zip(profile.frames, loaded.frames):
            assert orig.dist == pytest.approx(load.dist, abs=0.01)
            assert orig.speed == pytest.approx(load.speed, abs=0.001)
            assert orig.gear == load.gear


class TestPartialRecording:
    """Test handling of recordings with no lap boundary."""

    def test_no_lap_boundary_uses_all_data(self):
        """If all packets have same lap_no, use all as single lap."""
        fdps = [MockFDP(lap_no=1, is_race_on=1, cur_lap_time=i * 0.1) for i in range(15)]
        # _split_laps will return a single lap
        laps = _split_laps(fdps)
        assert len(laps) == 1
        assert len(laps[0]) == 15

    def test_empty_recording_raises(self):
        """from_recording with no valid packets should raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'empty.json')
            with open(path, 'w') as f:
                json.dump({'metadata': {}, 'packets': []}, f)
            with pytest.raises(ValueError, match='No valid packets'):
                ReferenceProfile.from_recording(path)


def _make_frames(brakes, gears, dist_start=0.0, dist_step=10.0):
    """Helper to create synthetic ReferencePoint frames.

    brakes: list of brake values (0.0-1.0)
    gears: list of gear ints
    Both lists must be same length.
    """
    assert len(brakes) == len(gears)
    return [
        ReferencePoint(
            dist=dist_start + i * dist_step, lap_no=1,
            pos_x=0.0, pos_y=0.0, pos_z=0.0,
            speed=50.0, rpm=5000.0, gear=gears[i],
            steer=0.0, throttle=1.0 - brakes[i], brake=brakes[i],
            yaw=0.0, avg_slip=0.1, timestamp=i * 0.016,
        )
        for i in range(len(brakes))
    ]


class TestExtractBrakeZones:
    """Test extract_brake_zones method."""

    def test_single_brake_zone_heavy(self):
        """Contiguous heavy braking frames produce one heavy zone."""
        brakes = [0.0, 0.0, 0.8, 0.9, 0.85, 0.0, 0.0]
        gears = [3] * 7
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        zones = profile.extract_brake_zones()

        assert len(zones) == 1
        z = zones[0]
        assert z['start_dist'] == pytest.approx(20.0)
        assert z['end_dist'] == pytest.approx(40.0)
        assert z['max_brake'] == pytest.approx(0.9)
        assert z['severity'] == 'heavy'

    def test_multiple_brake_zones(self):
        """Two separate braking zones produce two entries."""
        brakes = [0.0, 0.5, 0.0, 0.3, 0.6, 0.0]
        gears = [3] * 6
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        zones = profile.extract_brake_zones()

        assert len(zones) == 2
        assert zones[0]['severity'] == 'medium'
        assert zones[0]['start_dist'] == pytest.approx(10.0)
        assert zones[0]['end_dist'] == pytest.approx(10.0)
        assert zones[0]['max_brake'] == pytest.approx(0.5)
        assert zones[1]['severity'] == 'medium'
        assert zones[1]['max_brake'] == pytest.approx(0.6)

    def test_light_brake_zone(self):
        """Braking below 0.4 produces light severity."""
        brakes = [0.0, 0.2, 0.15, 0.0]
        gears = [3] * 4
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        zones = profile.extract_brake_zones()

        assert len(zones) == 1
        assert zones[0]['severity'] == 'light'
        assert zones[0]['max_brake'] == pytest.approx(0.2)

    def test_no_brake_zones_below_threshold(self):
        """All brakes below threshold produces empty list."""
        brakes = [0.0, 0.05, 0.09, 0.0]
        gears = [3] * 4
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        zones = profile.extract_brake_zones(threshold=0.1)

        assert zones == []

    def test_brake_zone_to_end_of_frames(self):
        """Brake zone extending to last frame is still captured."""
        brakes = [0.0, 0.5, 0.6]
        gears = [3] * 3
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        zones = profile.extract_brake_zones()

        assert len(zones) == 1
        assert zones[0]['end_dist'] == pytest.approx(20.0)

    def test_stores_in_segments(self):
        """Results are stored in self.segments['brake_zones']."""
        brakes = [0.0, 0.5, 0.0]
        gears = [3] * 3
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        zones = profile.extract_brake_zones()

        assert profile.segments['brake_zones'] == zones


class TestExtractShiftPoints:
    """Test extract_shift_points method."""

    def test_upshift_and_downshift(self):
        """Gear changes produce correct shift entries with types."""
        brakes = [0.0] * 6
        gears = [2, 2, 3, 3, 2, 2]
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        points = profile.extract_shift_points()

        assert len(points) == 2
        assert points[0]['from_gear'] == 2
        assert points[0]['to_gear'] == 3
        assert points[0]['type'] == 'up'
        assert points[0]['dist'] == pytest.approx(20.0)
        assert points[1]['from_gear'] == 3
        assert points[1]['to_gear'] == 2
        assert points[1]['type'] == 'down'
        assert points[1]['dist'] == pytest.approx(40.0)

    def test_multiple_upshifts(self):
        """Sequential upshifts each produce a shift point."""
        brakes = [0.0] * 5
        gears = [1, 2, 3, 4, 5]
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        points = profile.extract_shift_points()

        assert len(points) == 4
        assert all(p['type'] == 'up' for p in points)

    def test_no_shift_points_constant_gear(self):
        """No gear changes produces empty list."""
        brakes = [0.0] * 5
        gears = [3] * 5
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        points = profile.extract_shift_points()

        assert points == []

    def test_stores_in_segments(self):
        """Results are stored in self.segments['shift_points']."""
        brakes = [0.0] * 3
        gears = [2, 3, 3]
        frames = _make_frames(brakes, gears)
        profile = ReferenceProfile(metadata={}, frames=frames)
        points = profile.extract_shift_points()

        assert profile.segments['shift_points'] == points


class TestFromRecordingSegments:
    """Test that from_recording populates segments."""

    RECORDING_PATH = os.path.join(
        os.path.dirname(__file__), '..', 'data2', 'recordings', '20260517_235830.f6rec.json'
    )

    @pytest.fixture
    def recording_path(self):
        """Skip test if recording file is not available."""
        path = os.path.abspath(self.RECORDING_PATH)
        if not os.path.exists(path):
            pytest.skip(f'Recording not found: {path}')
        return path

    def test_brake_zones_populated(self, recording_path):
        """from_recording should produce non-empty brake_zones."""
        profile = ReferenceProfile.from_recording(recording_path)
        assert 'brake_zones' in profile.segments
        assert len(profile.segments['brake_zones']) > 0
        for z in profile.segments['brake_zones']:
            assert 'start_dist' in z
            assert 'end_dist' in z
            assert 'max_brake' in z
            assert 'severity' in z
            assert z['severity'] in ('light', 'medium', 'heavy')

    def test_shift_points_populated(self, recording_path):
        """from_recording should produce non-empty shift_points."""
        profile = ReferenceProfile.from_recording(recording_path)
        assert 'shift_points' in profile.segments
        assert len(profile.segments['shift_points']) > 0
        for p in profile.segments['shift_points']:
            assert 'dist' in p
            assert 'from_gear' in p
            assert 'to_gear' in p
            assert 'type' in p
            assert p['type'] in ('up', 'down')
