from __future__ import annotations

import math
from typing import List

from src import config
from src.utilities import Vec2, from_angle


class Stadium:
    def __init__(self, name: str) -> None:
        if name not in config.STADIUM_RADII:
            raise ValueError(f"Unknown stadium size: {name}")
        self.name = name
        self.radius = config.STADIUM_RADII[name]
        self.rim_width = config.STADIUM_RIM_WIDTH
        self.center = Vec2()

    @property
    def outer_radius(self) -> float:
        return self.radius + self.rim_width

    def contains(self, position: Vec2, margin: float = 0.0) -> bool:
        return (position - self.center).length() <= self.radius - margin

    def spawn_positions(self, count: int) -> List[Vec2]:
        ring = self.radius * config.SPAWN_RING_FRACTION
        start = math.pi / 2.0
        return [self.center + from_angle(start + i * math.tau / count, ring) for i in range(count)]

    def launch_positions(self, count: int) -> List[Vec2]:
        ring = self.radius - config.LAUNCH_EDGE_OFFSET
        start = math.pi / 2.0
        return [self.center + from_angle(start + i * math.tau / count, ring) for i in range(count)]
