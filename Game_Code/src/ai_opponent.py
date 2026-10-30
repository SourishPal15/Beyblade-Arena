from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from src import config
from src.beyblade import Beyblade
from src.utilities import Vec2, clamp, from_angle

if TYPE_CHECKING:
    from src.battle import Battle


@dataclass(frozen=True)
class AIProfile:
    interval: Tuple[float, float]
    aim_error: float
    prediction: float
    mistake_chance: float
    attack_chance: float
    ability_chance: float
    dash_chance: float
    recover_below: float
    recover_until: float
    restore_below: float
    wall_margin: float
    escape_chance: float
    coordinate: bool
    launch_delay: Tuple[float, float]
    launch_power: Tuple[float, float]
    launch_aim_error: float
    aim_at_opponent: bool


PROFILES = {
    "Easy": AIProfile(config.AI_INTERVALS["Easy"], 0.45, 0.0, 0.25, 0.45, 0.45, 0.15, 0.25, 0.80, 0.25, 45.0, 0.60, False, (0.50, 1.00), (0.45, 0.85), math.radians(25.0), False),
    "Medium": AIProfile(config.AI_INTERVALS["Medium"], 0.18, 0.25, 0.10, 0.75, 0.75, 0.40, 0.35, 0.90, 0.35, 70.0, 0.90, False, (0.30, 0.60), (0.60, 0.82), math.radians(10.0), True),
    "Hard": AIProfile(config.AI_INTERVALS["Hard"], 0.05, 0.45, 0.02, 0.95, 0.95, 0.65, 0.45, 0.97, 0.45, 95.0, 1.00, True, (0.15, 0.35), (0.77, 0.83), math.radians(3.0), True),
}

SPECIAL_RANGE = {
    "infernal_breaker": 260.0,
    "abyssal_vortex": 190.0,
    "thornstorm": 380.0,
    "earthshatter": 200.0,
    "thunder": 1e9,
    "phantom_cyclone": 170.0,
    "absolute_zero": 400.0,
    "venomous_touch": 220.0,
}


