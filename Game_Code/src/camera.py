from __future__ import annotations

import random
from typing import Tuple

from src import config
from src.utilities import Vec2


class Camera:
    def __init__(self, size: Tuple[int, int], world_radius: float, top_margin: int = 84, bottom_margin: int = 104) -> None:
        self.top_margin = top_margin
        self.bottom_margin = bottom_margin
        self._rng = random.Random(7)
        self.shake_magnitude = 0.0
        self.offset = (0.0, 0.0)
        self.configure(size, world_radius)

    def configure(self, size: Tuple[int, int], world_radius: float) -> None:
        self.size = size
        self.world_radius = world_radius
        width, height = size
        usable_h = max(100, height - self.top_margin - self.bottom_margin)
        usable_w = max(100, width - 40)
        outer = world_radius + config.STADIUM_RIM_WIDTH + 6
        self.scale = min(usable_w, usable_h) / (2.0 * outer)
        self.center = (width / 2.0, self.top_margin + usable_h / 2.0)

    def to_screen_xy(self, x: float, y: float) -> Tuple[int, int]:
        return (
            int(self.center[0] + self.offset[0] + x * self.scale),
            int(self.center[1] + self.offset[1] + y * self.scale),
        )

    def to_screen(self, pos: Vec2) -> Tuple[int, int]:
        return self.to_screen_xy(pos.x, pos.y)

    def to_world(self, sx: float, sy: float) -> Vec2:
        return Vec2((sx - self.center[0] - self.offset[0]) / self.scale, (sy - self.center[1] - self.offset[1]) / self.scale)

    def length(self, units: float) -> float:
        return units * self.scale

    def add_shake(self, amount: float) -> None:
        self.shake_magnitude = min(config.SHAKE_MAX, self.shake_magnitude + amount)

    def update(self, dt: float) -> None:
        if self.shake_magnitude < 0.2:
            self.shake_magnitude = 0.0
            self.offset = (0.0, 0.0)
            return
        self.offset = (
            self._rng.uniform(-1.0, 1.0) * self.shake_magnitude,
            self._rng.uniform(-1.0, 1.0) * self.shake_magnitude,
        )
        self.shake_magnitude *= max(0.0, 1.0 - 9.0 * dt)
