from horizon6_autogear.shifting.output_device import CommandedState


class Arbiter:
    """Resolves throttle/brake conflicts between controllers.

    Safety-first: lowest-wins for throttle. During shift, TCS and corner
    control are suppressed — drivetrain is disconnected via clutch.
    """

    def resolve(self, driver_throttle: float, tcs_throttle: float,
                corner_throttle: float, corner_brake: float,
                shift_pending: bool) -> CommandedState:
        if shift_pending:
            return CommandedState(throttle=driver_throttle, brake=0.0)

        return CommandedState(
            throttle=min(driver_throttle, tcs_throttle, corner_throttle),
            brake=corner_brake,
        )
