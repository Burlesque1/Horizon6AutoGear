import sys
import time

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.shifting.output_device import SharedState
from horizon6_autogear.shifting.shift_controller import ShiftController
from horizon6_autogear.shifting.simulated_output import SimulatedOutput


def test_should_shift_up_when_rpm_exceeds_target():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {1: {'rpmo': 7000, 'speed': 100.0}}
    fdp = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) == ('up', 1)


def test_should_not_shift_when_no_shift_point():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {}
    fdp = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) is None


def test_should_shift_down_when_speed_drops():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {1: {'rpmo': 7000, 'speed': 100.0}, 2: {'rpmo': 7000, 'speed': 150.0}}
    fdp = _make_fdp(gear=2, rpm=3000, speed=90.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) == ('down', 2)


def test_should_not_shift_when_slip_too_high():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {1: {'rpmo': 7000, 'speed': 100.0}}
    fdp = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=True, slip_rear=1.5)
    assert sc.should_shift(fdp) is None


def test_should_not_shift_up_at_max_gear():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {6: {'rpmo': 7000, 'speed': 200.0}}
    fdp = _make_fdp(gear=6, rpm=7200, speed=220.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) is None


def _make_fdp(gear, rpm, speed, accel, slip_rear):
    """Create a minimal mock ForzaDataPacket for shift decisions."""
    fdp = type('FDP', (), {})()
    fdp.gear = gear
    fdp.current_engine_rpm = rpm
    fdp.speed = speed / 3.6
    fdp.accel = 255 if accel else 0
    fdp.tire_slip_ratio_RL = slip_rear
    fdp.tire_slip_ratio_RR = slip_rear
    fdp.tire_slip_ratio_FL = 0.0
    fdp.tire_slip_ratio_FR = 0.0
    fdp.tire_slip_angle_RL = 0.0
    fdp.tire_slip_angle_RR = 0.0
    fdp.tire_slip_angle_FL = 0.0
    fdp.tire_slip_angle_FR = 0.0
    fdp.drivetrain_type = 2
    return fdp
