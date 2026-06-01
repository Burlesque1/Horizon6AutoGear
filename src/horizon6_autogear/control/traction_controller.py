class TractionController:
    """TCS: Detects wheel slip and reduces throttle output.

    Monitors combined_slip on drive wheels based on drivetrain type.
    Returns 1.0 (no intervention) or a reduced throttle value.
    Uses hysteresis to prevent oscillation at the threshold boundary.
    """

    def __init__(self, slip_threshold: float = 0.5,
                 min_speed: float = 5.0,
                 throttle_reduction: float = 0.3,
                 recovery_margin: float = 0.1):
        self.slip_threshold = slip_threshold
        self.min_speed = min_speed
        self.throttle_reduction = throttle_reduction
        self.recovery_threshold = slip_threshold - recovery_margin
        self._intervening = False

    def compute(self, fdp) -> float:
        """Returns target throttle (0.0-1.0). 1.0 = no intervention."""
        if fdp.speed < self.min_speed:
            self._intervening = False
            return 1.0

        if fdp.drivetrain_type == 1:    # RWD
            drive_slip = max(fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)
        elif fdp.drivetrain_type == 0:  # FWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR)
        else:                            # AWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                             fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)

        if drive_slip > self.slip_threshold:
            self._intervening = True
            return self.throttle_reduction

        if self._intervening and drive_slip > self.recovery_threshold:
            return self.throttle_reduction

        self._intervening = False
        return 1.0
