from __future__ import annotations

from src.config import ACTION_COST_FRACTION, PASSIVE_DRAIN_RATE, RECOVERY_RATE
from src.utilities import clamp


def action_cost(max_stamina: float, action: str, multiplier: float = 1.0) -> float:
    return max(0.0, max_stamina * ACTION_COST_FRACTION[action] * multiplier)


def drain_per_second(max_stamina: float, multiplier: float = 1.0) -> float:
    return max_stamina * PASSIVE_DRAIN_RATE * multiplier


def apply_drain(stamina: float, max_stamina: float, multiplier: float, dt: float) -> float:
    return clamp(stamina - drain_per_second(max_stamina, multiplier) * dt, 0.0, max_stamina)


def apply_recovery(stamina: float, max_stamina: float, dt: float) -> float:
    return clamp(stamina + max_stamina * RECOVERY_RATE * dt, 0.0, max_stamina)
