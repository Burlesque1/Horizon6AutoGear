"""Tests for PIDController brake modulation."""
import sys
import pytest

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.control.pid_controller import PIDController


class TestPIDController:

    def test_zero_error_zero_output(self):
        pid = PIDController()
        assert pid.compute(0.0, 0.016) == 0.0

    def test_positive_error_positive_output(self):
        pid = PIDController()
        assert pid.compute(5.0, 0.016) > 0.0

    def test_integral_accumulates(self):
        pid = PIDController(kp=0.05, ki=0.05, kd=0.0)
        out1 = pid.compute(1.0, 0.016)
        out2 = pid.compute(1.0, 0.016)
        assert out2 > out1

    def test_anti_windup(self):
        pid = PIDController(kp=0.0, ki=1.0, kd=0.0, integral_limit=0.1)
        for _ in range(200):
            pid.compute(100.0, 0.016)
        assert abs(pid._integral) <= 0.1 + 1e-9

    def test_output_clamped(self):
        pid = PIDController()
        assert pid.compute(1000.0, 0.016) <= 1.0

    def test_reset_clears_state(self):
        pid = PIDController()
        pid.compute(5.0, 0.016)
        pid.compute(5.0, 0.016)
        pid.reset()
        assert pid.compute(0.0, 0.016) == 0.0

    def test_update_gains(self):
        pid = PIDController(kp=0.1, ki=0.0, kd=0.0)
        out1 = pid.compute(1.0, 0.016)
        pid.update_gains(kp=0.4)
        pid.reset()
        out2 = pid.compute(1.0, 0.016)
        ratio = out2 / out1 if out1 > 0 else float('inf')
        assert ratio == pytest.approx(4.0, rel=1e-6)

    def test_negative_error_zero_output(self):
        pid = PIDController()
        assert pid.compute(-5.0, 0.016) == 0.0
