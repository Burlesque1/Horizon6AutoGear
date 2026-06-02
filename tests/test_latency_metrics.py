"""Tests for LatencyMetrics and LatencyCollector."""
import sys

sys.path.append(r".")
sys.path.append(r"./src")

import time

from horizon6_autogear.control.latency_metrics import LatencyCollector, LatencyMetrics


def test_empty_collector_returns_zeros():
    c = LatencyCollector()
    assert c.avg_total_ms == 0.0
    assert c.p95_total_ms == 0.0
    assert c.max_total_ms == 0.0
    assert c.speed_error_avg == 0.0


def test_single_frame():
    c = LatencyCollector()
    c.start_frame()
    c.record_match(1.0)
    c.record_pid(0.5)
    c.record_gamepad(0.3)
    metrics = c.end_frame(speed_error=2.0, brake_output=0.8)

    assert isinstance(metrics, LatencyMetrics)
    assert metrics.match_time_ms == 1.0
    assert metrics.pid_time_ms == 0.5
    assert metrics.gamepad_send_ms == 0.3
    assert metrics.speed_error == 2.0
    assert metrics.brake_output == 0.8
    assert metrics.total_loop_ms > 0
    assert c.avg_total_ms > 0


def test_rolling_stats():
    c = LatencyCollector()
    for val in [1.0, 2.0, 3.0, 4.0, 5.0]:
        c._frame_start = time.monotonic() - val / 1000.0
        c.end_frame()

    assert abs(c.avg_total_ms - 3.0) < 0.1
    assert abs(c.max_total_ms - 5.0) < 0.1


def test_p95_computation():
    c = LatencyCollector()
    for val in range(1, 21):
        c.start_frame()
        c._frame_start = time.monotonic() - float(val) / 1000.0
        c.end_frame()

    p95 = c.p95_total_ms
    assert 18.0 <= p95 <= 20.0


def test_to_dict():
    c = LatencyCollector()
    for _ in range(3):
        c.start_frame()
        c.end_frame()

    d = c.to_dict()
    assert "avg_total_ms" in d
    assert "p95_total_ms" in d
    assert "max_total_ms" in d
    assert "speed_error_avg" in d
    assert "frame_count" in d
    assert d["frame_count"] == 3


def test_speed_error_avg():
    c = LatencyCollector()
    for err in [1.0, 2.0, 3.0]:
        c.start_frame()
        c.end_frame(speed_error=err)

    assert c.speed_error_avg == 2.0
