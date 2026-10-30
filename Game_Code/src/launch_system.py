from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from src import config
from src.beyblade_data import BeybladeSpec
from src.utilities import Vec2, clamp, from_angle

ATTACHING = "attaching"
WAITING = "waiting"
CHARGING = "charging"
RELEASED = "released"


@dataclass
class LaunchResult:
    velocity: Vec2
    spin: float
    power: float
    quality: str
    angle: float


def charge_time_for(spec: BeybladeSpec) -> float:
    return config.CHARGE_TIME / max(0.1, spec.launch.get("charge_rate", 1.0))


def charge_power(held_time: float, spec: BeybladeSpec) -> float:
    return clamp(held_time / charge_time_for(spec), 0.0, 1.0)


def timing_quality(power: float) -> str:
    low, high = config.SWEET_SPOT
    if power < config.LAUNCH_POWER_FLOOR + 0.05:
        return "weak"
    if power > config.OVERCHARGE_THRESHOLD:
        return "overcharged"
    if low <= power <= high:
        return "perfect"
    return "good"


def launch_speed(spec: BeybladeSpec, power: float) -> float:
    base = spec.speed * config.SPEED_PER_STAT * spec.launch.get("speed", 1.0)
    fraction = config.LAUNCH_SPEED_FLOOR + (1.0 - config.LAUNCH_SPEED_FLOOR) * clamp(power, 0.0, 1.0)
    bonus = config.SWEET_SPOT_BONUS if timing_quality(power) == "perfect" else 1.0
    return base * fraction * bonus


def launch_spin(spec: BeybladeSpec, power: float) -> float:
    return clamp(0.85 + 0.15 * power * spec.launch.get("spin_boost", 1.0), 0.7, 1.0)


def clamp_aim(aim: float) -> float:
    return clamp(aim, -config.LAUNCH_ANGLE_MAX, config.LAUNCH_ANGLE_MAX)


def compute_launch(spec: BeybladeSpec, base_angle: float, aim: float, power: float, rng: random.Random) -> LaunchResult:
    power = clamp(power, 0.0, 1.0)
    quality = timing_quality(power)
    angle = base_angle + clamp_aim(aim)
    if quality == "overcharged":
        jitter = config.OVERCHARGE_JITTER / max(0.5, spec.launch.get("stability", 1.0))
        angle += rng.uniform(-jitter, jitter)
    velocity = from_angle(angle, launch_speed(spec, power))
    return LaunchResult(velocity, launch_spin(spec, power), power, quality, angle)


class Launcher:
    def __init__(self, spec: BeybladeSpec, base_angle: float, rng: Optional[random.Random] = None) -> None:
        self.spec = spec
        self.base_angle = base_angle
        self.rng = rng or random.Random()
        self.state = ATTACHING
        self.attach = 0.0
        self.aim = 0.0
        self.power = 0.0
        self.charge_time = 0.0
        self.release_anim = 0.0
        self.result: Optional[LaunchResult] = None
        self.pending_release = False
        self._armed = False

    @property
    def released(self) -> bool:
        return self.state == RELEASED

    @property
    def attached(self) -> bool:
        return self.state != ATTACHING

    @property
    def direction_angle(self) -> float:
        return self.base_angle + clamp_aim(self.aim)

    @property
    def display_spin(self) -> float:
        return 0.1 + 0.4 * self.power

    @property
    def release_progress(self) -> float:
        return 1.0 - clamp(self.release_anim / config.RELEASE_ANIM_TIME, 0.0, 1.0)

    def update(self, dt: float, hold: bool, aim_input: float, can_charge: bool) -> List[str]:
        events: List[str] = []
        if self.release_anim > 0.0:
            self.release_anim = max(0.0, self.release_anim - dt)
        if self.state == ATTACHING:
            self.attach = min(1.0, self.attach + dt / config.ATTACH_TIME)
            if self.attach >= 1.0:
                self.state = WAITING
                events.append("attached")
            return events
        if self.state in (WAITING, CHARGING):
            self.aim = clamp_aim(self.aim + clamp(aim_input, -1.0, 1.0) * config.AIM_RATE * dt)
        if self.state == WAITING:
            if not hold:
                self._armed = True
            elif can_charge and self._armed:
                self.state = CHARGING
                self.charge_time = 0.0
                self.power = 0.0
                events.append("charge_start")
        elif self.state == CHARGING:
            self.charge_time += dt
            self.power = charge_power(self.charge_time, self.spec)
            if not hold:
                self._release()
                events.append("released")
        return events

    def force_release(self) -> bool:
        if self.state not in (WAITING, CHARGING):
            return False
        self.power = max(self.power, config.LAUNCH_POWER_FLOOR)
        self._release()
        return True

    def _release(self) -> None:
        self.result = compute_launch(self.spec, self.base_angle, self.aim, self.power, self.rng)
        self.state = RELEASED
        self.release_anim = config.RELEASE_ANIM_TIME
        self.pending_release = True

    def take_release(self) -> Optional[LaunchResult]:
        if not self.pending_release:
            return None
        self.pending_release = False
        return self.result
