from typing import Optional

from horizon6_autogear.shifting.output_device import CommandedState


class Arbiter:
    """Resolves throttle/brake conflicts between controllers.

    Safety-first: lowest-wins for throttle. During shift, TCS and corner
    control are suppressed — drivetrain is disconnected via clutch.
    """

    def resolve(self, driver_throttle: float, tcs_throttle: float,
                corner_throttle: float, corner_brake: float,
                shift_pending: bool,
                semi_auto_brake: float = 0.0,
                semi_auto_throttle_override: Optional[float] = None) -> CommandedState:
        if shift_pending:
            return CommandedState(throttle=driver_throttle, brake=0.0)

        brake = max(corner_brake, semi_auto_brake)

        if semi_auto_throttle_override is not None:
            throttle = min(semi_auto_throttle_override, tcs_throttle)
        else:
            throttle = min(driver_throttle, tcs_throttle, corner_throttle)

        return CommandedState(throttle=throttle, brake=brake)
