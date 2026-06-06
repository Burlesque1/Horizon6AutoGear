"""Semi-automatic brake/throttle controller using reference profile data."""

from dataclasses import dataclass
from typing import Optional

import horizon6_autogear.config.config as constants
from horizon6_autogear.control.pid_controller import PIDController


ANTICIPATION_DISTANCES = {
    'heavy': constants.SEMI_AUTO_BRAKE_ANTICIPATION_HEAVY,
    'medium': constants.SEMI_AUTO_BRAKE_ANTICIPATION_MEDIUM,
    'light': constants.SEMI_AUTO_BRAKE_ANTICIPATION_LIGHT,
}

BRAKE_RELEASE_HYSTERESIS = constants.BRAKE_RELEASE_HYSTERESIS


@dataclass
class SemiAutoDecision:
    brake_force: float = 0.0
    throttle_override: Optional[float] = None
    should_shift: Optional[tuple] = None
    brake_zone_active: bool = False


class SemiAutoController:
    def __init__(self, pid_controller: PIDController):
        self.pid = pid_controller

    def compute(self, fdp, ref_data: dict) -> SemiAutoDecision:
        if ref_data is None:
            return SemiAutoDecision()

        next_bp = ref_data.get('next_brake_point')
        if next_bp is None:
            return SemiAutoDecision()

        entry_speed = next_bp.get('entry_speed', 0.0)
        if entry_speed <= 0:
            return SemiAutoDecision()

        current_speed = fdp.speed
        distance_ahead = next_bp['distance']
        severity = next_bp.get('severity', 'medium')
        anticipation = ANTICIPATION_DISTANCES.get(severity, 60.0)

        if distance_ahead > anticipation:
            return SemiAutoDecision()

        if current_speed <= entry_speed * BRAKE_RELEASE_HYSTERESIS:
            return SemiAutoDecision()

        speed_error = current_speed - entry_speed
        dt = 1.0 / 60.0
        pid_brake = self.pid.compute(speed_error, dt)

        proximity_ratio = 1.0 - (distance_ahead / anticipation)
        severity_scale = {'heavy': 0.6, 'medium': 0.4, 'light': 0.2}.get(severity, 0.3)
        proximity_brake = proximity_ratio * severity_scale

        brake_force = max(pid_brake, proximity_brake)

        throttle_override = None
        if ref_data.get('throttle', 1.0) < 0.1 and distance_ahead < anticipation:
            throttle_override = 0.0

        should_shift = None
        gear_suggestion = ref_data.get('gear_suggestion')
        if gear_suggestion:
            should_shift = (gear_suggestion,)

        return SemiAutoDecision(
            brake_force=brake_force,
            throttle_override=throttle_override,
            should_shift=should_shift,
            brake_zone_active=True,
        )
