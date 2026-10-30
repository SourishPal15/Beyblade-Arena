from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from src import combat, config
from src.beyblade import Beyblade
from src.beyblade_data import BeybladeSpec
from src.utilities import Vec2, clamp, from_angle

if TYPE_CHECKING:
    from src.battle import Battle


class WorldEffect:
    kind = "effect"

    def __init__(self, owner: Beyblade) -> None:
        self.owner = owner
        self.alive = True
        self.age = 0.0

    def update(self, battle: "Battle", dt: float) -> None:
        self.age += dt


class Vortex(WorldEffect):
    kind = "vortex"

    def __init__(self, owner: Beyblade, center: Vec2, params: dict) -> None:
        super().__init__(owner)
        self.center = center
        self.params = params
        self.radius = float(params["radius"])
        self.duration = float(params["duration"])

    def contains(self, position: Vec2) -> bool:
        return (position - self.center).length() <= self.radius

    def update(self, battle: "Battle", dt: float) -> None:
        super().update(battle, dt)
        if self.age >= self.duration or not self.owner.alive:
            self.alive = False
            return
        p = self.params
        for target in battle.opponents_of(self.owner):
            if not self.contains(target.pos):
                continue
            toward = (self.center - target.pos).normalized()
            target.ext_accel = target.ext_accel + toward * (float(p["pull"]) / target.mass)
            combat.apply_damage(battle, target, float(p["hp_rate"]) * target.max_hp * dt, self.owner, "vortex")
            target.stamina = max(0.0, target.stamina - float(p["stamina_rate"]) * target.max_stamina * dt)
            target.add_effect("vortex_slow", 0.12, speed_mult=float(p["slow"]))


class Thorn(WorldEffect):
    kind = "thorn"

    def __init__(self, owner: Beyblade, pos: Vec2, vel: Vec2, params: dict, group: Set[int]) -> None:
        super().__init__(owner)
        self.pos = pos
        self.vel = vel
        self.params = params
        self.group = group
        self.travelled = 0.0
        self.lifetime = float(params["duration"])
        self.radius = float(params["thorn_radius"])

    def update(self, battle: "Battle", dt: float) -> None:
        super().update(battle, dt)
        if self.age >= self.lifetime or not self.owner.alive:
            self.alive = False
            return
        step = self.vel * dt
        self.pos = self.pos + step
        self.travelled += step.length()
        limit = battle.stadium.radius - self.radius
        distance = self.pos.length()
        if distance > limit and distance > 1e-9:
            normal = self.pos * (1.0 / distance)
            self.pos = normal * limit
            self.vel = self.vel - normal * (2.0 * self.vel.dot(normal))
        for target in battle.opponents_of(self.owner):
            if target.uid in self.group:
                continue
            if (target.pos - self.pos).length() <= target.radius + self.radius:
                self.hit(battle, target)
                break

    def hit(self, battle: "Battle", target: Beyblade) -> None:
        self.group.add(target.uid)
        pre_defence = thorn_damage(self.params, self.travelled)
        scaled = min(pre_defence * combat.defence_factor(target.defence), float(self.params["max_damage"]))
        actual = combat.apply_damage(battle, target, scaled, self.owner, "thorn")
        target.add_effect("thorn_slow", float(self.params["slow_duration"]), speed_mult=float(self.params["slow"]))
        healed = combat.heal(self.owner, float(self.params["lifesteal"]) * actual)
        battle.emit("thorn_hit", self.pos.copy(), target=target.uid, damage=actual, healed=healed)
        self.alive = False


def thorn_damage(params: dict, distance: float) -> float:
    travel_factor = clamp(distance / float(params["ref_distance"]), 0.0, 1.0)
    return float(params["base_damage"]) * (1.0 + float(params["max_bonus"]) * travel_factor)


