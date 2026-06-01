"""End-to-end run loop simulation: feeds synthetic FDPs through _dispatch_controllers
and verifies the SimulatedOutput log contains the expected sequence of actions."""

import sys
import time

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.core.forza import Forza
from horizon6_autogear.shifting.output_device import SharedState
from horizon6_autogear.shifting.simulated_output import SimulatedOutput
from horizon6_autogear.control.traction_controller import TractionController
from horizon6_autogear.control.arbiter import Arbiter
from horizon6_autogear.control.corner_controller import CornerController
from concurrent.futures import ThreadPoolExecutor


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
    engine.car_drivetrain = 1
    engine.shift_point_factor = 1.0
    engine.shift_point = {
        1: {'rpmo': 7000, 'speed': 100.0},
        2: {'rpmo': 7000, 'speed': 150.0},
    }
    engine._init_shift_controller()
    engine.shift_controller.last_upshift = 0
    return engine, output


def test_normal_driving_passes_full_throttle():
    """No slip, no steer, below shift RPM -> throttle 1.0."""
    engine, output = _make_engine()
    fdp = _make_fdp(gear=1, rpm=5000, speed=120.0, accel=255)
    engine._dispatch_controllers(0, fdp)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert abs(throttle_entries[0] - 1.0) < 0.01


def test_wheelspin_triggers_tcs_reduction():
    """High combined_slip on drive wheels -> TCS reduces throttle to 0.3."""
    engine, output = _make_engine()
    engine.tcs_enabled = True
    fdp = _make_fdp(gear=1, rpm=5000, speed=120.0, accel=255,
                    combined_slip_rl=0.8, combined_slip_rr=0.7)
    engine._dispatch_controllers(0, fdp)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert abs(throttle_entries[0] - 0.3) < 0.01


def test_tcs_recovery_restores_throttle():
    """Slip -> TCS reduces, then slip drops below recovery -> throttle 1.0."""
    engine, output = _make_engine()
    engine.tcs_enabled = True

    # Phase 1: wheelspin engages TCS
    fdp_slip = _make_fdp(gear=1, rpm=5000, speed=120.0, accel=255,
                         combined_slip_rl=0.8, combined_slip_rr=0.7)
    engine._dispatch_controllers(0, fdp_slip)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert abs(throttle_entries[0] - 0.3) < 0.01

    # Phase 2: slip drops well below recovery threshold (0.5 - 0.1 = 0.4) -> throttle restored
    output.clear()
    fdp_recovered = _make_fdp(gear=1, rpm=5000, speed=120.0, accel=255,
                              combined_slip_rl=0.1, combined_slip_rr=0.1)
    engine._dispatch_controllers(1, fdp_recovered)
    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 1
    assert abs(throttle_entries[0] - 1.0) < 0.01


def test_shift_triggered_at_high_rpm():
    """RPM exceeds shift_point -> shift action logged in output."""
    engine, output = _make_engine()
    engine.shift_controller.last_upshift = 0  # bypass cooldown
    fdp = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=255, slip_rear=0.2)
    engine._dispatch_controllers(0, fdp)
    time.sleep(0.4)  # wait for async shift execution in threadPool
    shift_entries = [v for _, ch, v in output.log if ch == 'shift']
    assert len(shift_entries) >= 1
    assert shift_entries[0] == 'up'


def test_full_scenario_sequence():
    """Feed packets in order: normal -> slip -> shift -> recovery.
    Verify the output log contains actions in the expected sequence."""
    engine, output = _make_engine()
    engine.tcs_enabled = True
    engine.shift_controller.last_upshift = 0  # bypass cooldown
    iteration = 0

    # Step 1: Normal driving - full throttle, no shift
    fdp_normal = _make_fdp(gear=1, rpm=5000, speed=120.0, accel=255)
    iteration = engine._dispatch_controllers(iteration, fdp_normal)

    assert len(output.log) == 2  # throttle + brake
    assert output.log[0][1] == 'throttle'
    assert abs(output.log[0][2] - 1.0) < 0.01
    assert output.log[1][1] == 'brake'

    # Step 2: Wheelspin - TCS reduces throttle
    fdp_slip = _make_fdp(gear=1, rpm=5500, speed=120.0, accel=255,
                         combined_slip_rl=0.8, combined_slip_rr=0.7)
    iteration = engine._dispatch_controllers(iteration, fdp_slip)

    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 2
    assert abs(throttle_entries[1] - 0.3) < 0.01  # second throttle entry is reduced

    # Step 3: High RPM triggers shift
    fdp_high_rpm = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=255,
                             combined_slip_rl=0.1, combined_slip_rr=0.1)
    iteration = engine._dispatch_controllers(iteration, fdp_high_rpm)
    time.sleep(0.4)  # wait for async shift execution

    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 3
    assert abs(throttle_entries[2] - 1.0) < 0.01  # slip recovered, full throttle

    shift_entries = [v for _, ch, v in output.log if ch == 'shift']
    assert len(shift_entries) == 1
    assert shift_entries[0] == 'up'

    # Step 4: Recovery after shift - driving in gear 2 at normal RPM, slip gone
    fdp_recovered = _make_fdp(gear=2, rpm=5000, speed=140.0, accel=255,
                              combined_slip_rl=0.1, combined_slip_rr=0.1)
    iteration = engine._dispatch_controllers(iteration, fdp_recovered)

    throttle_entries = [v for _, ch, v in output.log if ch == 'throttle']
    assert len(throttle_entries) == 4
    assert abs(throttle_entries[3] - 1.0) < 0.01  # full throttle restored

    # Verify overall sequence: throttle actions span 1.0 -> 0.3 -> 1.0 -> 1.0
    assert abs(throttle_entries[0] - 1.0) < 0.01  # normal
    assert abs(throttle_entries[1] - 0.3) < 0.01  # TCS intervention
    assert abs(throttle_entries[2] - 1.0) < 0.01  # shift point (slip recovered)
    assert abs(throttle_entries[3] - 1.0) < 0.01  # post-shift recovery

    # Verify shift happened between step 3 throttle and step 4 throttle
    channels = [ch for _, ch, _ in output.log]
    shift_index = channels.index('shift')
    # The shift should appear after the third throttle entry
    throttle_indices = [i for i, ch in enumerate(channels) if ch == 'throttle']
    assert shift_index > throttle_indices[2]
