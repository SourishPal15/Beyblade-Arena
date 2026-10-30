from __future__ import annotations

import math
from typing import Tuple

from src import config
from src.beyblade import Beyblade
from src.utilities import Vec2, clamp, wrap_angle


def steering_vector(b: Beyblade, direction: Vec2, magnitude: float) -> Vec2:
    speed = b.vel.length()
    if speed < 5.0:
        return direction * magnitude
    vel_dir = b.vel * (1.0 / speed)
    parallel = direction.dot(vel_dir)
    lateral = direction - vel_dir * parallel
    return (vel_dir * parallel + lateral * b.turn) * magnitude


def update_spin(b: Beyblade, dt: float) -> None:
    rate = config.SPIN_DECAY
    if b.stamina <= 0.0:
        rate *= 1.4
    if b.recovering:
        rate *= 0.5
    b.spin = max(0.0, b.spin * math.exp(-rate * dt))
    b.angular_velocity = b.spin * b.spin_rate * b.spin_dir * config.SPIN_VISUAL_RATE
    b.angle = wrap_angle(b.angle + b.angular_velocity * dt)


def spin_visual_only(b: Beyblade, dt: float) -> None:
    b.angular_velocity = b.spin * b.spin_rate * b.spin_dir * config.SPIN_VISUAL_RATE
    b.angle = wrap_angle(b.angle + b.angular_velocity * dt)


def integrate(b: Beyblade, dt: float) -> None:
    if not b.alive:
        return
    if b.frozen:
        b.vel = Vec2()
        b.ext_accel = Vec2()
        update_spin(b, dt)
        return
    accel = b.ext_accel
    if b.can_steer() and not b.steer.is_zero(1e-3):
        direction = b.steer.normalized()
        accel = accel + steering_vector(b, direction, b.steering_acceleration())
    b.vel = b.vel + accel * dt
    drag = config.BASE_DRAG * b.friction
    if b.recovering:
        drag += config.RECOVERY_DAMPING
    b.vel = b.vel * math.exp(-drag * dt)
    speed = b.vel.length()
    limit = b.speed_limit()
    if speed > limit:
        reduced = limit + (speed - limit) * math.exp(-config.OVERSPEED_DECAY * dt)
        b.vel = b.vel * (reduced / speed)
        speed = reduced
    if speed > config.MAX_ABSOLUTE_SPEED:
        b.vel = b.vel * (config.MAX_ABSOLUTE_SPEED / speed)
        speed = config.MAX_ABSOLUTE_SPEED
    b.pos = b.pos + b.vel * dt
    b.ext_accel = Vec2()
    if speed > 20.0:
        b.facing = b.vel.normalized()
    update_spin(b, dt)


def resolve_arena_wall(b: Beyblade, radius: float, center: Vec2 = None) -> float:
    origin = center or Vec2()
    offset = b.pos - origin
    distance = offset.length()
    limit = radius - b.radius
    if distance <= limit:
        return 0.0
    normal = offset * (1.0 / distance) if distance > 1e-9 else Vec2(1.0, 0.0)
    b.pos = origin + normal * limit
    normal_speed = b.vel.dot(normal)
    impact = 0.0
    if normal_speed > 0.0:
        b.vel = b.vel - normal * ((1.0 + config.WALL_RESTITUTION) * normal_speed)
        impact = normal_speed
        excess = max(0.0, impact - config.MIN_IMPACT_SPEED)
        b.spin = max(0.0, b.spin * (1.0 - clamp(config.SPIN_LOSS_WALL * excess, 0.0, 0.1)))
    return impact


def resolve_rect(b: Beyblade, left: float, top: float, right: float, bottom: float) -> Tuple[bool, float, Vec2]:
    closest_x = clamp(b.pos.x, left, right)
    closest_y = clamp(b.pos.y, top, bottom)
    dx = b.pos.x - closest_x
    dy = b.pos.y - closest_y
    distance_sq = dx * dx + dy * dy
    if distance_sq >= b.radius * b.radius:
        return False, 0.0, Vec2()
    if distance_sq > 1e-12:
        distance = math.sqrt(distance_sq)
        normal = Vec2(dx / distance, dy / distance)
        penetration = b.radius - distance
    else:
        gaps = (
            (b.pos.x - left, Vec2(-1.0, 0.0)),
            (right - b.pos.x, Vec2(1.0, 0.0)),
            (b.pos.y - top, Vec2(0.0, -1.0)),
            (bottom - b.pos.y, Vec2(0.0, 1.0)),
        )
        gap, normal = min(gaps, key=lambda item: item[0])
        penetration = gap + b.radius
    b.pos = b.pos + normal * penetration
    into = -b.vel.dot(normal)
    impact = 0.0
    if into > 0.0:
        b.vel = b.vel + normal * ((1.0 + config.WALL_RESTITUTION) * into)
        impact = into
    return True, impact, normal