class StoneWall(WorldEffect):
    kind = "stone_wall"

    def __init__(self, owner: Beyblade, start: Vec2, direction: Tuple[int, int], length: float, params: dict, group: dict) -> None:
        super().__init__(owner)
        self.start = start
        self.direction = direction
        self.length = length
        self.params = params
        self.group = group
        self.thickness = float(params["wall_thickness"])
        self.duration = float(params["duration"])
        self.grow_time = float(params["grow_time"])
        self.hit_targets: Set[int] = set()

    @property
    def current_length(self) -> float:
        return self.length * clamp(self.age / self.grow_time, 0.0, 1.0)

    def rect(self) -> Tuple[float, float, float, float]:
        dx, dy = self.direction
        half = self.thickness / 2.0
        end_x = self.start.x + dx * self.current_length
        end_y = self.start.y + dy * self.current_length
        if dx != 0:
            left, right = sorted((self.start.x, end_x))
            return left, self.start.y - half, right, self.start.y + half
        top, bottom = sorted((self.start.y, end_y))
        return self.start.x - half, top, self.start.x + half, bottom

    def update(self, battle: "Battle", dt: float) -> None:
        super().update(battle, dt)
        if self.age >= self.duration:
            self.alive = False


class ThunderStrike(WorldEffect):
    kind = "thunder_strike"

    def __init__(self, owner: Beyblade, target: Beyblade, params: dict) -> None:
        super().__init__(owner)
        self.target = target
        self.params = params
        self.delay = float(params["strike_delay"])

    def update(self, battle: "Battle", dt: float) -> None:
        super().update(battle, dt)
        if self.age < self.delay:
            return
        self.alive = False
        owner, target = self.owner, self.target
        if not owner.alive or not target.alive or owner.team == target.team:
            return
        stolen = min(target.stamina * float(self.params["steal"]), owner.max_stamina - owner.stamina)
        stolen = max(0.0, stolen)
        target.stamina -= stolen
        owner.stamina += stolen
        damage = float(self.params["damage"]) * combat.defence_factor(target.defence) * 2.0
        combat.apply_damage(battle, target, damage, owner, "lightning")
        owner.add_effect("speed_boost", float(self.params["duration"]), speed_mult=float(self.params["speed_mult"]))
        battle.emit("strike", target.pos.copy(), attacker=owner.uid, target=target.uid, stolen=stolen)


class Gust(WorldEffect):
    kind = "gust"

    def __init__(self, owner: Beyblade, center: Vec2, radius: float, duration: float, direction: Vec2) -> None:
        super().__init__(owner)
        self.center = center
        self.radius = radius
        self.duration = duration
        self.direction = direction

    def update(self, battle: "Battle", dt: float) -> None:
        super().update(battle, dt)
        if self.age >= self.duration:
            self.alive = False


class Ability:
    def __init__(self, spec: BeybladeSpec) -> None:
        self.spec = spec
        self.params: dict = spec.ability

    def validate(self, battle: "Battle", caster: Beyblade) -> Tuple[bool, str]:
        return True, ""

    def activate(self, battle: "Battle", caster: Beyblade) -> None:
        raise NotImplementedError


class InfernalBreaker(Ability):
    def validate(self, battle, caster):
        if caster.charged:
            return False, "active"
        return True, ""

    def activate(self, battle, caster):
        p = self.params
        caster.add_effect(
            "charged", float(p["duration"]), attack_mult=float(p["attack_mult"]),
            speed_mult=float(p["speed_mult"]), cost_mult=float(p["cost_mult"]), drain_mult=float(p["drain_mult"]),
        )


class AbyssalVortex(Ability):
    def activate(self, battle, caster):
        p = self.params
        aim = battle.aim_direction(caster)
        center = caster.pos + aim * float(p["placement"])
        limit = battle.stadium.radius - 40.0
        if center.length() > limit:
            center = center.normalized() * limit
        battle.add_world_effect(Vortex(caster, center, p))


class Thornstorm(Ability):
    def activate(self, battle, caster):
        p = self.params
        aim = battle.aim_direction(caster)
        count = int(p["thorn_count"])
        spread = math.radians(float(p["spread_deg"]))
        group: Set[int] = set()
        for i in range(count):
            offset = 0.0 if count == 1 else -spread / 2.0 + spread * i / (count - 1)
            direction = aim.rotated(offset)
            start = caster.pos + direction * (caster.radius + 4.0)
            battle.add_world_effect(Thorn(caster, start, direction * float(p["speed"]), p, group))


