from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from src.beyblade_data import BeybladeSpec
from src.utilities import Color, mix_color

Point = Tuple[float, float]
Layer = Tuple  # ("circle", radius, color_key, width) | ("poly", points, color_key, outline_key)

SPRITE_SIZE = 192
UNIT_PIXELS = SPRITE_SIZE * 0.46


def _polar(points: Sequence[Point]) -> List[Point]:
    return [(r * math.cos(a), r * math.sin(a)) for r, a in points]


def _rotate(points: Sequence[Point], angle: float) -> List[Point]:
    c, s = math.cos(angle), math.sin(angle)
    return [(x * c - y * s, x * s + y * c) for x, y in points]


def _copies(points: Sequence[Point], count: int, offset: float = 0.0) -> List[List[Point]]:
    return [_rotate(points, offset + k * math.tau / count) for k in range(count)]


def curved_blade(r0: float, r1: float, sweep: float, width: float, power: float = 1.0, steps: int = 10) -> List[Point]:
    ts = [i / steps for i in range(steps + 1)]
    outer = [(r0 + (r1 - r0) * t, sweep * (t ** power)) for t in ts]
    inner = [(r0 + (r1 - r0) * t, sweep * (t ** power) - width * (1.0 - t)) for t in reversed(ts)]
    return _polar(outer + inner)


def leaf(r0: float, r1: float, half_width: float, steps: int = 8) -> List[Point]:
    ts = [i / steps for i in range(steps + 1)]
    upper = [(r0 + (r1 - r0) * t, half_width * math.sin(math.pi * t ** 0.8)) for t in ts]
    lower = [(x, -y) for x, y in reversed(upper)]
    return upper + lower[1:-1]


def bolt(r0: float, r1: float, w: float) -> List[Point]:
    mid = r0 + (r1 - r0) * 0.5
    return [
        (r0, -w * 0.4), (r0 + (r1 - r0) * 0.3, -w), (mid, -w * 0.15), (r1, -w * 0.5),
        (r1 * 0.97, w * 0.15), (mid + 0.08, w * 0.7), (r0 + (r1 - r0) * 0.35, w * 0.15), (r0, w * 0.5),
    ]


def block(r0: float, r1: float, w: float) -> List[Point]:
    return [(r0, -w), (r1 * 0.82, -w * 1.15), (r1, -w * 0.45), (r1, w * 0.45), (r1 * 0.82, w * 1.15), (r0, w)]


def crystal(r0: float, r1: float, w: float) -> List[Point]:
    mid = r0 + (r1 - r0) * 0.45
    return [(r0, 0.0), (mid, -w), (r1, 0.0), (mid, w)]


def regular_polygon(sides: int, radius: float, offset: float = 0.0) -> List[Point]:
    return [(radius * math.cos(offset + k * math.tau / sides), radius * math.sin(offset + k * math.tau / sides)) for k in range(sides)]


def star(points: int, outer: float, inner: float) -> List[Point]:
    out = []
    for k in range(points * 2):
        r = outer if k % 2 == 0 else inner
        a = -math.pi / 2 + k * math.pi / points
        out.append((r * math.cos(a), r * math.sin(a)))
    return out


def scalloped_ring(base: float, amp: float, lobes: int, steps: int = 72) -> List[Point]:
    return [
        ((base + amp * math.sin(lobes * 2 * math.pi * i / steps)) * math.cos(2 * math.pi * i / steps),
         (base + amp * math.sin(lobes * 2 * math.pi * i / steps)) * math.sin(2 * math.pi * i / steps))
        for i in range(steps)
    ]


def _fire() -> List[Layer]:
    layers: List[Layer] = [("circle", 0.80, "dark", 0)]
    tip = [(0.78, -0.18), (1.02, 0.0), (0.78, 0.18)]
    layers += [("poly", p, "secondary", None) for p in _copies(tip, 10)]
    layers.append(("circle", 0.80, "accent", 3))
    layers += [("poly", p, "primary", "accent") for p in _copies(curved_blade(0.25, 0.96, 0.55, 0.55, 1.2), 5)]
    layers += [("poly", p, "secondary", None) for p in _copies(curved_blade(0.25, 0.70, 0.55, 0.30, 1.2), 5)]
    layers += [("circle", 0.30, "dark", 0), ("circle", 0.20, "accent", 0), ("circle", 0.10, "primary", 0)]
    return layers


def _water() -> List[Layer]:
    layers: List[Layer] = [("poly", scalloped_ring(0.92, 0.05, 8), "dark", None), ("circle", 0.84, "secondary", 0)]
    layers += [("poly", p, "primary", "dark") for p in _copies(curved_blade(0.2, 0.90, 1.0, 0.75, 0.8), 4)]
    layers += [("poly", p, "accent", None) for p in _copies(curved_blade(0.3, 0.84, 1.0, 0.12, 0.8), 4, 0.15)]
    layers += [("circle", 0.30, "dark", 0), ("circle", 0.22, "accent", 0), ("circle", 0.10, "secondary", 0)]
    return layers


def _grass() -> List[Layer]:
    layers: List[Layer] = [("circle", 0.78, "dark", 0)]
    layers += [("poly", p, "secondary", "accent") for p in _copies(leaf(0.2, 0.98, 0.34), 6)]
    layers += [("poly", p, "primary", None) for p in _copies(leaf(0.2, 0.84, 0.24), 6, math.pi / 6)]
    layers += [("poly", p, "accent", None) for p in _copies(leaf(0.25, 0.7, 0.05), 6)]
    layers += [("circle", 0.28, "primary", 0), ("circle", 0.18, "dark", 0), ("circle", 0.09, "accent", 0)]
    return layers


