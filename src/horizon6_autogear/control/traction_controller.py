class TractionController:
    """TCS: Detects wheel slip and reduces throttle output.

    Monitors combined_slip on drive wheels based on drivetrain type.
    Returns 1.0 (no intervention) or a reduced throttle value.
    """

    def __init__(self, slip_threshold: float = 0.5,
                 min_speed: float = 5.0,
                 throttle_reduction: float = 0.3):
        self.slip_threshold = slip_threshold
        self.min_speed = min_speed
        self.throttle_reduction = throttle_reduction

    def compute(self, fdp) -> float:
        """Returns target throttle (0.0-1.0). 1.0 = no intervention."""
        if fdp.speed < self.min_speed:
            return 1.0

        if fdp.drivetrain_type == 1:    # RWD
            drive_slip = max(fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)
        elif fdp.drivetrain_type == 0:  # FWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR)
        else:                            # AWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                             fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)

        if drive_slip > self.slip_threshold:
            return self.throttle_reduction
        return 1.0
