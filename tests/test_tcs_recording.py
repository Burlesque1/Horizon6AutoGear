"""Recording-based TCS test: feeds real telemetry through TractionController + Arbiter + SimulatedOutput."""

import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.core.playback import PlaybackSource
from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
from horizon6_autogear.control.traction_controller import TractionController
from horizon6_autogear.control.arbiter import Arbiter
from horizon6_autogear.shifting.simulated_output import SimulatedOutput
from horizon6_autogear.shifting.output_device import SharedState

RECORDING_PATH = 'data2/recordings/20260517_235830.f6rec.json'
PACKET_FORMAT = 'fh6'


def _feed_recording(path):
    """Load recording and feed through TCS + Arbiter + SimulatedOutput, return results."""
    source = PlaybackSource(path)
    tcs = TractionController()
    arbiter = Arbiter()
    output = SimulatedOutput()
    shared_state = SharedState()

    tcs_interventions = 0
    tcs_pass_through = 0
    throttle_reductions = []
    total_moving = 0

    for pkt in source.packets:
        raw = bytes.fromhex(pkt['hex'])
        fdp = ForzaDataPacket(raw, packet_format=PACKET_FORMAT)

        if fdp.speed < 5.0:
            continue
        total_moving += 1

        tcs_throttle = tcs.compute(fdp)
        driver_throttle = fdp.accel / 255.0

        commanded = arbiter.resolve(
            driver_throttle=driver_throttle,
            tcs_throttle=tcs_throttle,
            corner_throttle=1.0,
            corner_brake=0.0,
            shift_pending=shared_state.shift_pending.is_set(),
        )
        output.set_analog('throttle', commanded.throttle)

        if tcs_throttle < 1.0:
            tcs_interventions += 1
            throttle_reductions.append(commanded.throttle)
        else:
            tcs_pass_through += 1

    return {
        'total_moving': total_moving,
        'tcs_interventions': tcs_interventions,
        'tcs_pass_through': tcs_pass_through,
        'throttle_reductions': throttle_reductions,
        'output': output,
    }


def test_tcs_intervenes_on_real_slip():
    """TCS must detect real wheelspin and reduce throttle."""
    results = _feed_recording(RECORDING_PATH)
    assert results['tcs_interventions'] > 0, \
        f"Expected TCS interventions but got 0 (out of {results['total_moving']} frames)"


def test_tcs_throttle_reduction_is_below_driver_input():
    """All TCS-reduced throttle values must be below full driver throttle."""
    results = _feed_recording(RECORDING_PATH)
    for throttle in results['throttle_reductions']:
        assert throttle <= 0.3, \
            f"TCS-reduced throttle {throttle} exceeds reduction target 0.3"


def test_tcs_does_not_intervene_on_grip():
    """Most frames should NOT trigger TCS (car has grip most of the time)."""
    results = _feed_recording(RECORDING_PATH)
    ratio = results['tcs_interventions'] / results['total_moving']
    assert ratio < 0.5, \
        f"TCS intervening on {ratio:.1%} of frames — threshold may be too low"


def test_tcs_output_never_exceeds_reduction():
    """When TCS intervenes, output throttle must be <= throttle_reduction (0.3)."""
    source = PlaybackSource(RECORDING_PATH)
    tcs = TractionController()
    arbiter = Arbiter()
    output = SimulatedOutput()
    shared_state = SharedState()

    for pkt in source.packets:
        fdp = ForzaDataPacket(bytes.fromhex(pkt['hex']), packet_format=PACKET_FORMAT)
        if fdp.speed < 5.0:
            continue

        tcs_throttle = tcs.compute(fdp)
        driver_throttle = fdp.accel / 255.0

        commanded = arbiter.resolve(
            driver_throttle=driver_throttle,
            tcs_throttle=tcs_throttle,
            corner_throttle=1.0,
            corner_brake=0.0,
            shift_pending=shared_state.shift_pending.is_set(),
        )

        if tcs_throttle < 1.0:
            assert commanded.throttle <= tcs.throttle_reduction, \
                f"TCS intervened but output throttle {commanded.throttle} > reduction {tcs.throttle_reduction}"

        output.set_analog('throttle', commanded.throttle)


def test_drivetrain_aware_monitoring():
    """Recording is mostly RWD (drivetrain_type=1) — TCS must monitor rear wheels."""
    source = PlaybackSource(RECORDING_PATH)
    tcs = TractionController()

    rwd_frames = 0
    rwd_interventions = 0
    for pkt in source.packets:
        fdp = ForzaDataPacket(bytes.fromhex(pkt['hex']), packet_format=PACKET_FORMAT)
        if fdp.drivetrain_type == 1 and fdp.speed > 5.0:
            rwd_frames += 1
            if tcs.compute(fdp) < 1.0:
                rwd_interventions += 1

    assert rwd_frames > 0, "No RWD frames in recording"
    assert rwd_interventions > 0, "TCS never triggered on RWD frames despite high slip data"


def test_tcs_with_high_threshold_never_intervenes():
    """With an unreasonably high threshold, TCS should not intervene."""
    source = PlaybackSource(RECORDING_PATH)
    tcs = TractionController(slip_threshold=100.0)

    interventions = 0
    for pkt in source.packets:
        fdp = ForzaDataPacket(bytes.fromhex(pkt['hex']), packet_format=PACKET_FORMAT)
        if fdp.speed > 5.0 and tcs.compute(fdp) < 1.0:
            interventions += 1

    assert interventions == 0, f"TCS intervened {interventions} times with threshold=100"
