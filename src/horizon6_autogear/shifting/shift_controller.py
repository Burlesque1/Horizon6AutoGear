import time
import logging

import horizon6_autogear.config.config as constants
import horizon6_autogear.shifting.keyboard as keyboard_helper
from horizon6_autogear.shifting.output_device import SharedState


class ShiftController:
    """Determines when to shift and executes shifts asynchronously.

    Extracts shift decision logic from forza.py shifting() into a standalone
    controller. Shift execution is submitted to threadPool with shift_pending
    guard to prevent double-shifts.
    """

    def __init__(self, min_gear: int, max_gear: int,
                 clutch_key: str, upshift_key: str, downshift_key: str,
                 drivetrain: int = 2, clutch_enabled: bool = False,
                 shift_factor: float = 1.0, farming: bool = False,
                 logger: logging.Logger = None):
        self.min_gear = min_gear
        self.max_gear = max_gear
        self.clutch_key = clutch_key
        self.upshift_key = upshift_key
        self.downshift_key = downshift_key
        self.drivetrain = drivetrain
        self.clutch_enabled = clutch_enabled
        self.shift_factor = shift_factor
        self.farming = farming
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
            if self.clutch_enabled:
                keyboard_helper.pressdown_str(self.clutch_key)
            time.sleep(constants.DELAY_CLUTCH_TO_SHIFT)
            keyboard_helper.press_str(self.upshift_key)
            time.sleep(constants.DELAY_SHIFT_TO_CLUTCH)
            if self.clutch_enabled:
                keyboard_helper.release_str(self.clutch_key)
            self.last_upshift = cur

    def _do_down_shift(self, gear: int):
        cur = time.time()
        if gear > self.min_gear and cur - self.last_downshift >= constants.DOWN_SHIFT_COOL_DOWN:
            self.logger.info(f'[ShiftController] down shift: {gear} -> {gear - 1}')
            if self.clutch_enabled:
                keyboard_helper.pressdown_str(self.clutch_key)
                if not self.farming:
                    keyboard_helper.pressdown_str(constants.ACCELERATION)
                    time.sleep(constants.BLIP_THROTTLE_DURATION)
                    keyboard_helper.release_str(constants.ACCELERATION)
            time.sleep(constants.DELAY_CLUTCH_TO_SHIFT)
            keyboard_helper.press_str(self.downshift_key)
            time.sleep(constants.DELAY_SHIFT_TO_CLUTCH)
            if self.clutch_enabled:
                keyboard_helper.release_str(self.clutch_key)
            self.last_downshift = cur
