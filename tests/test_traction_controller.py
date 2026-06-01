import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.control.traction_controller import TractionController


def test_no_intervention_below_min_speed():
    tc = TractionController()
    fdp = _make_fdp(speed=3.0, combined_slip_rl=0.8, combined_slip_rr=0.9, drivetrain=1)
    assert tc.compute(fdp) == 1.0


def test_no_intervention_below_slip_threshold():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.2, combined_slip_rr=0.3, drivetrain=1)
    assert tc.compute(fdp) == 1.0


def test_rwd_intervention_on_rear_slip():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.7, combined_slip_rr=0.8, drivetrain=1)
    assert tc.compute(fdp) < 1.0


def test_fwd_intervention_on_front_slip():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_fl=0.7, combined_slip_fr=0.8, drivetrain=0)
    assert tc.compute(fdp) < 1.0


def test_fwd_ignores_rear_slip():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.9, combined_slip_rr=0.9, drivetrain=0)
    assert tc.compute(fdp) == 1.0


def test_awd_monitors_all_wheels():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.1, combined_slip_rr=0.1,
                    combined_slip_fl=0.1, combined_slip_fr=0.8, drivetrain=2)
    assert tc.compute(fdp) < 1.0


def test_custom_threshold():
    tc = TractionController(slip_threshold=0.3, throttle_reduction=0.4)
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.4, combined_slip_rr=0.5, drivetrain=1)
    assert tc.compute(fdp) == 0.4


def _make_fdp(speed, combined_slip_rl=0.0, combined_slip_rr=0.0,
              combined_slip_fl=0.0, combined_slip_fr=0.0, drivetrain=1):
    fdp = type('FDP', (), {})()
    fdp.speed = speed
    fdp.tire_combined_slip_RL = combined_slip_rl
    fdp.tire_combined_slip_RR = combined_slip_rr
    fdp.tire_combined_slip_FL = combined_slip_fl
    fdp.tire_combined_slip_FR = combined_slip_fr
    fdp.drivetrain_type = drivetrain
    return fdp
