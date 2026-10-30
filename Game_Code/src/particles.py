from __future__ import annotations

import math
from typing import List, Tuple

from src import config
from src.utilities import Color, clamp

PRIORITY_DECOR = 1
PRIORITY_TRAIL = 2
PRIORITY_COMBAT = 3
PRIORITY_ABILITY = 4
PRIORITY_FLASH = 5


class Particle:
    __slots__ = (
        "x", "y", "vx", "vy", "ax", "ay", "life", "max_life", "size", "size_end",
        "color", "kind", "drag", "rotation", "spin", "priority",
    )

    def __init__(
        self, x: float, y: float, vx: float, vy: float, life: float, size: float, color: Color,
        kind: str = "dot", ax: float = 0.0, ay: float = 0.0, drag: float = 0.0, size_end: float = 0.0,
        rotation: float = 0.0, spin: float = 0.0, priority: int = PRIORITY_DECOR,
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.ax = ax
        self.ay = ay
        self.life = life
        self.max_life = max(life, 1e-6)
        self.size = size
        self.size_end = size_end
        self.color = color
        self.kind = kind
        self.drag = drag
        self.rotation = rotation
        self.spin = spin
        self.priority = priority

    @property
    def fade(self) -> float:
        return clamp(self.life / self.max_life, 0.0, 1.0)

    @property
    def current_size(self) -> float:
        t = 1.0 - self.fade
        return self.size + (self.size_end - self.size) * t


class ParticleSystem:
    def __init__(self, max_particles: int = config.MAX_PARTICLES) -> None:
        self.max_particles = max_particles
        self.particles: List[Particle] = []

    def __len__(self) -> int:
        return len(self.particles)

    def clear(self) -> None:
        self.particles.clear()

    def emit(self, particle: Particle) -> bool:
        if len(self.particles) >= self.max_particles:
            if particle.priority <= PRIORITY_TRAIL:
                return False
            for index, existing in enumerate(self.particles):
                if existing.priority < particle.priority:
                    self.particles[index] = particle
                    return True
            return False
        self.particles.append(particle)
        return True

    def update(self, dt: float) -> None:
        alive: List[Particle] = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0.0:
                continue
            if p.drag > 0.0:
                damping = math.exp(-p.drag * dt)
                p.vx *= damping
                p.vy *= damping
            p.vx += p.ax * dt
            p.vy += p.ay * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rotation += p.spin * dt
            alive.append(p)
        self.particles = alive


def fade_color(color: Color, amount: float) -> Color:
    return (int(color[0] * amount), int(color[1] * amount), int(color[2] * amount))


def draw_particles(surface, camera, system: ParticleSystem) -> None:
    import pygame

    scale = camera.scale
    for p in system.particles:
        sx, sy = camera.to_screen_xy(p.x, p.y)
        fade = p.fade
        color = fade_color(p.color, fade)
        size = max(1.0, p.current_size * scale)
        if p.kind == "ring":
            width = max(1, int(2 * scale * max(0.4, fade)))
            pygame.draw.circle(surface, color, (sx, sy), int(size), width)
        elif p.kind == "spark":
            tail = (sx - int(p.vx * 0.035 * scale), sy - int(p.vy * 0.035 * scale))
            pygame.draw.line(surface, color, (sx, sy), tail, max(1, int(size * 0.6)))
        elif p.kind == "shard":
            points = [
                (sx + math.cos(p.rotation + k * math.pi / 2.0) * size * (1.0 if k % 2 == 0 else 0.45),
                 sy + math.sin(p.rotation + k * math.pi / 2.0) * size * (1.0 if k % 2 == 0 else 0.45))
                for k in range(4)
            ]
            pygame.draw.polygon(surface, color, points)
        else:
            pygame.draw.circle(surface, color, (sx, sy), max(1, int(size)))
