"""Test telemetry data bridge from Python to JavaScript in gui.py."""

import json
import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from unittest.mock import Mock
from horizon6_autogear.gui import Api


def create_mock_fdp():
    """Create a mock ForzaDataPacket with all fields populated."""
    fdp = Mock()
    # Existing fields
    fdp.car_ordinal = 12345
    fdp.car_performance_index = 650
    fdp.car_class = 2  # B class
    fdp.drivetrain_type = 1  # RWD
    fdp.speed = 50.0  # m/s
    fdp.current_engine_rpm = 4500.0
    fdp.gear = 3
    fdp.engine_max_rpm = 8000.0
    fdp.accel = 200  # 0-255
    fdp.brake = 0  # 0-255
    fdp.acceleration_x = 0.5
    fdp.acceleration_y = 0.2
    fdp.acceleration_z = -9.81
    fdp.boost = 1.0
    fdp.fuel = 0.85
    fdp.torque = 500.0
    fdp.power = 300000.0  # W

    # Tire data
    fdp.tire_temp_FL = 85.0
    fdp.tire_temp_FR = 87.0
    fdp.tire_temp_RL = 90.0
    fdp.tire_temp_RR = 92.0
    fdp.tire_combined_slip_FL = 0.12
    fdp.tire_combined_slip_FR = 0.18
    fdp.tire_combined_slip_RL = 0.22
    fdp.tire_combined_slip_RR = 0.28
    fdp.norm_suspension_travel_FL = 0.1
    fdp.norm_suspension_travel_FR = 0.15
    fdp.norm_suspension_travel_RL = 0.2
    fdp.norm_suspension_travel_RR = 0.25

    # NEW fields - top-level
    fdp.clutch = 0
    fdp.handbrake = 0
    fdp.steer = -0.5
    fdp.engine_idle_rpm = 900.0
    fdp.angular_velocity_x = 0.1  # yaw_rate
    fdp.pitch = 0.3
    fdp.roll = -0.2
    fdp.best_lap_time = 72.5
    fdp.last_lap_time = 75.3
    fdp.cur_lap_time = 45.2
    fdp.lap_no = 3
    fdp.race_pos = 5
    fdp.cur_race_time = 300.5
    fdp.dist_traveled = 5000.0
    fdp.num_cylinders = 8
    fdp.norm_driving_line = 30
    fdp.norm_ai_brake_diff = 15
    fdp.yaw = 1.234
    fdp.position_x = 100.5
    fdp.position_y = 5.2
    fdp.position_z = -200.8

    # NEW fields - tire data
    fdp.tire_slip_ratio_FL = 0.05
    fdp.tire_slip_ratio_FR = 0.06
    fdp.tire_slip_ratio_RL = 0.07
    fdp.tire_slip_ratio_RR = 0.08
    fdp.tire_slip_angle_FL = 0.1
    fdp.tire_slip_angle_FR = 0.15
    fdp.tire_slip_angle_RL = 0.2
    fdp.tire_slip_angle_RR = 0.25
    fdp.suspension_travel_meters_FL = 0.05
    fdp.suspension_travel_meters_FR = 0.06
    fdp.suspension_travel_meters_RL = 0.07
    fdp.suspension_travel_meters_RR = 0.08
    fdp.wheel_rotation_speed_FL = 10.0
    fdp.wheel_rotation_speed_FR = 11.0
    fdp.wheel_rotation_speed_RL = 12.0
    fdp.wheel_rotation_speed_RR = 13.0

    return fdp


