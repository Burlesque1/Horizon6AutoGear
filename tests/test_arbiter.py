import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.control.arbiter import Arbiter


def test_no_intervention_passes_driver_throttle():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.8, tcs_throttle=1.0,
                         corner_throttle=1.0, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.8
    assert result.brake == 0.0


def test_tcs_reduces_throttle():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=1.0, tcs_throttle=0.3,
                         corner_throttle=1.0, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.3


def test_corner_and_tcs_both_reduce():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=1.0, tcs_throttle=0.5,
                         corner_throttle=0.7, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.5


def test_corner_brake_passes_through():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.5, tcs_throttle=1.0,
                         corner_throttle=1.0, corner_brake=0.4,
                         shift_pending=False)
    assert result.brake == 0.4


def test_shift_pending_suppresses_tcs():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.8, tcs_throttle=0.3,
                         corner_throttle=0.7, corner_brake=0.4,
                         shift_pending=True)
    assert result.throttle == 0.8
    assert result.brake == 0.0


def test_defaults_when_controllers_missing():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.9, tcs_throttle=1.0,
                         corner_throttle=1.0, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.9
    assert result.brake == 0.0
