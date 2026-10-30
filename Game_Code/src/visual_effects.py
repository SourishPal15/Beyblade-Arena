from __future__ import annotations

import math
import random
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from src import config
from src.abilities import Gust, StoneWall, Thorn, ThunderStrike, Vortex
from src.battle import Battle, Event
from src.beyblade import Beyblade
from src.launch_system import CHARGING, WAITING, Launcher
from src.particles import (
    PRIORITY_ABILITY, PRIORITY_COMBAT, PRIORITY_DECOR, PRIORITY_FLASH, PRIORITY_TRAIL,
    Particle, ParticleSystem, draw_particles, fade_color,
)
from src.stadium import Stadium
from src.utilities import Color, Vec2, clamp, from_angle, hex_to_rgb, mix_color

PALETTES: Dict[str, List[Color]] = {
    "inferno_fang": [(255, 106, 0), (255, 204, 51), (227, 38, 54)],
    "tidal_surge": [(8, 126, 188), (73, 227, 210), (199, 211, 224)],
    "verdant_reaper": [(0, 168, 107), (197, 232, 108), (60, 160, 70)],
    "titan_breaker": [(150, 155, 165), (205, 127, 50), (232, 155, 54)],
    "thunder_blitz": [(255, 230, 0), (212, 169, 0), (255, 255, 200)],
    "gale_phantom": [(135, 206, 235), (229, 231, 235), (197, 247, 255)],
    "frostbite_requiem": [(165, 242, 243), (75, 156, 211), (232, 241, 245)],
    "venom_viper": [(138, 43, 226), (124, 252, 0), (110, 55, 170)],
}
TRAIL_COLORS = {spec_id: colors[0] for spec_id, colors in PALETTES.items()}
EMIT_RATE = {
    "inferno_fang": 45, "tidal_surge": 30, "verdant_reaper": 26, "titan_breaker": 22,
    "thunder_blitz": 40, "gale_phantom": 34, "frostbite_requiem": 26, "venom_viper": 28,
}


def draw_translucent_circle(overlay, color: Color, center: Tuple[int, int], radius: float, alpha: int, width: int = 0) -> None:
    import pygame

    if radius < 1:
        return
    pygame.draw.circle(overlay, (*color, alpha), center, int(radius), width)


class StadiumRenderer:
    def __init__(self) -> None:
        self._cache: Dict[Tuple[float, int], object] = {}

    def surface(self, stadium: Stadium, scale: float):
        import pygame

        key = (stadium.radius, int(scale * 1000))
        if key in self._cache:
            return self._cache[key]
        outer = stadium.outer_radius * scale
        size = int(outer * 2) + 6
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        center = (c, c)
        col = {k: hex_to_rgb(v) for k, v in config.COLORS.items() if v.startswith("#")}
        R = stadium.radius * scale
        pygame.draw.circle(surf, col["arena_outer"], center, int(outer))
        pygame.draw.circle(surf, col["arena_border"], center, int(outer), max(2, int(3 * scale + 1)))
        for k in range(36):
            a = k * math.tau / 36
            px = c + math.cos(a) * (R + (outer - R) * 0.68)
            py = c + math.sin(a) * (R + (outer - R) * 0.68)
            pygame.draw.circle(surf, col["arena_marking"], (px, py), max(2, int(3 * scale + 1)))
        wall_outer = R + (outer - R) * 0.38
        pygame.draw.circle(surf, (58, 61, 68), center, int(wall_outer))
        pygame.draw.circle(surf, (28, 30, 35), center, int(R + 3))
        steps = max(12, int(R / 6))
        for i in range(steps):
            t = i / steps
            radius = R * (1.0 - t)
            pygame.draw.circle(surf, mix_color(col["arena_main"], col["arena_inner"], t), center, max(1, int(radius)))
        for fraction in (0.33, 0.66):
            pygame.draw.circle(surf, col["arena_marking"], center, int(R * fraction), 1)
        pygame.draw.circle(surf, col["arena_marking"], center, int(R * 0.1), 2)
        pygame.draw.line(surf, col["arena_marking"], (c - R * 0.06, c), (c + R * 0.06, c), 1)
        pygame.draw.line(surf, col["arena_marking"], (c, c - R * 0.06), (c, c + R * 0.06), 1)
        pygame.draw.circle(surf, (36, 38, 44), center, int(R), max(3, int(4 * scale + 1)))
        pygame.draw.circle(surf, col["arena_highlight"], center, int(R), 2)
        self._cache.clear()
        self._cache[key] = surf
        return surf

    def draw(self, target, camera, stadium: Stadium) -> None:
        surf = self.surface(stadium, camera.scale)
        cx, cy = camera.to_screen_xy(0.0, 0.0)
        target.blit(surf, surf.get_rect(center=(cx, cy)))


