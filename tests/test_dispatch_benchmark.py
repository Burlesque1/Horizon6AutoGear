"""Performance benchmark for _dispatch_controllers.

Verifies the fast-tier control loop completes within the 5ms budget.
Run via: pytest tests/test_dispatch_benchmark.py -v -s
"""

import time
import statistics

from concurrent.futures import ThreadPoolExecutor

import pytest

from horizon6_autogear.core.forza import Forza
from horizon6_autogear.shifting.output_device import SharedState
from horizon6_autogear.shifting.simulated_output import SimulatedOutput
from horizon6_autogear.control.traction_controller import TractionController
from horizon6_autogear.control.arbiter import Arbiter
from horizon6_autogear.control.corner_controller import CornerController


def _make_fdp(gear=3, rpm=6000, speed=50.0, accel=200,
              combined_slip_fl=0.0, combined_slip_fr=0.0,
              combined_slip_rl=0.1, combined_slip_rr=0.1,
              steer=0.0, drivetrain=2):
    """Create a minimal ForzaDataPacket-like object for benchmarking."""
    fdp = type('FDP', (), {})()
    fdp.gear = gear
    fdp.current_engine_rpm = rpm
    fdp.speed = speed / 3.6  # km/h -> m/s
    fdp.accel = accel
    fdp.tire_slip_ratio_FL = 0.0
    fdp.tire_slip_ratio_FR = 0.0
    fdp.tire_slip_ratio_RL = 0.0
    fdp.tire_slip_ratio_RR = 0.0
    fdp.tire_slip_angle_FL = 0.0
    fdp.tire_slip_angle_FR = 0.0
    fdp.tire_slip_angle_RL = 0.0
    fdp.tire_slip_angle_RR = 0.0
    fdp.tire_combined_slip_FL = combined_slip_fl
    fdp.tire_combined_slip_FR = combined_slip_fr
    fdp.tire_combined_slip_RL = combined_slip_rl
    fdp.tire_combined_slip_RR = combined_slip_rr
    fdp.steer = steer
    fdp.drivetrain_type = drivetrain
    fdp.car_ordinal = 1
    fdp.car_class = 0
    fdp.car_performance_index = 0
    fdp.brake = 0
    return fdp


def _make_engine():
    """Create a Forza engine with SimulatedOutput for benchmarking."""
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bench")
    engine = Forza(pool, packet_format='fh6', enable_clutch=False)
    engine.output_device = SimulatedOutput()
    engine.shared_state = SharedState()
    engine.traction_controller = TractionController()
    engine.arbiter = Arbiter()
    engine.corner_controller = CornerController()
    engine.isRunning = True
    engine.minGear = 1
    engine.maxGear = 10
    engine.car_drivetrain = 2  # AWD
    engine.shift_point_factor = 1.0
    engine.shift_point = {
        2: {'rpmo': 6500, 'speed': 100.0},
        3: {'rpmo': 6500, 'speed': 150.0},
        4: {'rpmo': 6500, 'speed': 200.0},
    }
    engine._init_shift_controller()
    return engine


@pytest.fixture
def engine():
    e = _make_engine()
    yield e
    e.isRunning = False
    e.threadPool.shutdown(wait=False)


def test_dispatch_timing_1000_packets(engine):
    """Feed 1000 synthetic packets, verify mean/median/p95 < 5ms."""
    fdp = _make_fdp(gear=3, rpm=4000, speed=120.0)

    # Warm up (let JIT / caches settle)
    for _ in range(10):
        engine._dispatch_controllers(0, fdp)

    timings = []
    for i in range(1000):
        t0 = time.perf_counter()
        engine._dispatch_controllers(i, fdp)
        elapsed = (time.perf_counter() - t0) * 1000  # ms
        timings.append(elapsed)

    mean_t = statistics.mean(timings)
    median_t = statistics.median(timings)
    p95_t = sorted(timings)[int(len(timings) * 0.95)]
    max_t = max(timings)

    print("\n_dispatch_controllers benchmark (1000 packets):")
    print(f"  mean:   {mean_t:.3f} ms")
    print(f"  median: {median_t:.3f} ms")
    print(f"  p95:    {p95_t:.3f} ms")
    print(f"  max:    {max_t:.3f} ms")

    assert p95_t < 5.0, f"P95 latency {p95_t:.3f}ms exceeds 5ms budget"


def test_dispatch_timing_with_tcs_enabled(engine):
    """Benchmark with TCS active (higher compute path)."""
    engine.tcs_enabled = True
    fdp = _make_fdp(gear=3, rpm=4000, speed=120.0,
                    combined_slip_rl=0.6, combined_slip_rr=0.6)

    timings = []
    for i in range(1000):
        t0 = time.perf_counter()
        engine._dispatch_controllers(i, fdp)
        elapsed = (time.perf_counter() - t0) * 1000
        timings.append(elapsed)

    p95_t = sorted(timings)[int(len(timings) * 0.95)]

    print("\n_dispatch_controllers with TCS active (1000 packets):")
    print(f"  p95: {p95_t:.3f} ms")

    assert p95_t < 5.0, f"P95 with TCS {p95_t:.3f}ms exceeds 5ms budget"