class Earthshatter(Ability):
    def activate(self, battle, caster):
        p = self.params
        half = float(p["wall_thickness"]) / 2.0
        limit = battle.stadium.radius - half - 4.0
        group = {"broken": set()}
        for direction in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            d = Vec2(*direction)
            start = caster.pos + d * float(p["offset"])
            if start.length() >= limit:
                continue
            projection = start.dot(d)
            discriminant = projection * projection - start.length_sq() + limit * limit
            reach = -projection + math.sqrt(max(0.0, discriminant))
            length = min(float(p["wall_length"]), reach)
            if length < 24.0:
                continue
            battle.add_world_effect(StoneWall(caster, start, direction, length, p, group))


class Thunder(Ability):
    def validate(self, battle, caster):
        if battle.nearest_opponent(caster) is None:
            return False, "no_target"
        return True, ""

    def activate(self, battle, caster):
        target = battle.nearest_opponent(caster)
        battle.add_world_effect(ThunderStrike(caster, target, self.params))


class PhantomCyclone(Ability):
    def activate(self, battle, caster):
        p = self.params
        center = caster.pos.copy()
        radius = float(p["radius"])
        for target in battle.opponents_of(caster):
            offset = target.pos - center
            distance = offset.length()
            if distance > radius:
                continue
            normal = offset.normalized() if distance > 1e-6 else from_angle(battle.rng.uniform(0.0, math.tau))
            falloff = 1.0 - 0.5 * distance / radius
            impulse = float(p["force"]) * falloff / target.effective_mass
            if not target.frozen:
                target.vel = target.vel + normal * impulse
                target.cancel_recovery()
        direction = battle.aim_direction(caster)
        nearest = battle.nearest_opponent(caster)
        if caster.steer.is_zero(1e-3) and caster.aim_override is None and nearest is not None:
            direction = (caster.pos - nearest.pos).normalized()
        burst = float(p["burst_speed"])
        caster.vel = caster.vel + direction * burst
        caster.cancel_recovery()
        caster.add_effect("repositioning", float(p["burst_duration"]), limit=burst * 1.05)
        battle.add_world_effect(Gust(caster, center, radius, float(p["duration"]), direction))


class AbsoluteZero(Ability):
    def activate(self, battle, caster):
        p = self.params
        for target in battle.opponents_of(caster):
            if target.frozen:
                continue
            target.add_effect("frozen", float(p["freeze_duration"]), refresh=False, drain_mult=float(p["drain_mult"]))
            target.vel = Vec2()
            target.attack_window = 0.0
            target.dash_timer = 0.0
            target.pending.clear()
            target.cancel_recovery()
            battle.emit("freeze", target.pos.copy(), target=target.uid)


class VenomousTouch(Ability):
    def validate(self, battle, caster):
        if caster.venomous:
            return False, "active"
        return True, ""

    def activate(self, battle, caster):
        caster.add_effect("venomous", float(self.params["duration"]))


def apply_poison(battle: "Battle", venom: Beyblade, target: Beyblade) -> None:
    p = venom.spec.ability
    fresh = target.add_effect(
        "poison", float(p["poison_duration"]), drain_mult=float(p["poison_drain_mult"]),
        speed_mult=float(p["poison_slow"]), rate=float(p["poison_rate"]),
    )
    if fresh:
        battle.emit("poison_applied", target.pos.copy(), target=target.uid, source=venom.uid)


ABILITY_TYPES = {
    "infernal_breaker": InfernalBreaker,
    "abyssal_vortex": AbyssalVortex,
    "thornstorm": Thornstorm,
    "earthshatter": Earthshatter,
    "thunder": Thunder,
    "phantom_cyclone": PhantomCyclone,
    "absolute_zero": AbsoluteZero,
    "venomous_touch": VenomousTouch,
}


def create_ability(spec: BeybladeSpec) -> Ability:
    return ABILITY_TYPES[str(spec.ability["type"])](spec)