class EffectsManager:
    def __init__(self, camera, seed: int = 11) -> None:
        self.camera = camera
        self.particles = ParticleSystem()
        self.rng = random.Random(seed)
        self.trails: Dict[int, Deque[Tuple[float, float, float]]] = {}
        self.bolts: List[dict] = []
        self.emit_accumulators: Dict[int, float] = {}
        self.time = 0.0
        self.stadium_renderer = StadiumRenderer()
        self._overlay = None
        self.flash = 0.0

    def clear(self) -> None:
        self.particles.clear()
        self.trails.clear()
        self.bolts.clear()
        self.emit_accumulators.clear()
        self.flash = 0.0

    def burst(self, pos: Vec2, colors: List[Color], count: int, speed: float, life: float, size: float,
              kind: str = "dot", priority: int = PRIORITY_COMBAT, drag: float = 2.5, size_end: float = 0.0,
              direction: Optional[Vec2] = None, cone: float = math.tau) -> None:
        base = direction.angle() if direction is not None else 0.0
        for _ in range(count):
            angle = base + self.rng.uniform(-cone / 2.0, cone / 2.0)
            v = self.rng.uniform(0.35, 1.0) * speed
            self.particles.emit(Particle(
                pos.x, pos.y, math.cos(angle) * v, math.sin(angle) * v, life * self.rng.uniform(0.6, 1.0),
                size * self.rng.uniform(0.6, 1.2), self.rng.choice(colors), kind, drag=drag, size_end=size_end,
                rotation=self.rng.uniform(0, math.tau), spin=self.rng.uniform(-8, 8), priority=priority,
            ))

    def ring(self, pos: Vec2, color: Color, radius: float, life: float = 0.45, priority: int = PRIORITY_ABILITY) -> None:
        self.particles.emit(Particle(pos.x, pos.y, 0.0, 0.0, life, radius * 0.25, color, "ring", size_end=radius, priority=priority))

    def handle_events(self, events: List[Event], battle: Battle) -> None:
        by_uid = {b.uid: b for b in battle.beyblades}
        for e in events:
            handler = getattr(self, f"_on_{e.kind}", None)
            if handler is not None:
                handler(e, battle, by_uid)

    def _palette(self, b: Optional[Beyblade]) -> List[Color]:
        return PALETTES[b.spec.id] if b is not None else [(220, 220, 230)]

    def _on_collision(self, e: Event, battle: Battle, by_uid) -> None:
        intensity = e.data["intensity"]
        a, b = by_uid[e.data["a"]], by_uid[e.data["b"]]
        colors = self._palette(a) + self._palette(b) + [(255, 255, 255)]
        self.burst(e.pos, colors, int(6 + 14 * intensity), 160 + 140 * intensity, 0.4, 3.0, "spark", PRIORITY_COMBAT)
        self.ring(e.pos, (230, 230, 240), 22 + 26 * intensity, 0.3, PRIORITY_FLASH)
        if intensity > 0.7:
            self.camera.add_shake(2.0 + 5.0 * intensity)
            self.burst(e.pos, colors, int(8 * intensity), 120, 0.6, 5.0, "dot", PRIORITY_COMBAT, drag=3.0)

    def _on_grind(self, e: Event, battle: Battle, by_uid) -> None:
        self.burst(e.pos, [(255, 220, 120), (255, 255, 255)], 3, 140, 0.25, 2.0, "spark", PRIORITY_COMBAT)

    def _on_wall_hit(self, e: Event, battle: Battle, by_uid) -> None:
        intensity = e.data["intensity"]
        self.burst(e.pos, [(200, 205, 215), (160, 165, 175)], int(3 + 6 * intensity), 110, 0.35, 2.5, "spark", PRIORITY_COMBAT)
        if intensity > 0.9:
            self.camera.add_shake(2.0)

    def _on_attack_hit(self, e: Event, battle: Battle, by_uid) -> None:
        attacker = by_uid[e.data["attacker"]]
        self.burst(e.pos, self._palette(attacker) + [(255, 255, 255)], 18, 260, 0.45, 3.5, "spark", PRIORITY_FLASH)
        self.ring(e.pos, self._palette(attacker)[1], 40, 0.35, PRIORITY_FLASH)
        self.camera.add_shake(4.0)

    def _on_attack(self, e: Event, battle: Battle, by_uid) -> None:
        b = by_uid[e.data["target"]]
        self.burst(e.pos, self._palette(b), 8, 180, 0.3, 3.0, "spark", PRIORITY_COMBAT, direction=e.data["direction"], cone=0.9)

    def _on_dash(self, e: Event, battle: Battle, by_uid) -> None:
        b = by_uid[e.data["target"]]
        self.burst(e.pos, self._palette(b), 14, 200, 0.4, 3.5, "dot", PRIORITY_COMBAT, direction=-e.data["direction"], cone=0.8)

    def _on_launch(self, e: Event, battle: Battle, by_uid) -> None:
        b = by_uid[e.data["target"]]
        quality = e.data["quality"]
        count = 24 + int(30 * e.data["power"])
        self.burst(e.pos, self._palette(b) + [(255, 255, 255)], count, 260, 0.6, 3.5, "spark", PRIORITY_FLASH, direction=e.data["direction"], cone=1.2)
        self.ring(e.pos, self._palette(b)[1], 50, 0.45, PRIORITY_FLASH)
        if quality == "perfect":
            self.ring(e.pos, (255, 255, 255), 80, 0.6, PRIORITY_FLASH)
        self.camera.add_shake(2.0 + 3.0 * e.data["power"])

    def _on_attached(self, e: Event, battle: Battle, by_uid) -> None:
        b = by_uid[e.data["target"]]
        self.burst(e.pos, [(255, 255, 255), self._palette(b)[1]], 10, 90, 0.3, 2.5, "spark", PRIORITY_FLASH)

    def _on_charge_start(self, e: Event, battle: Battle, by_uid) -> None:
        self.ring(e.pos, (230, 230, 240), 34, 0.3, PRIORITY_COMBAT)

    def _on_restore(self, e: Event, battle: Battle, by_uid) -> None:
        self.burst(e.pos, [(79, 209, 122), (190, 255, 200), (255, 255, 255)], 22, 90, 1.0, 3.5, "dot", PRIORITY_ABILITY,
                   drag=1.5, direction=Vec2(0, -1), cone=2.2)
        self.ring(e.pos, (79, 209, 122), 44, 0.6, PRIORITY_ABILITY)

    def _on_recover_start(self, e: Event, battle: Battle, by_uid) -> None:
        self.ring(e.pos, (79, 168, 232), 40, 0.6, PRIORITY_ABILITY)

    def _on_eliminated(self, e: Event, battle: Battle, by_uid) -> None:
        b = by_uid[e.data["target"]]
        self.burst(e.pos, self._palette(b) + [(255, 255, 255)], 50, 280, 1.0, 5.0, "shard", PRIORITY_FLASH, size_end=0.5)
        self.ring(e.pos, (255, 255, 255), 90, 0.7, PRIORITY_FLASH)
        self.camera.add_shake(6.0)

    def _on_freeze(self, e: Event, battle: Battle, by_uid) -> None:
        self.burst(e.pos, PALETTES["frostbite_requiem"], 24, 120, 0.9, 5.0, "shard", PRIORITY_ABILITY)

    def _on_poison_applied(self, e: Event, battle: Battle, by_uid) -> None:
        self.burst(e.pos, PALETTES["venom_viper"], 20, 120, 0.7, 4.5, "dot", PRIORITY_ABILITY)

    def _on_stone_hit(self, e: Event, battle: Battle, by_uid) -> None:
        self.burst(e.pos, PALETTES["titan_breaker"], 20, 200, 0.7, 5.0, "shard", PRIORITY_ABILITY)
        self.camera.add_shake(4.0)

    def _on_thorn_hit(self, e: Event, battle: Battle, by_uid) -> None:
        self.burst(e.pos, PALETTES["verdant_reaper"], 16, 170, 0.6, 4.0, "shard", PRIORITY_ABILITY)

    def _on_strike(self, e: Event, battle: Battle, by_uid) -> None:
        attacker = by_uid[e.data["attacker"]]
        top = Vec2(e.pos.x + self.rng.uniform(-30, 30), e.pos.y - 420)
        points = [top]
        for i in range(1, 8):
            t = i / 7
            points.append(Vec2(top.x + (e.pos.x - top.x) * t + (self.rng.uniform(-24, 24) if i < 7 else 0), top.y + (e.pos.y - top.y) * t))
        self.bolts.append({"points": points, "life": 0.35, "max": 0.35})
        self.burst(e.pos, PALETTES["thunder_blitz"], 36, 320, 0.6, 3.5, "spark", PRIORITY_FLASH)
        self.ring(e.pos, (255, 255, 200), 70, 0.4, PRIORITY_FLASH)
        self.flash = 0.25
        self.camera.add_shake(7.0)

    def _on_ability(self, e: Event, battle: Battle, by_uid) -> None:
        caster = by_uid[e.data["caster"]]
        spec_id = caster.spec.id
        colors = PALETTES[spec_id]
        pos = e.pos
        self.camera.add_shake(3.0)
        if spec_id == "inferno_fang":
            self.burst(pos, colors, 50, 260, 0.9, 6.0, "dot", PRIORITY_ABILITY, drag=2.0, size_end=1.0)
            self.ring(pos, colors[1], 90, 0.6)
        elif spec_id == "tidal_surge":
            self.ring(pos, colors[1], 70, 0.7)
            self.ring(pos, colors[0], 110, 0.9)
        elif spec_id == "verdant_reaper":
            self.burst(pos, colors, 36, 240, 0.9, 5.0, "shard", PRIORITY_ABILITY)
        elif spec_id == "titan_breaker":
            self.burst(pos, colors, 40, 220, 1.0, 6.0, "shard", PRIORITY_ABILITY)
            self.ring(pos, colors[2], 120, 0.7)
            self.camera.add_shake(6.0)
        elif spec_id == "thunder_blitz":
            self.burst(pos, colors, 20, 300, 0.4, 3.0, "spark", PRIORITY_ABILITY)
        elif spec_id == "gale_phantom":
            for i in range(3):
                self.ring(pos, colors[i % 3], 60 + 45 * i, 0.4 + 0.15 * i)
            self.burst(pos, colors, 26, 280, 0.6, 3.0, "spark", PRIORITY_ABILITY)
        elif spec_id == "frostbite_requiem":
            self.ring(pos, colors[2], battle.stadium.radius * 0.9, 0.9)
            self.burst(pos, colors, 40, 260, 1.0, 6.0, "shard", PRIORITY_ABILITY)
            self.flash = 0.2
        elif spec_id == "venom_viper":
            self.burst(pos, colors, 40, 140, 1.1, 8.0, "dot", PRIORITY_ABILITY, drag=1.8, size_end=14.0)

    def _on_round_over(self, e: Event, battle: Battle, by_uid) -> None:
        winner = e.data.get("winner")
        if winner is None:
            return
        for b in battle.beyblades:
            if b.alive and b.team == winner:
                self.burst(b.pos, self._palette(b) + [(255, 255, 255)], 70, 330, 1.4, 5.0, "dot", PRIORITY_FLASH, drag=1.5)

    def _emit_trail_particles(self, b: Beyblade, dt: float) -> None:
        speed = b.vel.length()
        if speed < 40.0:
            return
        acc = self.emit_accumulators.get(b.uid, 0.0) + EMIT_RATE[b.spec.id] * (speed / 300.0) * dt
        count = int(acc)
        self.emit_accumulators[b.uid] = acc - count
        colors = PALETTES[b.spec.id]
        back = -b.vel.normalized()
        for _ in range(min(count, 3)):
            pos = b.pos + back * b.radius * 0.6 + Vec2(self.rng.uniform(-6, 6), self.rng.uniform(-6, 6))
            sid = b.spec.id
            if sid == "inferno_fang":
                p = Particle(pos.x, pos.y, back.x * 40, back.y * 40 - 30, 0.5, 5.0, self.rng.choice(colors), "dot", size_end=0.5, priority=PRIORITY_DECOR)
            elif sid == "tidal_surge":
                p = Particle(pos.x, pos.y, back.x * 30, back.y * 30, 0.6, 2.5, self.rng.choice(colors), "dot", drag=2.0, priority=PRIORITY_DECOR)
            elif sid == "verdant_reaper":
                p = Particle(pos.x, pos.y, back.x * 50, back.y * 50, 0.7, 4.0, self.rng.choice(colors), "shard", rotation=self.rng.uniform(0, 6), spin=6.0, priority=PRIORITY_DECOR)
            elif sid == "titan_breaker":
                p = Particle(pos.x, pos.y, back.x * 25, back.y * 25, 0.8, 5.0, (110, 105, 100), "dot", drag=2.0, size_end=9.0, priority=PRIORITY_DECOR)
            elif sid == "thunder_blitz":
                v = from_angle(self.rng.uniform(0, math.tau), 160)
                p = Particle(pos.x, pos.y, v.x, v.y, 0.25, 2.5, self.rng.choice(colors), "spark", priority=PRIORITY_DECOR)
            elif sid == "gale_phantom":
                side = back.perp() * self.rng.uniform(-60, 60)
                p = Particle(pos.x, pos.y, back.x * 60 + side.x, back.y * 60 + side.y, 0.5, 2.5, self.rng.choice(colors), "dot", drag=2.0, priority=PRIORITY_DECOR)
            elif sid == "frostbite_requiem":
                p = Particle(pos.x, pos.y, back.x * 35, back.y * 35, 0.7, 4.0, self.rng.choice(colors), "shard", rotation=self.rng.uniform(0, 6), spin=3.0, priority=PRIORITY_DECOR)
            else:
                p = Particle(pos.x, pos.y, back.x * 25, back.y * 25 - 10, 0.9, 4.0, self.rng.choice(colors), "dot", drag=1.5, size_end=10.0 if self.rng.random() < 0.6 else 2.0, priority=PRIORITY_DECOR)
            self.particles.emit(p)

    def update(self, battle: Battle, dt: float) -> None:
        self.time += dt
        self.flash = max(0.0, self.flash - dt)
        for b in battle.beyblades:
            if not (b.alive and b.launched):
                continue
            trail = self.trails.setdefault(b.uid, deque(maxlen=26))
            trail.append((b.pos.x, b.pos.y, self.time))
            self._emit_trail_particles(b, dt)
            if b.charged and self.rng.random() < 0.6:
                self.burst(b.pos, PALETTES[b.spec.id], 1, 80, 0.4, 4.0, "dot", PRIORITY_DECOR, direction=Vec2(0, -1), cone=1.4)
            if b.poisoned and self.rng.random() < 0.3:
                self.burst(b.pos, [(124, 252, 0), (138, 43, 226)], 1, 40, 0.6, 3.0, "dot", PRIORITY_DECOR)
        for uid in list(self.trails):
            trail = self.trails[uid]
            while trail and self.time - trail[0][2] > 0.45:
                trail.popleft()
        for bolt in self.bolts:
            bolt["life"] -= dt
        self.bolts = [b for b in self.bolts if b["life"] > 0.0]
        for effect in battle.world_effects:
            if isinstance(effect, Gust) and self.rng.random() < 0.7:
                spot = effect.center + from_angle(self.rng.uniform(0, math.tau), effect.radius * self.rng.uniform(0.3, 1.0))
                tangent = (spot - effect.center).perp().normalized() * 200
                self.particles.emit(Particle(spot.x, spot.y, tangent.x, tangent.y, 0.4, 2.5, self.rng.choice(PALETTES["gale_phantom"]), "spark", priority=PRIORITY_ABILITY))
            if isinstance(effect, Thorn) and self.rng.random() < 0.5:
                self.particles.emit(Particle(effect.pos.x, effect.pos.y, 0, 0, 0.35, 3.5, PALETTES["verdant_reaper"][1], "dot", size_end=0.5, priority=PRIORITY_TRAIL))
            if isinstance(effect, Vortex) and self.rng.random() < 0.8:
                ang = self.rng.uniform(0, math.tau)
                spot = effect.center + from_angle(ang, effect.radius * self.rng.uniform(0.5, 1.0))
                tangent = (effect.center - spot).perp().normalized() * 120
                self.particles.emit(Particle(spot.x, spot.y, tangent.x, tangent.y, 0.5, 3.0, self.rng.choice(PALETTES["tidal_surge"]), "dot", priority=PRIORITY_ABILITY))
        self.particles.update(dt)
        self.camera.update(dt)

    def _get_overlay(self, size: Tuple[int, int]):
        import pygame

        if self._overlay is None or self._overlay.get_size() != size:
            self._overlay = pygame.Surface(size, pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, 0))
        return self._overlay

    def draw_stadium(self, surface, battle: Battle) -> None:
        self.stadium_renderer.draw(surface, self.camera, battle.stadium)

    def draw_ground_effects(self, surface, battle: Battle) -> None:
        import pygame

        cam = self.camera
        overlay = self._get_overlay(surface.get_size())
        used = False
        for effect in battle.world_effects:
            if isinstance(effect, Vortex):
                used = True
                center = cam.to_screen(effect.center)
                radius = cam.length(effect.radius)
                fade = clamp(min(effect.age / 0.3, (effect.duration - effect.age) / 0.5), 0.0, 1.0)
                draw_translucent_circle(overlay, (8, 126, 188), center, radius, int(70 * fade))
                draw_translucent_circle(overlay, (73, 227, 210), center, radius, int(200 * fade), 3)
                for arm in range(4):
                    pts = []
                    for i in range(24):
                        t = i / 23
                        ang = effect.age * 3.5 + arm * math.pi / 2 + t * 4.2
                        r = radius * (1.0 - t * 0.92)
                        pts.append((center[0] + math.cos(ang) * r, center[1] + math.sin(ang) * r))
                    pygame.draw.lines(overlay, (120, 240, 230, int(210 * fade)), False, pts, 3)
                draw_translucent_circle(overlay, (200, 250, 250), center, max(4, radius * 0.08), int(220 * fade))
            elif isinstance(effect, Gust):
                used = True
                center = cam.to_screen(effect.center)
                radius = cam.length(effect.radius)
                fade = clamp(1.0 - effect.age / effect.duration, 0.0, 1.0)
                draw_translucent_circle(overlay, (197, 247, 255), center, radius, int(40 * fade))
                draw_translucent_circle(overlay, (229, 231, 235), center, radius, int(200 * fade), 3)
                for arm in range(3):
                    pts = []
                    for i in range(16):
                        t = i / 15
                        ang = effect.age * 9.0 + arm * math.tau / 3 + t * 2.6
                        pts.append((center[0] + math.cos(ang) * radius * t, center[1] + math.sin(ang) * radius * t))
                    pygame.draw.lines(overlay, (255, 255, 255, int(200 * fade)), False, pts, 2)
        if used:
            surface.blit(overlay, (0, 0))
        for effect in battle.world_effects:
            if isinstance(effect, StoneWall):
                left, top, right, bottom = effect.rect()
                x1, y1 = cam.to_screen_xy(left, top)
                x2, y2 = cam.to_screen_xy(right, bottom)
                rect = pygame.Rect(x1, y1, max(2, x2 - x1), max(2, y2 - y1))
                remaining = effect.duration - effect.age
                shade = 1.0 if remaining > 1.5 else 0.6 + 0.4 * math.sin(effect.age * 18)
                pygame.draw.rect(surface, mix_color((37, 42, 52), (112, 119, 128), shade), rect, border_radius=4)
                pygame.draw.rect(surface, (205, 127, 50), rect, 3, border_radius=4)
                for k in range(1, 4):
                    if rect.width > rect.height:
                        px = rect.x + rect.width * k // 4
                        pygame.draw.line(surface, (60, 64, 72), (px, rect.y + 3), (px, rect.bottom - 3), 2)
                    else:
                        py = rect.y + rect.height * k // 4
                        pygame.draw.line(surface, (60, 64, 72), (rect.x + 3, py), (rect.right - 3, py), 2)

    def draw_launchers(self, surface, battle: Battle, player_uid: int) -> None:
        import pygame

        if battle.phase not in ("prep", "countdown", "launch", "flight") and not battle.launchers:
            return
        cam = self.camera
        for b in battle.beyblades:
            launcher = battle.launchers.get(b.uid)
            if launcher is None:
                continue
            direction = from_angle(launcher.direction_angle)
            outward = -from_angle(launcher.base_angle)
            anchor = b.pos if not b.launched else battle.stadium.launch_positions(len(battle.beyblades))[b.uid]
            recoil = math.sin(launcher.release_progress * math.pi) * 14 if launcher.released else 0.0
            colors = PALETTES[b.spec.id]
            base = anchor + outward * (10 + recoil)
            side = outward.perp()
            body = [base + side * 17, base + side * -17, base + outward * 70 + side * -17, base + outward * 70 + side * 17]
            pygame.draw.polygon(surface, (46, 49, 56), [cam.to_screen(p) for p in body])
            pygame.draw.polygon(surface, (98, 104, 115), [cam.to_screen(p) for p in body], 2)
            stripe = [base + outward * 8 + side * 17, base + outward * 8 + side * -17, base + outward * 16 + side * -17, base + outward * 16 + side * 17]
            pygame.draw.polygon(surface, colors[0], [cam.to_screen(p) for p in stripe])
            grip_start = base + outward * 70
            pull = launcher.power * 34 if launcher.state == CHARGING else 0.0
            grip = grip_start + outward * (6 + pull)
            pygame.draw.line(surface, (200, 205, 215), cam.to_screen(grip_start), cam.to_screen(grip), 3)
            pygame.draw.circle(surface, colors[1], cam.to_screen(grip + outward * 6), max(3, int(cam.length(8))))
            if not launcher.attached:
                gap = (1.0 - launcher.attach) * 16
                for sign in (-1, 1):
                    start = anchor + side * sign * (b.radius + 4 + gap)
                    end = start + outward * 12
                    pygame.draw.line(surface, (190, 195, 205), cam.to_screen(start), cam.to_screen(end), 4)
            else:
                for sign in (-1, 1):
                    start = anchor + side * sign * (b.radius + 4)
                    pygame.draw.line(surface, (190, 195, 205), cam.to_screen(start), cam.to_screen(start + outward * 12), 4)
            if launcher.state in (WAITING, CHARGING) and b.uid == player_uid:
                length = 150
                for k in range(1, 9):
                    p = anchor + direction * (k * length / 8)
                    pygame.draw.circle(surface, mix_color((98, 104, 115), colors[1], launcher.power), cam.to_screen(p), max(1, int(cam.length(3))))
                tip = anchor + direction * (length + 14)
                left = tip - direction * 14 + direction.perp() * 8
                right = tip - direction * 14 - direction.perp() * 8
                pygame.draw.polygon(surface, colors[1], [cam.to_screen(tip), cam.to_screen(left), cam.to_screen(right)])

    def beyblade_draw_position(self, b: Beyblade, battle: Battle) -> Vec2:
        launcher = battle.launchers.get(b.uid)
        if launcher is None or b.launched or launcher.attached:
            return b.pos
        outward = -from_angle(launcher.base_angle)
        ease = 1.0 - (1.0 - launcher.attach) ** 2
        return b.pos + outward * (60.0 * (1.0 - ease))

    def draw_trails(self, surface, battle: Battle) -> None:
        import pygame

        cam = self.camera
        for uid, trail in self.trails.items():
            b = next((x for x in battle.beyblades if x.uid == uid), None)
            if b is None or len(trail) < 2:
                continue
            color = TRAIL_COLORS[b.spec.id]
            pts = list(trail)
            for i in range(1, len(pts)):
                age = (self.time - pts[i][2]) / 0.45
                fade = clamp(1.0 - age, 0.0, 1.0)
                width = max(1, int(cam.length(b.radius * 0.9) * fade * 0.8))
                pygame.draw.line(surface, fade_color(color, fade * 0.8),
                                 cam.to_screen_xy(pts[i - 1][0], pts[i - 1][1]), cam.to_screen_xy(pts[i][0], pts[i][1]), width)

    def draw_status_overlays(self, surface, battle: Battle) -> None:
        import pygame

        cam = self.camera
        overlay = self._get_overlay(surface.get_size())
        any_drawn = False
        for b in battle.beyblades:
            if not (b.alive and b.launched):
                continue
            center = cam.to_screen(b.pos)
            r = cam.length(b.radius)
            pulse = 0.5 + 0.5 * math.sin(self.time * 8.0 + b.uid)
            if b.charged:
                any_drawn = True
                draw_translucent_circle(overlay, (255, 106, 0), center, r * (1.7 + 0.2 * pulse), 90)
                draw_translucent_circle(overlay, (255, 204, 51), center, r * 1.35, 140, 2)
            if b.has_effect("speed_boost"):
                any_drawn = True
                draw_translucent_circle(overlay, (255, 230, 0), center, r * (1.4 + 0.2 * pulse), 150, 2)
                for _ in range(2):
                    a = self.rng.uniform(0, math.tau)
                    p1 = (center[0] + math.cos(a) * r, center[1] + math.sin(a) * r)
                    p2 = (center[0] + math.cos(a + 0.3) * r * 1.9, center[1] + math.sin(a + 0.3) * r * 1.9)
                    pygame.draw.line(overlay, (255, 245, 150, 220), p1, p2, 2)
            if b.venomous:
                any_drawn = True
                draw_translucent_circle(overlay, (60, 20, 90), center, r * (1.9 + 0.2 * pulse), 150)
                draw_translucent_circle(overlay, (138, 43, 226), center, r * 1.5, 200, 3)
            if b.poisoned:
                any_drawn = True
                draw_translucent_circle(overlay, (124, 252, 0), center, r * 1.25, 160, 2)
                draw_translucent_circle(overlay, (138, 43, 226), center, r * 1.1, 70)
            if b.frozen:
                any_drawn = True
                draw_translucent_circle(overlay, (165, 242, 243), center, r * 1.2, 110)
                draw_translucent_circle(overlay, (232, 241, 245), center, r * 1.2, 230, 2)
                for k in range(6):
                    a = k * math.pi / 3 + 0.2
                    pygame.draw.line(overlay, (232, 241, 245, 220), (center[0] + math.cos(a) * r * 0.5, center[1] + math.sin(a) * r * 0.5),
                                     (center[0] + math.cos(a) * r * 1.3, center[1] + math.sin(a) * r * 1.3), 2)
            if b.has_effect("vortex_slow"):
                any_drawn = True
                draw_translucent_circle(overlay, (73, 227, 210), center, r * 1.3, 160, 2)
            if b.has_effect("thorn_slow"):
                any_drawn = True
                draw_translucent_circle(overlay, (0, 168, 107), center, r * 1.3, 170, 2)
            if b.has_effect("repositioning"):
                any_drawn = True
                draw_translucent_circle(overlay, (197, 247, 255), center, r * 1.5, 130, 2)
            if b.defence_mult < 1.0:
                any_drawn = True
                for k in range(4):
                    a = k * math.pi / 2 + 0.6
                    pygame.draw.line(overlay, (205, 127, 50, 230), (center[0] + math.cos(a) * r * 1.1, center[1] + math.sin(a) * r * 1.1),
                                     (center[0] + math.cos(a + 0.25) * r * 1.5, center[1] + math.sin(a + 0.25) * r * 1.5), 2)
        if any_drawn:
            surface.blit(overlay, (0, 0))

    def draw_thorns_and_bolts(self, surface, battle: Battle) -> None:
        import pygame

        cam = self.camera
        for effect in battle.world_effects:
            if isinstance(effect, Thorn):
                tip = effect.pos + effect.vel.normalized() * 14
                tail = effect.pos - effect.vel.normalized() * 8
                side = effect.vel.normalized().perp() * 5
                pts = [cam.to_screen(tip), cam.to_screen(tail + side), cam.to_screen(tail - side)]
                pygame.draw.polygon(surface, (197, 232, 108), pts)
                pygame.draw.polygon(surface, (0, 168, 107), pts, 1)
            elif isinstance(effect, ThunderStrike):
                target = effect.target
                if not target.alive:
                    continue
                center = cam.to_screen(target.pos)
                r = cam.length(target.radius * (2.4 - 1.2 * clamp(effect.age / effect.delay, 0.0, 1.0)))
                pygame.draw.circle(surface, (255, 230, 0), center, int(r), 2)
                span = int(cam.length(target.radius * 2.8))
                pygame.draw.line(surface, (255, 230, 0), (center[0] - span, center[1]), (center[0] + span, center[1]), 1)
                pygame.draw.line(surface, (255, 230, 0), (center[0], center[1] - span), (center[0], center[1] + span), 1)
        for bolt in self.bolts:
            fade = bolt["life"] / bolt["max"]
            pts = [cam.to_screen(p) for p in bolt["points"]]
            pygame.draw.lines(surface, (255, 255, 220), False, pts, max(2, int(5 * fade)))
            pygame.draw.lines(surface, (255, 230, 0), False, pts, max(1, int(2 * fade)))

    def draw_particles(self, surface) -> None:
        draw_particles(surface, self.camera, self.particles)

    def draw_flash(self, surface) -> None:
        import pygame

        if self.flash > 0.0:
            overlay = self._get_overlay(surface.get_size())
            overlay.fill((255, 255, 255, int(120 * clamp(self.flash / 0.25, 0, 1))))
            surface.blit(overlay, (0, 0))
