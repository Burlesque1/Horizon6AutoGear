from dataclasses import dataclass, field
from threading import Event
from typing import Protocol


@dataclass
class CommandedState:
    throttle: float = 1.0
    brake: float = 0.0


@dataclass
class SharedState:
    shift_pending: Event = field(default_factory=Event)


class OutputDevice(Protocol):
    def set_analog(self, channel: str, value: float) -> None:
        ...

    def execute_shift(self, direction: str) -> None:
        ...
