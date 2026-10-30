from __future__ import annotations

import math
from typing import List, Optional, Tuple

from src import config
from src.battle import Battle
from src.beyblade import Beyblade
from src.launch_system import ATTACHING, CHARGING, RELEASED, WAITING
from src.ui_common import C, Fonts, draw_bar, draw_panel, draw_text, hp_color, key_label
from src.utilities import clamp, mix_color

ACTIONS = (
    ("dash", "Dash", "dash"),
    ("attack", "Attack", "attack"),
    ("special", "Ability", "special"),
    ("restore", "Restore HP", "restore"),
    ("recover", "Recover", "recover"),
)
REASON_TEXT = {
    "cooldown": "COOLDOWN", "stamina": "LOW STAMINA", "frozen": "FROZEN", "no_target": "NO TARGET",
    "full_hp": "HP FULL", "full_stamina": "STAMINA FULL", "busy": "BUSY", "active": "ACTIVE",
    "no_attack": "ATTACK 0", "inactive": "",
}
STATUS_LABELS = {
    "charged": ("Charged", (255, 106, 0)),
    "speed_boost": ("Speed x2", (255, 230, 0)),
    "venomous": ("Untouchable", (138, 43, 226)),
    "poison": ("Poisoned", (124, 252, 0)),
    "frozen": ("Frozen", (165, 242, 243)),
    "vortex_slow": ("Vortex slow", (73, 227, 210)),
    "thorn_slow": ("Thorn slow", (0, 168, 107)),
    "repositioning": ("Cyclone", (197, 247, 255)),
}
STRATEGY_TEXT = ((20.0, "Centre"), (50.0, "Wide angle"), (91.0, "Edge run"))


def strategy_for(angle_degrees: float) -> str:
    for limit, text in STRATEGY_TEXT:
        if abs(angle_degrees) <= limit:
            return text
    return "Edge run"


