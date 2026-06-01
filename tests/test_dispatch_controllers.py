"""Integration tests for _dispatch_controllers: TCS + Arbiter + shift decision via SimulatedOutput."""

import sys
import time

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.core.forza import Forza
from horizon6_autogear.shifting.output_device import SharedState
from horizon6_autogear.shifting.shift_controller import ShiftController
from horizon6_autogear.shifting.simulated_output import SimulatedOutput
from horizon6_autogear.control.traction_controller import TractionController
from horizon6_autogear.control.arbiter import Arbiter
from horizon6_autogear.control.corner_controller import CornerController
from concurrent.futures import ThreadPoolExecutor


def _make_engine():
    """Create a minimal Forza engine with SimulatedOutput for testing."""
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="test")
    engine = Forza(pool, packet_format='fh6', enable_clutch=True)
    output = SimulatedOutput()
    engine.output_device = output
    engine.shared_state = SharedState()
    engine.traction_controller = TractionController()
    engine.arbiter = Arbiter()
    engine.corner_controller = CornerController()
    engine.minGear = 1
    engine.maxGear = 6
    engine.car_drivetrain = 1  # RWD
    engine.shift_point_factor = 1.0
    engine.shift_point = {
        1: {'rpmo': 7000, 'speed': 100.0},
        2: {'rpmo': 7000, 'speed': 150.0},
    }
    engine._init_shift_controller()
    return engine, output


def _make_fdp(gear=1, rpm=5000, speed=80.0, accel=255, slip_rear=0.2,
              combined_slip_rl=0.1, combined_slip_rr=0.1,
              combined_slip_fl=0.0, combined_slip_fr=0.0,
              steer=0.0, drivetrain=1):
    fdp = type('FDP', (), {})()
    fdp.gear = gear
    fdp.current_engine_rpm = rpm
    fdp.speed = speed / 3.6  # km/h to m/s
    fdp.accel = accel
    fdp.tire_slip_ratio_RL = slip_rear
    fdp.tire_slip_ratio_RR = slip_rear
    fdp.tire_slip_ratio_FL = 0.0
    fdp.tire_slip_ratio_FR = 0.0
    fdp.tire_slip_angle_RL = 0.0
    fdp.tire_slip_angle_RR = 0.0
    fdp.tire_slip_angle_FL = 0.0
    fdp.tire_slip_angle_FR = 0.0
    fdp.tire_combined_slip_RL = combined_slip_rl
    fdp.tire_combined_slip_RR = combined_slip_rr
    fdp.tire_combined_slip_FL = combined_slip_fl
    fdp.tire_combined_slip_FR = combined_slip_fr
    fdp.steer = steer
    fdp.drivetrain_type = drivetrain
    return fdp


def test_dispatch_normal_driving_passes_driver_throttle():
    engine, output = _make_engine()
    fdp = _make_fdp(speed=120, accel=255)
    engine._dispatch_controllers(0, fdp)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert abs(throttle_entries[0] - 1.0) < 0.01


def test_dispatch_tcs_reduces_throttle_on_slip():
    engine, output = _make_engine()
    engine.tcs_enabled = True
    fdp = _make_fdp(speed=120, accel=255, combined_slip_rl=0.8, combined_slip_rr=0.7)
    engine._dispatch_controllers(0, fdp)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert throttle_entries[0] <= 0.3


def test_dispatch_tcs_disabled_passes_through():
    engine, output = _make_engine()
    engine.tcs_enabled = False
    fdp = _make_fdp(speed=120, accel=255, combined_slip_rl=0.8, combined_slip_rr=0.7)
    engine._dispatch_controllers(0, fdp)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert abs(throttle_entries[0] - 1.0) < 0.01


def test_dispatch_shift_pending_suppresses_tcs():
    engine, output = _make_engine()
    engine.tcs_enabled = True
    engine.shared_state.shift_pending.set()
    fdp = _make_fdp(speed=120, accel=255, combined_slip_rl=0.8)
    engine._dispatch_controllers(0, fdp)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert abs(throttle_entries[0] - 1.0) < 0.01  # TCS suppressed, driver throttle passes


def test_dispatch_triggers_upshift():
    engine, output = _make_engine()
    engine.shift_controller.last_upshift = 0  # bypass cooldown
    fdp = _make_fdp(gear=1, rpm=7200, speed=120, accel=255)
    engine._dispatch_controllers(0, fdp)
    time.sleep(0.4)  # wait for async shift execution
    shift_entries = [v for _, ch, v in output.log if ch == 'shift']
    assert len(shift_entries) >= 1
    assert shift_entries[0] == 'up'


def test_dispatch_no_shift_below_target_rpm():
    engine, output = _make_engine()
    fdp = _make_fdp(gear=1, rpm=4000, speed=80, accel=255)
    engine._dispatch_controllers(0, fdp)
    time.sleep(0.1)
    shift_entries = [v for _, ch, v in output.log if ch == 'shift']
    assert len(shift_entries) == 0


def test_set_output_device_updates_shift_controller():
    engine, _ = _make_engine()
    new_output = SimulatedOutput()
    engine.set_output_device(new_output)
    assert engine.output_device is new_output
    assert engine.shift_controller.output_device is new_output


def test_set_output_device_releases_old():
    engine, old_output = _make_engine()
    old_output.set_analog('throttle', 0.8)
    new_output = SimulatedOutput()
    engine.set_output_device(new_output)
    assert engine.output_device is new_output


def test_dispatch_arbiter_lowest_wins_throttle():
    engine, output = _make_engine()
    engine.tcs_enabled = True
    fdp = _make_fdp(speed=120, accel=128, combined_slip_rl=0.8)
    engine._dispatch_controllers(0, fdp)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert throttle_entries[0] <= 0.3


def test_dispatch_low_speed_skips():
    engine, output = _make_engine()
    fdp = _make_fdp(speed=0.2, accel=255, combined_slip_rl=0.8)  # 0.2 km/h = 0.056 m/s < 0.1 threshold
    engine._dispatch_controllers(0, fdp)
    assert len(output.log) == 0