class AIController:
    def __init__(self, beyblade: Beyblade, difficulty: str, rng: random.Random) -> None:
        self.b = beyblade
        self.difficulty = difficulty
        self.profile = PROFILES[difficulty]
        self.rng = rng
        self.reset()

    def reset(self) -> None:
        self.timer = self.rng.uniform(0.0, self.profile.interval[1])
        self.mode = "attack"
        self.target_uid: Optional[int] = None
        self.target_lock = 0.0
        self.target_pos = Vec2()
        self.flee_from = Vec2()
        self.aim_offset = 0.0
        self.wander = Vec2(1.0, 0.0)
        self.recover = False
        self.b.aim_override = None
        self.launch_clock = 0.0
        self.launch_delay = self.rng.uniform(*self.profile.launch_delay)
        self.launch_target = self.rng.uniform(*self.profile.launch_power)
        self.launch_aim: Optional[float] = None

    def update(self, battle: "Battle", dt: float) -> None:
        b = self.b
        if not b.alive or not battle.combat_enabled:
            return
        if b.frozen:
            battle.set_input(b, Vec2(), False)
            return
        self.timer -= dt
        self.target_lock -= dt
        if self.timer <= 0.0:
            self._decide(battle)
            self.timer = self.rng.uniform(*self.profile.interval)
        battle.set_input(b, self._movement(battle), self.recover)

    def _plan_launch_aim(self, battle: "Battle") -> float:
        launcher = battle.launchers[self.b.uid]
        p = self.profile
        if p.aim_at_opponent:
            opponents = battle.opponents_of(self.b)
            if opponents:
                nearest = min(opponents, key=lambda o: (o.pos - self.b.pos).length_sq())
                offset = (nearest.pos - self.b.pos).angle() - launcher.base_angle
                offset = (offset + math.pi) % math.tau - math.pi
                return clamp(offset + self.rng.gauss(0.0, p.launch_aim_error), -config.LAUNCH_ANGLE_MAX, config.LAUNCH_ANGLE_MAX)
        limit = math.radians(35.0)
        return self.rng.uniform(-limit, limit) + self.rng.gauss(0.0, p.launch_aim_error * 0.3)

    def update_launch(self, battle: "Battle", dt: float) -> None:
        launcher = battle.launchers[self.b.uid]
        if launcher.released:
            return
        if self.launch_aim is None:
            self.launch_aim = self._plan_launch_aim(battle)
        self.launch_clock += dt
        diff = self.launch_aim - launcher.aim
        aim_input = 0.0
        if abs(diff) > math.radians(1.5):
            aim_input = 1.0 if diff > 0 else -1.0
        hold = False
        if self.launch_clock >= self.launch_delay:
            finished = launcher.state == "charging" and launcher.power >= self.launch_target
            hold = not finished
        battle.set_launch_input(self.b, hold, aim_input)

    def _decide(self, battle: "Battle") -> None:
        b, p, rng = self.b, self.profile, self.rng
        opponents = battle.opponents_of(b)
        self.recover = False
        if not opponents:
            self.mode = "idle"
            return
        vortex = battle.hostile_vortex_at(b)
        if vortex is not None and rng.random() < p.escape_chance:
            self.mode = "escape"
            self.flee_from = vortex.center
            if p.dash_chance > 0.3 and battle.can_perform(b, "dash")[0]:
                battle.request_action(b, "dash")
            return
        target = self._pick_target(battle, opponents)
        distance = (target.pos - b.pos).length()
        nearest = min((o.pos - b.pos).length() for o in opponents)
        noise = rng.gauss(0.0, p.aim_error * 25.0)
        self.target_pos = target.pos + target.vel * p.prediction + Vec2(noise, -noise)
        self.aim_offset = rng.gauss(0.0, p.aim_error)
        direction = self.target_pos - b.pos
        b.aim_override = direction.normalized() if not direction.is_zero() else None

        if rng.random() < p.mistake_chance:
            self.mode = "wander"
            self.wander = from_angle(rng.uniform(0.0, math.tau))
            return
        if b.hp_ratio < p.restore_below and battle.can_perform(b, "restore")[0]:
            battle.request_action(b, "restore")
        resting = self.mode == "recover" and b.stamina_ratio < p.recover_until
        if (b.stamina_ratio < p.recover_below or resting) and nearest > 170.0 and battle.can_perform(b, "recover")[0]:
            self.mode = "recover"
            self.recover = True
            return
        if b.hp_ratio < 0.25 and p.dash_chance > 0.3 and not battle.can_perform(b, "restore")[0] and nearest < 220.0:
            self.mode = "retreat"
            if b.stamina_ratio > 0.4 and battle.can_perform(b, "dash")[0] and rng.random() < p.dash_chance:
                battle.request_action(b, "dash")
            return
        self.mode = "attack"
        reach = b.radius + target.radius + config.ATTACK_REACH + 25.0
        if distance < reach and rng.random() < p.attack_chance and battle.can_perform(b, "attack")[0]:
            battle.request_action(b, "attack")
        elif distance > 220.0 and b.stamina_ratio > 0.55 and rng.random() < p.dash_chance and battle.can_perform(b, "dash")[0]:
            battle.request_action(b, "dash")
        self._consider_special(battle, target, distance)

    def _consider_special(self, battle: "Battle", target: Beyblade, distance: float) -> None:
        b, p = self.b, self.profile
        spec_type = str(b.spec.ability["type"])
        if distance > SPECIAL_RANGE[spec_type]:
            return
        if spec_type == "phantom_cyclone" and b.hp_ratio >= 0.5:
            return
        if battle.team_mode and p.coordinate and battle.time - battle.team_last_special.get(b.team, -99.0) < 2.5:
            return
        if self.rng.random() > p.ability_chance or not battle.can_perform(b, "special")[0]:
            return
        if spec_type == "phantom_cyclone":
            b.aim_override = (b.pos - target.pos).normalized()
        battle.request_action(b, "special")

    def _pick_target(self, battle: "Battle", opponents: List[Beyblade]) -> Beyblade:
        if self.target_lock > 0.0:
            for o in opponents:
                if o.uid == self.target_uid:
                    return o

        def score(o: Beyblade) -> float:
            value = (o.pos - self.b.pos).length() + 120.0 * o.hp_ratio
            if o.frozen:
                value -= 50.0
            return value

        chosen = min(opponents, key=score)
        self.target_uid = chosen.uid
        self.target_lock = 1.2
        return chosen

    def _movement(self, battle: "Battle") -> Vec2:
        b, p = self.b, self.profile
        base = Vec2()
        if self.mode == "escape":
            base = (b.pos - self.flee_from).normalized()
            if base.is_zero():
                base = from_angle(self.rng.uniform(0.0, math.tau))
        elif self.mode == "retreat":
            base = (b.pos - self.target_pos).normalized()
        elif self.mode == "wander":
            base = self.wander
        elif self.mode == "attack":
            goal = self.target_pos
            if battle.team_mode and p.coordinate and (goal - b.pos).length() > 170.0:
                allies = sorted([b.uid] + [a.uid for a in battle.allies_of(b)])
                side = 1.0 if allies.index(b.uid) % 2 == 0 else -1.0
                around = (b.pos - goal).normalized().rotated(side * 0.8)
                goal = goal + around * 130.0
            base = (goal - b.pos).normalized().rotated(self.aim_offset)
        elif self.mode == "recover":
            return Vec2()
        distance = b.pos.length()
        danger_start = battle.stadium.radius - b.radius - p.wall_margin
        if distance > danger_start:
            strength = clamp((distance - danger_start) / p.wall_margin, 0.0, 1.0) * 1.6
            base = base + (-b.pos).normalized() * strength
        return base.normalized() if not base.is_zero(1e-6) else Vec2()
