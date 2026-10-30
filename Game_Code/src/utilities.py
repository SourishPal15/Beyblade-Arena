from __future__ import annotations

import math
from typing import Tuple

TAU = math.tau
Color = Tuple[int, int, int]


class Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)

    def copy(self) -> "Vec2":
        return Vec2(self.x, self.y)

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> "Vec2":
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __truediv__(self, k: float) -> "Vec2":
        return Vec2(self.x / k, self.y / k)

    def __neg__(self) -> "Vec2":
        return Vec2(-self.x, -self.y)

    def __iter__(self):
        yield self.x
        yield self.y

    def __repr__(self) -> str:
        return f"Vec2({self.x:.3f}, {self.y:.3f})"

    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.y * other.y

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def distance_to(self, other: "Vec2") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def normalized(self) -> "Vec2":
        length = self.length()
        if length < 1e-9:
            return Vec2()
        return Vec2(self.x / length, self.y / length)

    def clamp_length(self, max_length: float) -> "Vec2":
        length = self.length()
        if length <= max_length or length < 1e-9:
            return self.copy()
        return self * (max_length / length)

    def rotated(self, angle: float) -> "Vec2":
        c, s = math.cos(angle), math.sin(angle)
        return Vec2(self.x * c - self.y * s, self.x * s + self.y * c)

    def perp(self) -> "Vec2":
        return Vec2(-self.y, self.x)

    def angle(self) -> float:
        return math.atan2(self.y, self.x)

    def is_zero(self, eps: float = 1e-9) -> bool:
        return self.length_sq() < eps * eps


def from_angle(angle: float, length: float = 1.0) -> Vec2:
    return Vec2(math.cos(angle) * length, math.sin(angle) * length)


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def wrap_angle(angle: float) -> float:
    return angle % TAU


def hex_to_rgb(value: str) -> Color:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def mix_color(a: Color, b: Color, t: float) -> Color:
    t = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def scale_color(color: Color, k: float) -> Color:
    return (
        int(clamp(color[0] * k, 0, 255)),
        int(clamp(color[1] * k, 0, 255)),
        int(clamp(color[2] * k, 0, 255)),
    )


def sanitize_name(raw: str, max_length: int = 16, default: str = "Player") -> str:
    allowed_punctuation = " -_.'"
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in allowed_punctuation)
    cleaned = " ".join(cleaned.split())[:max_length].strip()
    return cleaned if cleaned else default