class BattleHUD:
    def __init__(self, fonts: Fonts) -> None:
        self.fonts = fonts

    def draw(self, surface, battle: Battle, camera, key_names: dict, banner: Optional[Tuple[str, float, tuple]],
             toast: Optional[Tuple[str, float]]) -> None:
        self._draw_world_labels(surface, battle, camera)
        self._draw_top_bar(surface, battle)
        self._draw_action_bar(surface, battle, key_names)
        if battle.phase in ("prep", "countdown", "launch", "flight"):
            self._draw_launch_panel(surface, battle, key_names)
        if banner is not None:
            self._draw_banner(surface, banner)
        if toast is not None:
            w, h = surface.get_size()
            draw_text(surface, self.fonts, toast[0], 22, (255, 210, 120), (w // 2, h - 150), "midbottom", True)

    def _team_color(self, battle: Battle, b: Beyblade) -> tuple:
        return C["player_team"] if b.team == battle.player.team else C["enemy_team"]

    def _draw_world_labels(self, surface, battle: Battle, camera) -> None:
        import pygame

        for b in battle.beyblades:
            if not b.alive:
                continue
            center = camera.to_screen(b.pos)
            radius = camera.length(b.radius)
            color = self._team_color(battle, b)
            pygame.draw.circle(surface, color, center, int(radius + 3), 2)
            if b.launched and b.vel.length() > 40.0:
                tip = b.vel.normalized()
                p = (center[0] + tip.x * (radius + 10), center[1] + tip.y * (radius + 10))
                left = (center[0] + tip.x * (radius + 3) - tip.y * 5, center[1] + tip.y * (radius + 3) + tip.x * 5)
                right = (center[0] + tip.x * (radius + 3) + tip.y * 5, center[1] + tip.y * (radius + 3) - tip.x * 5)
                pygame.draw.polygon(surface, color, [p, left, right])
            width = max(54, int(camera.length(72)))
            x = center[0] - width // 2
            y = center[1] - int(radius) - 42
            draw_text(surface, self.fonts, b.label, 14, C["text"], (center[0], y - 2), "midbottom", True)
            hp_rect = pygame.Rect(x, y, width, 7)
            st_rect = pygame.Rect(x, y + 9, width, 5)
            draw_bar(surface, hp_rect, b.hp_ratio, hp_color(b.hp_ratio))
            draw_bar(surface, st_rect, b.stamina_ratio, C["stamina"])
            draw_text(surface, self.fonts, f"{int(math.ceil(b.hp))}", 11, C["text"], (x + width + 4, y - 3))
            draw_text(surface, self.fonts, f"{int(b.stamina)}", 11, C["stamina"], (x + width + 4, y + 7))

    def _draw_top_bar(self, surface, battle: Battle) -> None:
        import pygame

        w, _ = surface.get_size()
        p = battle.player
        bar = pygame.Rect(0, 0, w, 78)
        pygame.draw.rect(surface, (22, 24, 28), bar)
        pygame.draw.line(surface, C["arena_border"], (0, 78), (w, 78), 1)
        pc = p.spec.colors["primary"]
        draw_text(surface, self.fonts, p.label, 20, C["text"], (16, 8), "topleft", True)
        draw_text(surface, self.fonts, f"{p.spec.name}  |  {p.spec.element}", 13, mix_color(pc, (255, 255, 255), 0.3), (16, 32))
        draw_text(surface, self.fonts, "HP", 12, C["text_dim"], (16, 50))
        draw_bar(surface, pygame.Rect(40, 50, 190, 10), p.hp_ratio, hp_color(p.hp_ratio))
        draw_text(surface, self.fonts, f"{int(math.ceil(p.hp))}/{int(p.max_hp)}", 12, C["text"], (236, 48))
        draw_text(surface, self.fonts, "STA", 12, C["text_dim"], (16, 63))
        draw_bar(surface, pygame.Rect(40, 64, 190, 8), p.stamina_ratio, C["stamina"])
        draw_text(surface, self.fonts, f"{int(p.stamina)}/{int(p.max_stamina)}", 12, C["stamina"], (236, 61))
        if p.alive and p.launched:
            spin_rect = pygame.Rect(300, 64, 110, 8)
            draw_bar(surface, spin_rect, p.spin, (230, 180, 70) if not p.low_spin else (230, 90, 60))
            draw_text(surface, self.fonts, "LOW SPIN" if p.low_spin else "SPIN", 12, (230, 90, 60) if p.low_spin else C["text_dim"], (300, 48))
        self._draw_status_chips(surface, p, 430, 50)

        cx = w // 2
        draw_text(surface, self.fonts, f"ROUND {max(1, battle.round_number)}", 18, C["text"], (cx, 6), "midtop", True)
        score = f"{battle.player_score()}  -  {battle.best_opposing_score()}"
        draw_text(surface, self.fonts, score, 28, C["text"], (cx, 28), "midtop", True)
        draw_text(surface, self.fonts, f"First to {battle.rounds_to_win}", 12, C["text_dim"], (cx, 62), "midtop")

        info = f"{battle.cfg.mode}  |  {battle.cfg.stadium}  |  {battle.cfg.difficulty}"
        draw_text(surface, self.fonts, info, 13, C["text_dim"], (w - 16, 8), "topright")
        relation = "Teams: AI team vs YOU" if battle.team_mode else ("Free-for-all" if battle.opponent_count > 1 else "Duel")
        draw_text(surface, self.fonts, relation, 13, C["accent"], (w - 16, 26), "topright", True)
        y = 44
        for b in battle.beyblades:
            if b.uid == p.uid:
                continue
            color = C["text"] if b.alive else (110, 112, 118)
            draw_text(surface, self.fonts, b.label, 12, color, (w - 140, y), "topright")
            draw_bar(surface, pygame.Rect(w - 134, y + 2, 118, 8), b.hp_ratio if b.alive else 0.0, hp_color(b.hp_ratio))
            y += 12

    def _draw_status_chips(self, surface, b: Beyblade, x: int, y: int) -> None:
        import pygame

        for kind, effect in list(b.effects.items()):
            label = STATUS_LABELS.get(kind)
            if label is None:
                continue
            text = f"{label[0]} {effect.remaining:.1f}s"
            rect = draw_text(surface, self.fonts, text, 12, (15, 15, 18), (x + 6, y + 2), "topleft", True)
            chip = pygame.Rect(x, y, rect.width + 12, 18)
            pygame.draw.rect(surface, label[1], chip, border_radius=9)
            draw_text(surface, self.fonts, text, 12, (15, 15, 18), (x + 6, y + 2), "topleft", True)
            x += chip.width + 6
        if b.defence_mult < 1.0:
            draw_text(surface, self.fonts, f"DEF x{b.defence_mult:.2f}", 12, (205, 127, 50), (x, y + 2), "topleft", True)

    def _draw_action_bar(self, surface, battle: Battle, key_names: dict) -> None:
        import pygame

        w, h = surface.get_size()
        p = battle.player
        colors = p.spec.colors
        accent = colors["accent"] if sum(colors["accent"]) > 200 else colors["primary"]
        slot_w, slot_h, gap = 130, 58, 10
        total = len(ACTIONS) * slot_w + (len(ACTIONS) - 1) * gap
        x0 = (w - total) // 2
        y0 = h - slot_h - 14
        for i, (action, title, key) in enumerate(ACTIONS):
            rect = pygame.Rect(x0 + i * (slot_w + gap), y0, slot_w, slot_h)
            ok, reason = battle.can_perform(p, action)
            cooldown = p.cooldowns.get(action, 0.0)
            active = p.recovering if action == "recover" else False
            muted = not ok and not active
            border = accent if (ok or active) else (70, 74, 82)
            draw_panel(surface, rect, (34, 37, 43) if not muted else (26, 28, 32), border, 8, 2 if ok or active else 1)
            if cooldown > 0.0:
                total_cd = config.ACTION_COOLDOWN.get(action, p.spec.ability_cooldown if action == "special" else 1.0)
                if action == "special":
                    total_cd = p.spec.ability_cooldown
                frac = clamp(cooldown / max(0.1, total_cd), 0.0, 1.0)
                shade = pygame.Rect(rect.x + 2, rect.y + 2, int((rect.width - 4) * frac), rect.height - 4)
                pygame.draw.rect(surface, (52, 56, 64), shade, border_radius=6)
            text_color = C["text"] if ok or active else (120, 124, 132)
            draw_text(surface, self.fonts, title, 15, text_color, (rect.x + 8, rect.y + 6), "topleft", True)
            keycap = pygame.Rect(rect.right - 42, rect.y + 6, 34, 20)
            pygame.draw.rect(surface, (58, 62, 70), keycap, border_radius=4)
            draw_text(surface, self.fonts, key_label(key_names.get(key, "")), 11, text_color, keycap.center, "center", True)
            if active:
                status, status_color = "RECOVERING", C["stamina"]
            elif ok:
                cost = p.action_cost(action) if action in config.ACTION_COST_FRACTION else 0.0
                status = f"READY  {int(round(cost))} STA" if cost else "READY"
                status_color = (120, 230, 150)
            elif cooldown > 0.0 and reason == "cooldown":
                status, status_color = f"{cooldown:.1f}s", (230, 190, 110)
            else:
                status, status_color = REASON_TEXT.get(reason, ""), (200, 110, 100)
            draw_text(surface, self.fonts, status, 12, status_color, (rect.x + 8, rect.y + 34), "topleft", True)
            if action == "special":
                for kind in ("charged", "venomous", "speed_boost"):
                    effect = p.effects.get(kind)
                    if effect is not None:
                        draw_bar(surface, pygame.Rect(rect.x + 6, rect.bottom - 7, rect.width - 12, 4), effect.remaining / effect.duration, STATUS_LABELS[kind][1])
        draw_text(surface, self.fonts, p.spec.ability_name, 12, C["text_dim"], (x0 + 2 * (slot_w + gap) + slot_w // 2, y0 - 4), "midbottom")

    def _draw_launch_panel(self, surface, battle: Battle, key_names: dict) -> None:
        import pygame

        w, h = surface.get_size()
        p = battle.player
        launcher = battle.launchers[p.uid]
        panel = pygame.Rect(w // 2 - 260, h - 214, 520, 92)
        draw_panel(surface, panel, (28, 30, 35), C["arena_border"], 10, 1)
        state_text = {
            ATTACHING: "Locking into launcher...",
            WAITING: "Locked and ready" if battle.phase != "launch" else "Hold SPACE to charge",
            CHARGING: "Charging - release to launch!",
            RELEASED: "Launched!",
        }[launcher.state]
        draw_text(surface, self.fonts, state_text, 16, C["text"], (panel.x + 14, panel.y + 8), "topleft", True)
        meter = pygame.Rect(panel.x + 14, panel.y + 36, panel.width - 28, 18)
        draw_bar(surface, meter, launcher.power, mix_color((90, 190, 120), (240, 120, 80), launcher.power))
        low, high = config.SWEET_SPOT
        sweet = pygame.Rect(meter.x + int(meter.width * low), meter.y - 3, int(meter.width * (high - low)), meter.height + 6)
        pygame.draw.rect(surface, (255, 255, 255), sweet, 2, border_radius=3)
        draw_text(surface, self.fonts, "SWEET SPOT", 10, (255, 255, 255), (sweet.centerx, meter.y - 4), "midbottom")
        angle = math.degrees(launcher.aim)
        side = "left" if angle < -1 else "right" if angle > 1 else "straight"
        keys = f"{key_label(key_names.get('aim_left', 'left'))}/{key_label(key_names.get('aim_right', 'right'))} or A/D"
        draw_text(surface, self.fonts, f"Direction: {abs(angle):.0f} deg {side}  -  {strategy_for(angle)}   ({keys} to aim)", 13,
                  C["text_dim"], (panel.x + 14, panel.y + 62))
        row_x = panel.right - 14
        for b in battle.beyblades:
            if b.uid == p.uid:
                continue
            other = battle.launchers[b.uid]
            label = {ATTACHING: "attaching", WAITING: "ready", CHARGING: "charging", RELEASED: "launched"}[other.state]
            row_x_text = f"{b.label}: {label}"
            draw_text(surface, self.fonts, row_x_text, 11, C["text_dim"], (row_x, panel.y + 10 + 13 * (b.uid - 1)), "topright")
        if launcher.released and launcher.result is not None:
            quality = launcher.result.quality.upper()
            color = (120, 255, 160) if quality == "PERFECT" else (255, 180, 100) if quality in ("OVERCHARGED", "WEAK") else C["text"]
            draw_text(surface, self.fonts, f"{quality}  {int(launcher.result.power * 100)}%", 18, color, (panel.centerx, panel.y - 8), "midbottom", True)

    def _draw_banner(self, surface, banner: Tuple[str, float, tuple]) -> None:
        text, age, color = banner
        w, h = surface.get_size()
        pop = 1.0 + 0.5 * max(0.0, 1.0 - age * 5.0)
        size = int(64 * pop)
        draw_text(surface, self.fonts, text, size, (0, 0, 0), (w // 2 + 3, h // 2 - 90 + 3), "center", True)
        draw_text(surface, self.fonts, text, size, color, (w // 2, h // 2 - 90), "center", True)
