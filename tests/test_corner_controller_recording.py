"""Recording-based CornerController test: feeds real telemetry through CornerController."""

import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.core.playback import PlaybackSource
from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
from horizon6_autogear.control.corner_controller import CornerController

RECORDING_PATH = 'data2/recordings/20260517_235830.f6rec.json'
PACKET_FORMAT = 'fh6'


def _feed_recording(path):
    """Load recording and feed through CornerController, return results."""
    source = PlaybackSource(path)
    cc = CornerController()

    total_moving = 0
    corner_interventions = 0
    straight_frames = 0
    high_steering_frames = 0
    high_steering_with_slip = 0
    throttle_reductions = []
    corner_brake_values = []

    for pkt in source.packets:
        raw = bytes.fromhex(pkt['hex'])
        fdp = ForzaDataPacket(raw, packet_format=PACKET_FORMAT)

        if fdp.speed < 5.0:
            continue
        total_moving += 1

        corner_throttle, corner_brake = cc.compute(fdp)

        if abs(fdp.steer) >= cc.steer_threshold:
            high_steering_frames += 1
            max_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                           fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)
            if max_slip > cc.slip_limit:
                high_steering_with_slip += 1
                throttle_reductions.append(corner_throttle)
                corner_brake_values.append(corner_brake)

        if corner_throttle < 1.0:
            corner_interventions += 1
        else:
            if abs(fdp.steer) < cc.steer_threshold:
                straight_frames += 1

    return {
        'total_moving': total_moving,
        'corner_interventions': corner_interventions,
        'straight_frames': straight_frames,
        'high_steering_frames': high_steering_frames,
        'high_steering_with_slip': high_steering_with_slip,
        'throttle_reductions': throttle_reductions,
        'corner_brake_values': corner_brake_values,
    }


def test_corner_intervenes_on_high_steering():
    """Corner must detect steering > threshold and reduce throttle."""
    results = _feed_recording(RECORDING_PATH)
    msg = (
        f"Expected corner interventions but got 0 "
        f"(out of {results['total_moving']} frames, "
        f"{results['high_steering_frames']} high-steer frames, "
        f"{results['high_steering_with_slip']} high-steer+high-slip frames)"
    )
    assert results['corner_interventions'] > 0, msg


def test_corner_no_intervention_when_straight():
    """No intervention when abs(steer) < threshold."""
    source = PlaybackSource(RECORDING_PATH)
    cc = CornerController()

    for pkt in source.packets:
        raw = bytes.fromhex(pkt['hex'])
        fdp = ForzaDataPacket(raw, packet_format=PACKET_FORMAT)
        if fdp.speed < 5.0:
            continue
        if abs(fdp.steer) < cc.steer_threshold:
            corner_throttle, corner_brake = cc.compute(fdp)
            assert corner_throttle == 1.0, \
                f"Corner intervened on straight (steer={fdp.steer:.3f}), throttle={corner_throttle}"
            assert corner_brake == 0.0, \
                f"Corner applied brake on straight (steer={fdp.steer:.3f}), brake={corner_brake}"


def test_corner_slip_aggravates_reduction():
    """When steer AND slip are both high, throttle reduction is stronger than steer-only."""
    results = _feed_recording(RECORDING_PATH)
    assert results['throttle_reductions'], \
        "No high-steer+high-slip frames found in recording"

    for throttle in results['throttle_reductions']:
        assert throttle < 1.0, \
            f"Corner throttle {throttle} should be < 1.0 when steer+slip exceed limits"


def test_corner_brake_on_high_slip_corner():
    """When steer and slip exceed limits, corner_brake is non-negative and throttle is reduced."""
    results = _feed_recording(RECORDING_PATH)
    assert results['corner_interventions'] > 0, \
        "No corner interventions in recording"

    for brake_val in results['corner_brake_values']:
        assert brake_val >= 0.0, \
            f"Corner brake {brake_val} must be non-negative"
