from __future__ import annotations

import math
import random
from typing import Optional

import pygame

from src import config
from src.battle import Battle, Event
from src.battle_ui import BattleHUD
from src.beyblade_art import draw_beyblade
from src.camera import Camera
from src.input_handler import InputHandler
from src.menus import ButtonList, Screen
from src.ui_common import C, draw_panel, draw_text
from src.utilities import Vec2, clamp
from src.visual_effects import PALETTES, EffectsManager

REASON_TOAST = {
    "stamina": "Not enough stamina", "cooldown": "Still on cooldown", "frozen": "You are frozen!",
    "no_target": "No valid target", "full_hp": "HP is already full", "full_stamina": "Stamina is full",
    "no_attack": "Attack is 0 right now", "active": "Already active", "busy": "Busy - try again in a moment",
}


class BattleScene(Screen):
    def __init__(self, game, battle: Battle) -> None:
        super().__init__(game)
        self.battle = battle
        size = pygame.display.get_surface().get_size()
        self.camera = Camera(size, battle.stadium.radius)
        self.effects = EffectsManager(self.camera)
        self.hud = BattleHUD(game.fonts)
        self.input = InputHandler(game.settings.key_bindings)
        self.paused = False
        self.banner: Optional[list] = None
        self.toast: Optional[list] = None
        self.confetti = 0.0
        self.age = 0.0
        self.pause_menu = ButtonList([
            {"label": "Resume", "action": self._resume},
            {"label": "Restart Match", "action": self._restart},
            {"label": lambda: f"Sound: {'On' if game.settings.sound_on else 'Off'}", "action": self._toggle_sound},
            {"label": "Main Menu", "action": self._main_menu},
        ])
        self.result_menu = ButtonList([
            {"label": "Play Again", "action": self._restart},
            {"label": "Main Menu", "action": self._main_menu},
        ])
        self._handle_events(battle.drain_events())

    def _resume(self) -> None:
        self.paused = False

    def _restart(self) -> None:
        self.paused = False
        self.game.sound.stop_all()
        self.battle.restart_match()
        self.effects.clear()
        self.banner = None
        self.toast = None
        self._handle_events(self.battle.drain_events())

    def _toggle_sound(self) -> None:
        s = self.game.settings
        s.sound_on = not s.sound_on
        self.game.sound.set_enabled(s.sound_on)

    def _main_menu(self) -> None:
        self.game.sound.stop_all()
        self.effects.clear()
        self.game.goto_main()

    def handle_event(self, event) -> None:
        battle = self.battle
        if battle.phase == "match_over":
            self.result_menu.handle_event(event, self.game)
            return
        if self.paused:
            if event.type == pygame.KEYDOWN and event.key == self.input.keys["pause"]:
                self.paused = False
            else:
                self.pause_menu.handle_event(event, self.game)
            return
        if event.type == pygame.KEYDOWN:
            if event.key == self.input.keys["pause"]:
                self.paused = True
                self.game.sound.stop_loop()
                self.pause_menu.index = 0
            else:
                self.input.handle_keydown(event, battle)

    def _banner(self, text: str, color: tuple, duration: float) -> None:
        self.banner = [text, 0.0, color, duration]

    def _round_over_text(self, event: Event) -> None:
        battle = self.battle
        winner = event.data.get("winner")
        if event.data.get("match_winner") is not None:
            winner_is_player = winner == battle.player.team
            text, color = ("MATCH WON!", (120, 255, 160)) if winner_is_player else ("MATCH LOST", (255, 110, 100))
        elif winner is None:
            text, color = "DRAW - REPLAY", C["text"]
        elif winner == battle.player.team:
            text, color = "ROUND WON!", (120, 255, 160)
        elif battle.team_mode or battle.opponent_count == 1:
            text, color = "ROUND LOST", (255, 110, 100)
        else:
            survivor = next((b for b in battle.beyblades if b.team == winner), None)
            text, color = f"{survivor.label.upper()} WINS THE ROUND", (255, 180, 100)
        self._banner(text, color, 99.0)

    def _handle_events(self, events) -> None:
        battle, sound, player = self.battle, self.game.sound, self.battle.player
        self.effects.handle_events(events, battle)
        for e in events:
            kind = e.kind
            if kind == "round_start":
                self._banner(f"ROUND {e.data['number']}", C["text"], 1.4)
            elif kind == "countdown":
                self._banner(str(e.data["number"]), (255, 200, 90), 0.8)
                sound.play("countdown_tick")
            elif kind == "let_it_rip":
                self._banner("LET IT RIP!", C["accent"], 1.3)
                sound.play("let_it_rip")
            elif kind == "attached":
                sound.play("attach", 0.6)
            elif kind == "charge_start" and e.data["target"] == player.uid:
                sound.play("charge", 0.8)
            elif kind == "launch":
                sound.play("launch", 1.0 if e.data["target"] == player.uid else 0.7)
            elif kind == "collision":
                sound.play("hit_heavy" if e.data["intensity"] >= 0.9 else "hit_light", clamp(0.4 + e.data["intensity"] * 0.5, 0.3, 1.0))
            elif kind == "attack_hit":
                sound.play("hit_heavy")
            elif kind == "wall_hit":
                sound.play("wall", 0.5 + 0.3 * e.data["intensity"])
            elif kind == "stone_hit":
                sound.play("hit_heavy", 0.8)
            elif kind in ("thorn_hit", "strike"):
                sound.play("hit_light" if kind == "thorn_hit" else "hit_heavy", 0.8)
            elif kind == "attack":
                sound.play("attack", 0.8)
            elif kind == "dash":
                sound.play("dash", 0.7)
            elif kind == "ability":
                sound.play_ability(e.data["spec_id"])
            elif kind == "restore":
                sound.play("restore")
            elif kind == "recover_start":
                sound.play("recover", 1.0 if e.data["target"] == player.uid else 0.5)
            elif kind == "eliminated":
                sound.play("eliminated", 0.9)
            elif kind == "action_rejected" and e.data["target"] == player.uid:
                text = REASON_TOAST.get(e.data["reason"])
                if text:
                    self.toast = [text, 1.2]
            elif kind == "round_over":
                self._round_over_text(e)
                if e.data.get("winner") is not None:
                    sound.play("victory" if e.data["winner"] == player.team else "defeat")

    def update(self, dt: float) -> None:
        self.age += dt
        battle = self.battle
        size = pygame.display.get_surface().get_size()
        if size != self.camera.size:
            self.camera.configure(size, battle.stadium.radius)
        if self.paused:
            return
        if battle.phase != "match_over":
            self.input.poll(battle)
            battle.advance(dt)
        self._handle_events(battle.drain_events())
        self.effects.update(battle, dt)
        if self.banner is not None:
            self.banner[1] += dt
            if self.banner[1] > self.banner[3]:
                self.banner = None
        if self.toast is not None:
            self.toast[1] -= dt
            if self.toast[1] <= 0.0:
                self.toast = None
        if battle.phase in ("round_over", "match_over") and battle.round_winner == battle.player.team:
            self.confetti -= dt
            if self.confetti <= 0.0:
                self.confetti = 0.25
                rng = random.Random(int(self.age * 1000))
                pos = Vec2(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6)) * battle.stadium.radius
                self.effects.burst(pos, PALETTES[battle.player.spec.id] + [(255, 255, 255)], 24, 220, 1.1, 4.0, "dot", 5, drag=1.5)
        level = 0.0
        if battle.phase in ("active", "flight", "launch"):
            ratios = [b.vel.length() / max(1.0, b.speed_limit()) for b in battle.in_play()]
            level = clamp(max(ratios) if ratios else 0.0, 0.0, 1.0)
        self.game.sound.update_spin_loop(level)

    def draw(self, surface) -> None:
        battle, effects, camera = self.battle, self.effects, self.camera
        surface.fill(C["background"])
        effects.draw_stadium(surface, battle)
        effects.draw_ground_effects(surface, battle)
        effects.draw_launchers(surface, battle, battle.player.uid)
        effects.draw_trails(surface, battle)
        for b in battle.beyblades:
            if b.alive:
                draw_beyblade(surface, camera, b, pos=effects.beyblade_draw_position(b, battle))
            elif b.eliminated_at is not None:
                since = battle.time - b.eliminated_at
                if since < 1.2:
                    draw_beyblade(surface, camera, b, alpha=int(200 * (1.0 - since / 1.2)))
        effects.draw_status_overlays(surface, battle)
        effects.draw_thorns_and_bolts(surface, battle)
        effects.draw_particles(surface)
        banner = None
        if self.banner is not None:
            banner = (self.banner[0], self.banner[1], self.banner[2])
        toast = (self.toast[0], self.toast[1]) if self.toast is not None else None
        self.hud.draw(surface, battle, camera, self.game.settings.key_bindings, banner, toast)
        effects.draw_flash(surface)
        if self.paused:
            self._draw_menu_overlay(surface, "PAUSED", self.pause_menu, None)
        elif battle.phase == "match_over":
            won = battle.match_winner == battle.player.team
            sub = f"Final score  {battle.player_score()} - {battle.best_opposing_score()}"
            self._draw_menu_overlay(surface, "VICTORY!" if won else "DEFEAT", self.result_menu, sub, (120, 255, 160) if won else (255, 110, 100))

    def _draw_menu_overlay(self, surface, heading: str, menu: ButtonList, subtitle: Optional[str], color=None) -> None:
        w, h = surface.get_size()
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((10, 11, 14, 170))
        surface.blit(shade, (0, 0))
        pulse = 1.0 + 0.04 * math.sin(self.age * 4.0)
        draw_text(surface, self.game.fonts, heading, int(60 * pulse), color or C["text"], (w // 2, h // 2 - 190), "center", True)
        if subtitle:
            draw_text(surface, self.game.fonts, subtitle, 24, C["text"], (w // 2, h // 2 - 140), "center")
        menu.draw(surface, self.game.fonts, w // 2, h // 2 - 100, 340, 48, 12)
