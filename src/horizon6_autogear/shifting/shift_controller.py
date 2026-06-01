import time
import logging

import horizon6_autogear.config.config as constants
from horizon6_autogear.shifting.output_device import OutputDevice, SharedState


class ShiftController:
    """Determines when to shift and delegates execution to OutputDevice.

    Shift execution is submitted to threadPool with shift_pending guard
    to prevent double-shifts. Actual key/button presses go through the
    OutputDevice protocol.
    """

    def __init__(self, output_device: OutputDevice,
                 min_gear: int, max_gear: int,
                 drivetrain: int = 2, shift_factor: float = 1.0,
                 logger: logging.Logger = None):
        self.output_device = output_device
        self.min_gear = min_gear
        self.max_gear = max_gear
        self.drivetrain = drivetrain
        self.shift_factor = shift_factor
        self.shift_point = {}
        self.logger = logger or logging.getLogger(__name__)
        self.last_upshift = time.time()
        self.last_downshift = time.time()

    def should_shift(self, fdp) -> tuple[str, int] | None:
        """Decide whether to shift based on telemetry.

        Returns ('up', gear) or ('down', gear) or None.
        """
        gear = fdp.gear
        if not self.shift_point:
            return None
        if fdp.speed <= constants.SPEED_THRESHOLD:
            return None
        if gear < self.min_gear or gear > self.max_gear:
            return None

        slip = (fdp.tire_slip_ratio_RL + fdp.tire_slip_ratio_RR) / 2
        speed = fdp.speed * constants.MS_TO_KMH
        rpm = fdp.current_engine_rpm
        accel = fdp.accel

        if slip >= 1.0:
            return None

        if gear < self.max_gear and accel and gear in self.shift_point:
            target_rpm = self.shift_point[gear]['rpmo'] * self.shift_factor
            target_speed = self.shift_point[gear]['speed'] * self.shift_factor
            if rpm > target_rpm and speed > target_speed:
                return ('up', gear)

        if gear > self.min_gear:
            lower_gear = gear - 1
            if lower_gear not in self.shift_point:
                available = list(self.shift_point.keys())
                if not available:
                    return None
                lower_gear = min(available, key=lambda x: abs(x - (gear - 1)))
            target_down_speed = self.shift_point[lower_gear]['speed'] * self.shift_factor
            if speed < target_down_speed * constants.DOWNSHIFT_SPEED_FACTOR:
                if self.drivetrain == constants.DRIVETRAIN_RWD and gear < constants.RWD_LOW_GEAR_THRESHOLD:
                    return None
                return ('down', gear)

        return None

    def execute_shift(self, direction: str, gear: int, shared_state: SharedState) -> None:
        """Execute a shift in a worker thread. Always clears shift_pending."""
        try:
            if direction == 'up':
                self._do_up_shift(gear)
            elif direction == 'down':
                self._do_down_shift(gear)
        finally:
            shared_state.shift_pending.clear()

    def _do_up_shift(self, gear: int):
        cur = time.time()
        if gear < self.max_gear and cur - self.last_upshift >= constants.UP_SHIFT_COOL_DOWN:
            self.logger.info(f'[ShiftController] up shift: {gear} -> {gear + 1}')
            self.output_device.execute_shift('up')
            self.last_upshift = cur

    def _do_down_shift(self, gear: int):
        cur = time.time()
        if gear > self.min_gear and cur - self.last_downshift >= constants.DOWN_SHIFT_COOL_DOWN:
            self.logger.info(f'[ShiftController] down shift: {gear} -> {gear - 1}')
            self.output_device.execute_shift('down')
            self.last_downshift = cur
