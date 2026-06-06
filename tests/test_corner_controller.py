import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.control.corner_controller import CornerController


def test_no_intervention_on_straight():
    cc = CornerController()
    fdp = _make_fdp(steer=0.1, max_slip=0.2)
    throttle, brake = cc.compute(fdp)
    assert throttle == 1.0
    assert brake == 0.0


def test_reduce_throttle_in_corner_with_slip():
    cc = CornerController()
    fdp = _make_fdp(steer=0.5, max_slip=0.5)
    throttle, brake = cc.compute(fdp)
    assert throttle < 1.0
    assert brake == 0.0


def test_corner_without_slip_no_intervention():
    cc = CornerController()
    fdp = _make_fdp(steer=0.5, max_slip=0.2)
    throttle, brake = cc.compute(fdp)
    assert throttle == 1.0
    assert brake == 0.0


def test_custom_thresholds():
    cc = CornerController(steer_threshold=0.5, slip_limit=0.3, throttle_reduction=0.5)
    fdp = _make_fdp(steer=0.6, max_slip=0.4)
    throttle, brake = cc.compute(fdp)
    assert throttle == 0.5


def _make_fdp(steer, max_slip):
    fdp = type('FDP', (), {})()
    fdp.steer = steer
    fdp.speed = 30.0
    fdp.tire_combined_slip_FL = max_slip
    fdp.tire_combined_slip_FR = max_slip * 0.9
    fdp.tire_combined_slip_RL = max_slip * 0.8
    fdp.tire_combined_slip_RR = max_slip * 0.7
    return fdp
