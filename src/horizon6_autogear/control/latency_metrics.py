"""Latency metrics instrumentation for the control loop."""
import csv
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class LatencyMetrics:
    """Per-frame latency snapshot."""

    match_time_ms: float = 0.0
    pid_time_ms: float = 0.0
    gamepad_send_ms: float = 0.0
    total_loop_ms: float = 0.0
    speed_error: float = 0.0
    brake_output: float = 0.0


class LatencyCollector:
    """Collects rolling-window latency statistics and optional CSV export."""

    def __init__(self, window_size: int = 60):
        self._window: deque[LatencyMetrics] = deque(maxlen=window_size)
        self._frame_start: float = 0.0
        self._match_ms: float = 0.0
        self._pid_ms: float = 0.0
        self._gamepad_ms: float = 0.0
        self._speed_errors: deque[float] = deque(maxlen=window_size)
        self._csv_path: str | None = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    def start_frame(self) -> None:
        self._frame_start = time.monotonic()
        self._match_ms = 0.0
        self._pid_ms = 0.0
        self._gamepad_ms = 0.0

    def record_match(self, elapsed_ms: float) -> None:
        self._match_ms = elapsed_ms

    def record_pid(self, elapsed_ms: float) -> None:
        self._pid_ms = elapsed_ms

    def record_gamepad(self, elapsed_ms: float) -> None:
        self._gamepad_ms = elapsed_ms

    def end_frame(
        self, speed_error: float = 0.0, brake_output: float = 0.0
    ) -> LatencyMetrics:
        total = (time.monotonic() - self._frame_start) * 1000.0
        metrics = LatencyMetrics(
            match_time_ms=self._match_ms,
            pid_time_ms=self._pid_ms,
            gamepad_send_ms=self._gamepad_ms,
            total_loop_ms=total,
            speed_error=speed_error,
            brake_output=brake_output,
        )
        self._window.append(metrics)
        self._speed_errors.append(abs(speed_error))
        if self._csv_path:
            self._executor.submit(self._append_csv_row, metrics)
        return metrics

    def enable_csv(self, path: str) -> None:
        self._csv_path = path
        write_header = not os.path.exists(path)
        if write_header:
            dirpath = os.path.dirname(path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "match_ms",
                        "pid_ms",
                        "gamepad_ms",
                        "total_ms",
                        "speed_error",
                        "brake_output",
                    ]
                )

    def _append_csv_row(self, metrics: LatencyMetrics) -> None:
        with open(self._csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    metrics.match_time_ms,
                    metrics.pid_time_ms,
                    metrics.gamepad_send_ms,
                    metrics.total_loop_ms,
                    metrics.speed_error,
                    metrics.brake_output,
                ]
            )

    @property
    def avg_total_ms(self) -> float:
        if not self._window:
            return 0.0
        return sum(m.total_loop_ms for m in self._window) / len(self._window)

    @property
    def p95_total_ms(self) -> float:
        if not self._window:
            return 0.0
        sorted_vals = sorted(m.total_loop_ms for m in self._window)
        idx = max(0, int(len(sorted_vals) * 0.95) - 1)
        return sorted_vals[idx]

    @property
    def max_total_ms(self) -> float:
        if not self._window:
            return 0.0
        return max(m.total_loop_ms for m in self._window)

    @property
    def speed_error_avg(self) -> float:
        if not self._speed_errors:
            return 0.0
        return sum(self._speed_errors) / len(self._speed_errors)

    def to_dict(self) -> dict:
        return {
            "avg_total_ms": round(self.avg_total_ms, 2),
            "p95_total_ms": round(self.p95_total_ms, 2),
            "max_total_ms": round(self.max_total_ms, 2),
            "speed_error_avg": round(self.speed_error_avg, 2),
            "frame_count": len(self._window),
        }
