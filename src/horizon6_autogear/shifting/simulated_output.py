import time


class SimulatedOutput:
    def __init__(self):
        self.log: list[tuple[float, str, float | str]] = []

    def set_analog(self, channel: str, value: float) -> None:
        self.log.append((time.monotonic(), channel, value))

    def execute_shift(self, direction: str) -> None:
        self.log.append((time.monotonic(), 'shift', direction))

    def release_all(self) -> None:
        pass

    def clear(self) -> None:
        self.log.clear()