def _stone() -> List[Layer]:
    layers: List[Layer] = [("poly", regular_polygon(8, 1.0, math.pi / 8), "secondary", None), ("circle", 0.90, "primary", 0)]
    layers += [("poly", p, "primary", "accent") for p in _copies(block(0.25, 0.98, 0.34), 4)]
    layers += [("poly", p, "secondary", "accent") for p in _copies(block(0.4, 0.84, 0.18), 4, math.pi / 4)]
    layers += [("circle", 0.90, "accent", 4)]
    layers += [("poly", regular_polygon(6, 0.30), "accent", "secondary"), ("circle", 0.15, "secondary", 0)]
    return layers


def _lightning() -> List[Layer]:
    layers: List[Layer] = [("circle", 0.82, "dark", 0), ("circle", 0.82, "accent", 5)]
    teeth = [(0.78, -0.10), (1.0, 0.0), (0.78, 0.10)]
    layers += [("poly", p, "accent", None) for p in _copies(teeth, 10)]
    layers += [("poly", p, "primary", "dark") for p in _copies(bolt(0.2, 0.98, 0.30), 5)]
    layers += [("poly", p, "secondary", None) for p in _copies(bolt(0.25, 0.68, 0.14), 5, math.pi / 5)]
    layers += [("circle", 0.30, "dark", 0), ("poly", star(5, 0.24, 0.10), "primary", None)]
    return layers


def _wind() -> List[Layer]:
    layers: List[Layer] = [("circle", 0.86, "secondary", 2), ("circle", 0.40, "dark", 0)]
    layers += [("poly", p, "primary", "dark") for p in _copies(curved_blade(0.2, 0.98, 1.5, 0.30, 0.7), 3)]
    layers += [("poly", p, "accent", None) for p in _copies(curved_blade(0.2, 0.85, 1.5, 0.12, 0.7), 3, math.pi / 3)]
    layers += [("circle", 0.22, "secondary", 0), ("circle", 0.12, "dark", 0)]
    return layers


def _ice() -> List[Layer]:
    layers: List[Layer] = [("circle", 0.84, "dark", 0), ("poly", regular_polygon(12, 0.92), "secondary", "accent")]
    layers += [("poly", p, "primary", "accent") for p in _copies(crystal(0.3, 0.98, 0.24), 6)]
    layers += [("poly", p, "secondary", None) for p in _copies(crystal(0.3, 0.68, 0.14), 6, math.pi / 6)]
    layers += [("poly", regular_polygon(6, 0.30), "accent", "primary"), ("poly", regular_polygon(6, 0.17, math.pi / 6), "primary", None)]
    return layers


def _poison() -> List[Layer]:
    layers: List[Layer] = [("circle", 0.86, "dark", 0), ("circle", 0.78, "secondary", 2)]
    layers += [("poly", p, "primary", "dark") for p in _copies(curved_blade(0.25, 0.98, 0.9, 0.42, 1.8), 4)]
    layers += [("poly", p, "secondary", None) for p in _copies(curved_blade(0.28, 0.86, 0.9, 0.10, 1.8), 4)]
    layers += [("circle", 0.32, "dark", 0), ("circle", 0.24, "secondary", 2), ("circle", 0.10, "secondary", 0)]
    return layers


DESIGNS: Dict[str, Callable[[], List[Layer]]] = {
    "inferno_fang": _fire,
    "tidal_surge": _water,
    "verdant_reaper": _grass,
    "titan_breaker": _stone,
    "thunder_blitz": _lightning,
    "gale_phantom": _wind,
    "frostbite_requiem": _ice,
    "venom_viper": _poison,
}


def design_layers(spec_id: str) -> List[Layer]:
    return DESIGNS[spec_id]()


def design_signature(spec_id: str) -> Tuple:
    signature = []
    for layer in design_layers(spec_id):
        if layer[0] == "poly":
            signature.append(("poly", len(layer[1]), tuple(round(c, 2) for point in layer[1][:4] for c in point), layer[2]))
        else:
            signature.append(("circle", layer[1], layer[2], layer[3]))
    return tuple(signature)


def _sprite_colors(spec: BeybladeSpec) -> Dict[str, Color]:
    return dict(spec.colors)


_SPRITE_CACHE: Dict[Tuple[str, int], object] = {}


def render_sprite(spec: BeybladeSpec, size: int = SPRITE_SIZE):
    import pygame

    key = (spec.id, size)
    if key in _SPRITE_CACHE:
        return _SPRITE_CACHE[key]
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    center = size / 2.0
    unit = size * 0.46
    colors = _sprite_colors(spec)
    edge = mix_color(colors["dark"], (0, 0, 0), 0.5)
    for layer in design_layers(spec.id):
        if layer[0] == "circle":
            _, radius, color_key, width = layer
            pygame.draw.circle(surface, colors[color_key], (center, center), radius * unit, int(width))
        else:
            _, points, color_key, outline_key = layer
            pixels = [(center + x * unit, center + y * unit) for x, y in points]
            pygame.draw.polygon(surface, colors[color_key], pixels)
            outline = colors[outline_key] if outline_key else edge
            pygame.draw.polygon(surface, outline, pixels, 2 if outline_key else 1)
    _SPRITE_CACHE[key] = surface
    return surface


def draw_beyblade(surface, camera, b, pos=None, alpha: int = 255) -> None:
    import pygame

    sprite = render_sprite(b.spec)
    zoom = camera.length(b.radius) / UNIT_PIXELS
    rotated = pygame.transform.rotozoom(sprite, -math.degrees(b.angle), max(0.05, zoom))
    if alpha < 255:
        rotated.set_alpha(alpha)
    rect = rotated.get_rect(center=camera.to_screen(pos if pos is not None else b.pos))
    surface.blit(rotated, rect)
