"""Tests for SemiAutoController and Arbiter semi-auto extension."""

import pytest

from horizon6_autogear.control.arbiter import Arbiter
from horizon6_autogear.control.pid_controller import PIDController
from horizon6_autogear.control.semi_auto_controller import (
    ANTICIPATION_DISTANCES,
    BRAKE_RELEASE_HYSTERESIS,
    SemiAutoController,
    SemiAutoDecision,
)


class MockFdp:
    def __init__(self, speed=50.0):
        self.speed = speed


def _make_controller():
    pid = PIDController(kp=0.5, ki=0.05, kd=0.1)
    return SemiAutoController(pid)


def _make_ref_data(distance=40.0, severity='medium', entry_speed=40.0,
                   throttle=0.8, gear_suggestion=None):
    return {
        'next_brake_point': {
            'distance': distance,
            'severity': severity,
            'entry_speed': entry_speed,
        },
        'throttle': throttle,
        'gear_suggestion': gear_suggestion,
    }


class TestSemiAutoControllerNoIntervention:
    """Cases where SemiAutoController returns zero intervention."""

    def test_no_ref_data_returns_zero(self):
        ctrl = _make_controller()
        fdp = MockFdp(speed=50.0)
        result = ctrl.compute(fdp, None)
        assert result.brake_force == 0.0
        assert result.throttle_override is None
        assert result.should_shift is None
        assert result.brake_zone_active is False

    def test_no_next_brake_point_returns_zero(self):
        ctrl = _make_controller()
        fdp = MockFdp(speed=50.0)
        result = ctrl.compute(fdp, {'next_brake_point': None})
        assert result.brake_force == 0.0
        assert result.brake_zone_active is False

    def test_speed_below_entry_speed_hysteresis_no_braking(self):
        ctrl = _make_controller()
        entry_speed = 50.0
        fdp = MockFdp(speed=entry_speed * BRAKE_RELEASE_HYSTERESIS - 1.0)
        ref = _make_ref_data(distance=40.0, entry_speed=entry_speed)
        result = ctrl.compute(fdp, ref)
        assert result.brake_force == 0.0
        assert result.brake_zone_active is False

    def test_distance_ahead_exceeds_anticipation_no_braking(self):
        ctrl = _make_controller()
        fdp = MockFdp(speed=60.0)
        ref = _make_ref_data(
            distance=ANTICIPATION_DISTANCES['heavy'] + 10.0,
            severity='heavy',
            entry_speed=30.0,
        )
        result = ctrl.compute(fdp, ref)
        assert result.brake_force == 0.0
        assert result.brake_zone_active is False


class TestSemiAutoControllerBraking:
    """Cases where SemiAutoController applies braking."""

    def test_speed_above_entry_speed_within_anticipation_brakes(self):
        ctrl = _make_controller()
        fdp = MockFdp(speed=60.0)
        ref = _make_ref_data(distance=40.0, severity='medium', entry_speed=30.0)
        result = ctrl.compute(fdp, ref)
        assert result.brake_force > 0.0
        assert result.brake_zone_active is True

    def test_throttle_override_when_ref_throttle_low(self):
        ctrl = _make_controller()
        fdp = MockFdp(speed=60.0)
        ref = _make_ref_data(distance=40.0, entry_speed=30.0, throttle=0.05)
        result = ctrl.compute(fdp, ref)
        assert result.throttle_override == 0.0

    def test_no_throttle_override_when_ref_throttle_normal(self):
        ctrl = _make_controller()
        fdp = MockFdp(speed=60.0)
        ref = _make_ref_data(distance=40.0, entry_speed=30.0, throttle=0.8)
        result = ctrl.compute(fdp, ref)
        assert result.throttle_override is None

    def test_gear_suggestion_propagated(self):
        ctrl = _make_controller()
        fdp = MockFdp(speed=60.0)
        ref = _make_ref_data(distance=40.0, entry_speed=30.0, gear_suggestion='down')
        result = ctrl.compute(fdp, ref)
        assert result.should_shift == ('down',)


class TestArbiterSemiAuto:
    """Tests for Arbiter semi-auto parameter extension."""

    def test_semi_auto_brake_merges_with_corner_brake(self):
        arb = Arbiter()
        result = arb.resolve(
            driver_throttle=1.0, tcs_throttle=1.0,
            corner_throttle=1.0, corner_brake=0.3,
            shift_pending=False,
            semi_auto_brake=0.5,
        )
        assert result.brake == 0.5

    def test_semi_auto_brake_lower_than_corner_brake(self):
        arb = Arbiter()
        result = arb.resolve(
            driver_throttle=1.0, tcs_throttle=1.0,
            corner_throttle=1.0, corner_brake=0.7,
            shift_pending=False,
            semi_auto_brake=0.2,
        )
        assert result.brake == 0.7

    def test_semi_auto_throttle_override(self):
        arb = Arbiter()
        result = arb.resolve(
            driver_throttle=1.0, tcs_throttle=1.0,
            corner_throttle=1.0, corner_brake=0.0,
            shift_pending=False,
            semi_auto_throttle_override=0.0,
        )
        assert result.throttle == 0.0

    def test_backward_compatibility_no_semi_auto_params(self):
        arb = Arbiter()
        result = arb.resolve(
            driver_throttle=0.8, tcs_throttle=1.0,
            corner_throttle=1.0, corner_brake=0.0,
            shift_pending=False,
        )
        assert result.throttle == 0.8
        assert result.brake == 0.0

    def test_shift_pending_still_takes_priority(self):
        arb = Arbiter()
        result = arb.resolve(
            driver_throttle=0.8, tcs_throttle=0.5,
            corner_throttle=0.6, corner_brake=0.4,
            shift_pending=True,
            semi_auto_brake=0.9,
            semi_auto_throttle_override=0.0,
        )
        assert result.throttle == 0.8
        assert result.brake == 0.0
