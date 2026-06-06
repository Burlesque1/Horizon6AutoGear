"""PID brake controller for speed regulation."""


class PIDController:
    """Standalone PID controller for brake force modulation.

    Sign convention:
        error = current_speed - reference_speed
        Positive error means car is too fast and needs braking.
        compute() returns positive brake output for positive error.

    Output is clamped to [0.0, 1.0] — negative brake force is not allowed.
    """

    def __init__(self, kp=0.5, ki=0.05, kd=0.1, integral_limit=2.0):
        self._kp = kp
        self._ki = ki
        self._kd = kd
        self._integral_limit = integral_limit
        self._integral = 0.0
        self._prev_error = 0.0

    def compute(self, error: float, dt: float) -> float:
        """Compute PID output for the given error and time step.

        Args:
            error: current_speed - reference_speed (positive = too fast).
            dt: Time step in seconds.

        Returns:
            Brake force in [0.0, 1.0].
        """
        # P term
        p_term = self._kp * error

        # I term with anti-windup clamping
        self._integral += error * dt
        self._integral = max(-self._integral_limit,
                             min(self._integral_limit, self._integral))
        i_term = self._ki * self._integral

        # D term
        if dt > 0.0:
            d_term = self._kd * (error - self._prev_error) / dt
        else:
            d_term = 0.0

        output = p_term + i_term + d_term
        self._prev_error = error

        return max(0.0, min(1.0, output))

    def reset(self):
        """Clear integral accumulator and previous error."""
        self._integral = 0.0
        self._prev_error = 0.0

    def update_gains(self, kp=None, ki=None, kd=None):
        """Update PID gains. Only provided values are changed."""
        if kp is not None:
            self._kp = kp
        if ki is not None:
            self._ki = ki
        if kd is not None:
            self._kd = kd
