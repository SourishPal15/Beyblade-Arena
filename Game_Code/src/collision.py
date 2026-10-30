from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from src import config
from src.beyblade import Beyblade
from src.utilities import Vec2, clamp


class ContactResult:
    __slots__ = ("a", "b", "closing", "normal", "point", "impact", "ram_ab", "ram_ba")

    def __init__(self, a: Beyblade, b: Beyblade, closing: float, normal: Vec2, point: Vec2) -> None:
        self.a = a
        self.b = b
        self.closing = closing
        self.normal = normal
        self.point = point
        self.impact = False
        self.ram_ab = 0.0
        self.ram_ba = 0.0


def overlapping(a: Beyblade, b: Beyblade) -> bool:
    reach = a.radius + b.radius
    dx = a.pos.x - b.pos.x
    dy = a.pos.y - b.pos.y
    return dx * dx + dy * dy < reach * reach


def resolve_pair(a: Beyblade, b: Beyblade) -> ContactResult:
    offset = b.pos - a.pos
    distance = offset.length()
    normal = offset * (1.0 / distance) if distance > 1e-9 else Vec2(1.0, 0.0)
    approach_a = max(0.0, a.vel.dot(normal))
    approach_b = max(0.0, -b.vel.dot(normal))
    closing = (a.vel - b.vel).dot(normal)
    point = a.pos + normal * a.radius
    result = ContactResult(a, b, closing, normal, point)
    result.ram_ab = approach_a
    result.ram_ba = approach_b

    inv_a = a.inverse_mass
    inv_b = b.inverse_mass
    inv_sum = inv_a + inv_b
    if inv_sum <= 0.0:
        return result

    if closing > 0.0:
        restitution = 0.5 * (a.spec.restitution + b.spec.restitution)
        impulse = (1.0 + restitution) * closing / inv_sum
        a.vel = a.vel - normal * (impulse * inv_a)
        b.vel = b.vel + normal * (impulse * inv_b)
        loss = clamp(config.SPIN_LOSS_COLLISION * max(0.0, closing - config.MIN_IMPACT_SPEED), 0.0, 0.1)
        a.spin = max(0.0, a.spin * (1.0 - loss))
        b.spin = max(0.0, b.spin * (1.0 - loss))

    overlap = a.radius + b.radius - distance
    if overlap > 0.0:
        a.pos = a.pos - normal * (overlap * inv_a / inv_sum)
        b.pos = b.pos + normal * (overlap * inv_b / inv_sum)
    return result


class ContactTracker:
    def __init__(self) -> None:
        self._impact_cooldown: Dict[Tuple[int, int], float] = {}
        self._ram_cooldown: Dict[Tuple[int, int], float] = {}

    def reset(self) -> None:
        self._impact_cooldown.clear()
        self._ram_cooldown.clear()

    def _decay(self, dt: float) -> None:
        for store in (self._impact_cooldown, self._ram_cooldown):
            for key in list(store):
                store[key] -= dt
                if store[key] <= 0.0:
                    del store[key]

    def process(self, beyblades: Sequence[Beyblade], dt: float) -> List[ContactResult]:
        self._decay(dt)
        results: List[ContactResult] = []
        count = len(beyblades)
        for i in range(count):
            a = beyblades[i]
            if not a.alive:
                continue
            for j in range(i + 1, count):
                b = beyblades[j]
                if not b.alive or not overlapping(a, b):
                    continue
                result = resolve_pair(a, b)
                key = (min(a.uid, b.uid), max(a.uid, b.uid))
                if result.closing >= config.MIN_IMPACT_SPEED and key not in self._impact_cooldown:
                    result.impact = True
                    self._impact_cooldown[key] = config.IMPACT_COOLDOWN
                if result.ram_ab < config.RAM_MIN_SPEED or (a.uid, b.uid) in self._ram_cooldown:
                    result.ram_ab = 0.0
                else:
                    self._ram_cooldown[(a.uid, b.uid)] = config.RAM_COOLDOWN
                if result.ram_ba < config.RAM_MIN_SPEED or (b.uid, a.uid) in self._ram_cooldown:
                    result.ram_ba = 0.0
                else:
                    self._ram_cooldown[(b.uid, a.uid)] = config.RAM_COOLDOWN
                results.append(result)
        return results