def test_update_car_info_all_fields():
    """Test that update_car_info includes all required telemetry fields."""
    # Setup
    api = Api()
    mock_window = Mock()
    api.set_window(mock_window)

    # Mock the Forza engine setup
    from concurrent.futures import ThreadPoolExecutor

    api.threadPool = ThreadPoolExecutor(max_workers=8)
    api.engine = Mock()
    api.engine.isRunning = True
    api.engine.gear_ratios = {3: {'ratio': 1.5}}

    # Create mock ForzaDataPacket
    fdp = create_mock_fdp()

    # Track JS calls
    js_calls = []
    def capture_js(js_code):
        js_calls.append(js_code)
    mock_window.evaluate_js = capture_js

    # Execute
    api.update_car_info(fdp)

    # Verify JS was called
    assert len(js_calls) == 1
    js_call = js_calls[0]

    # Extract JSON payload from onTelemetry(...) call
    assert 'onTelemetry(' in js_call
    json_start = js_call.find('onTelemetry(') + len('onTelemetry(')
    json_str = js_call[json_start:].rstrip(')')
    data = json.loads(json_str)

    # Verify existing top-level fields
    assert 'car_ordinal' in data
    assert 'car_perf' in data
    assert 'car_class' in data
    assert 'drivetrain' in data
    assert 'speed' in data
    assert 'rpm' in data
    assert 'gear' in data
    assert 'engine_max_rpm' in data
    assert 'accel' in data
    assert 'brake' in data
    assert 'accel_x' in data
    assert 'accel_z' in data
    assert 'boost' in data
    assert 'fuel' in data
    assert 'torque' in data
    assert 'output_torque' in data
    assert 'power' in data

    # Verify NEW top-level fields
    assert 'clutch' in data, "Missing field: clutch"
    assert 'handbrake' in data, "Missing field: handbrake"
    assert 'steer' in data, "Missing field: steer"
    assert 'engine_idle_rpm' in data, "Missing field: engine_idle_rpm"
    assert 'accel_y' in data, "Missing field: accel_y"
    assert 'yaw_rate' in data, "Missing field: yaw_rate"
    assert 'pitch' in data, "Missing field: pitch"
    assert 'roll' in data, "Missing field: roll"
    assert 'best_lap_time' in data, "Missing field: best_lap_time"
    assert 'last_lap_time' in data, "Missing field: last_lap_time"
    assert 'cur_lap_time' in data, "Missing field: cur_lap_time"
    assert 'lap_no' in data, "Missing field: lap_no"
    assert 'race_pos' in data, "Missing field: race_pos"
    assert 'cur_race_time' in data, "Missing field: cur_race_time"
    assert 'dist_traveled' in data, "Missing field: dist_traveled"
    assert 'num_cylinders' in data, "Missing field: num_cylinders"
    assert 'norm_driving_line' in data, "Missing field: norm_driving_line"
    assert 'norm_ai_brake_diff' in data, "Missing field: norm_ai_brake_diff"
    assert 'combined_slip_FL' in data, "Missing field: combined_slip_FL"
    assert 'combined_slip_FR' in data, "Missing field: combined_slip_FR"
    assert 'combined_slip_RL' in data, "Missing field: combined_slip_RL"
    assert 'combined_slip_RR' in data, "Missing field: combined_slip_RR"

    # Verify new field values
    assert data['clutch'] == 0
    assert data['handbrake'] == 0
    assert data['steer'] == -0.5
    assert data['engine_idle_rpm'] == 900.0
    assert data['accel_y'] == 0.2
    assert data['yaw_rate'] == 0.1
    assert data['pitch'] == 0.3
    assert data['roll'] == -0.2
    assert data['best_lap_time'] == 72.5
    assert data['last_lap_time'] == 75.3
    assert data['cur_lap_time'] == 45.2
    assert data['lap_no'] == 3
    assert data['race_pos'] == 5
    assert data['cur_race_time'] == 300.5
    assert data['dist_traveled'] == 5000.0
    assert data['num_cylinders'] == 8

    # Verify tires structure exists
    assert 'tires' in data
    assert 'FL' in data['tires']
    assert 'FR' in data['tires']
    assert 'RL' in data['tires']
    assert 'RR' in data['tires']

    # Verify existing tire fields
    for corner in ['FL', 'FR', 'RL', 'RR']:
        assert 'temp' in data['tires'][corner]
        assert 'slip' in data['tires'][corner]
        assert 'susp' in data['tires'][corner]

    # Verify NEW tire fields for each corner
    for corner in ['FL', 'FR', 'RL', 'RR']:
        assert 'slip_ratio' in data['tires'][corner], f"Missing tire field: {corner}.slip_ratio"
        assert 'slip_angle' in data['tires'][corner], f"Missing tire field: {corner}.slip_angle"
        assert 'combined_slip' in data['tires'][corner], f"Missing tire field: {corner}.combined_slip"
        assert 'susp_meters' in data['tires'][corner], f"Missing tire field: {corner}.susp_meters"
        assert 'wheel_speed' in data['tires'][corner], f"Missing tire field: {corner}.wheel_speed"

    # Verify specific tire values
    assert data['tires']['FL']['slip_ratio'] == 0.05
    assert data['tires']['FL']['slip_angle'] == 0.1
    assert data['tires']['FL']['combined_slip'] == 0.12
    assert data['tires']['FL']['susp_meters'] == 0.05
    assert data['tires']['FL']['wheel_speed'] == 10

    assert data['tires']['FR']['slip_ratio'] == 0.06
    assert data['tires']['FR']['slip_angle'] == 0.15
    assert data['tires']['FR']['combined_slip'] == 0.18
    assert data['tires']['FR']['susp_meters'] == 0.06
    assert data['tires']['FR']['wheel_speed'] == 11

    assert data['tires']['RL']['slip_ratio'] == 0.07
    assert data['tires']['RL']['slip_angle'] == 0.2
    assert data['tires']['RL']['combined_slip'] == 0.22
    assert data['tires']['RL']['susp_meters'] == 0.07
    assert data['tires']['RL']['wheel_speed'] == 12

    assert data['tires']['RR']['slip_ratio'] == 0.08
    assert data['tires']['RR']['slip_angle'] == 0.25
    assert data['tires']['RR']['combined_slip'] == 0.28
    assert data['tires']['RR']['susp_meters'] == 0.08
    assert data['tires']['RR']['wheel_speed'] == 13


if __name__ == '__main__':
    test_update_car_info_all_fields()
    print("All tests passed!")
