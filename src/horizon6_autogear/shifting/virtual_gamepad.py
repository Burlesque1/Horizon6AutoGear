import sys
import time

import horizon6_autogear.config.config as constants

if sys.platform == 'win32':
    try:
        import vigem_client
    except ImportError:
        vigem_client = None
else:
    vigem_client = None


class GamepadOutput:
    """OutputDevice implementation using ViGEmBus virtual Xbox controller.

    Provides analog throttle/brake output (0.0-1.0). Windows-only.
    Falls back gracefully if ViGEmBus driver or Python binding is missing.
    """

    def __init__(self):
        if vigem_client is None:
            raise RuntimeError(
                "GamepadOutput requires Windows with ViGEmBus installed. "
                "Install vigem-client: pip install vigem-client"
            )
        self._client = vigem_client.ViGEmBusClient()
        self._controller = self._client.create_x360_controller()
        self._controller.connect()
        self._throttle_value = 0.0
        self._brake_value = 0.0
        self._shifting = False

    @property
    def shifting(self) -> bool:
        return self._shifting

    def set_analog(self, channel: str, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if channel == 'throttle':
            if value != self._throttle_value:
                self._controller.set_axis_value(
                    vigem_client.X360_AXIS.RT, int(value * 255)
                )
                self._throttle_value = value
        elif channel == 'brake':
            if value != self._brake_value:
                self._controller.set_axis_value(
                    vigem_client.X360_AXIS.LT, int(value * 255)
                )
                self._brake_value = value
        elif channel == 'steer':
            pass

    def execute_shift(self, direction: str) -> None:
        self._shifting = True
        try:
            if direction == 'up':
                self._controller.press_button(vigem_client.X360_BUTTON.LEFT_SHOULDER)
                time.sleep(constants.DELAY_CLUTCH_TO_SHIFT)
                self._controller.press_button(vigem_client.X360_BUTTON.B)
                time.sleep(constants.KEY_PRESS_DURATION)
                self._controller.release_button(vigem_client.X360_BUTTON.B)
                time.sleep(constants.DELAY_SHIFT_TO_CLUTCH)
                self._controller.release_button(vigem_client.X360_BUTTON.LEFT_SHOULDER)
            elif direction == 'down':
                self._controller.press_button(vigem_client.X360_BUTTON.LEFT_SHOULDER)
                time.sleep(constants.DELAY_CLUTCH_TO_SHIFT)
                self._controller.press_button(vigem_client.X360_BUTTON.A)
                time.sleep(constants.KEY_PRESS_DURATION)
                self._controller.release_button(vigem_client.X360_BUTTON.A)
                time.sleep(constants.DELAY_SHIFT_TO_CLUTCH)
                self._controller.release_button(vigem_client.X360_BUTTON.LEFT_SHOULDER)
        finally:
            self._shifting = False

    def release_all(self) -> None:
        self.set_analog('throttle', 0.0)
        self.set_analog('brake', 0.0)

    @staticmethod
    def is_available() -> bool:
        return vigem_client is not None
