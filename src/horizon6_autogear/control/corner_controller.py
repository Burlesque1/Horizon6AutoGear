class CornerController:
    """Corner throttle/brake auto-control.

    Reduces throttle when steering input exceeds threshold AND tire slip
    indicates the car is at or beyond grip limit in a corner.
    """

    def __init__(self, steer_threshold: float = 0.3,
                 slip_limit: float = 0.4,
                 throttle_reduction: float = 0.7):
        self.steer_threshold = steer_threshold
        self.slip_limit = slip_limit
        self.throttle_reduction = throttle_reduction

    def compute(self, fdp) -> tuple[float, float]:
        """Returns (corner_throttle, corner_brake)."""
        if abs(fdp.steer) < self.steer_threshold:
            return 1.0, 0.0

        max_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                       fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)

        if max_slip > self.slip_limit:
            return self.throttle_reduction, 0.0

        return 1.0, 0.0
