import time


class SimulatedOutput:
    def __init__(self):
        self.log: list[tuple[float, str, float | str]] = []
        self.analog_log: list[tuple[float, str, float]] = []
        self.shift_log: list[tuple[float, str]] = []
        self._last_values: dict[str, float] = {}

    def set_analog(self, channel: str, value: float) -> None:
        self.log.append((time.monotonic(), channel, value))
        self.analog_log.append((time.monotonic(), channel, value))
        self._last_values[channel] = value

    def execute_shift(self, direction: str) -> None:
        self.log.append((time.monotonic(), 'shift', direction))
        self.shift_log.append((time.monotonic(), direction))

    def release_all(self) -> None:
        self.log.append((time.monotonic(), 'release_all', None))

    def clear(self) -> None:
        self.log.clear()
        self.analog_log.clear()
        self.shift_log.clear()
        self._last_values.clear()

    @property
    def last_throttle(self) -> float:
        return self._last_values.get('throttle', 0.0)

    @property
    def last_brake(self) -> float:
        return self._last_values.get('brake', 0.0)

    @property
    def last_steer(self) -> float:
        return self._last_values.get('steer', 0.0)

    def get_analog_snapshot(self) -> dict[str, float]:
        return dict(self._last_values)
