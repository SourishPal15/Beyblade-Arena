from __future__ import annotations

import math
from typing import Callable, List, Optional

import pygame

from src import config
from src.battle import Battle, BattleConfig
from src.beyblade_art import UNIT_PIXELS, render_sprite
from src.beyblade_data import BeybladeSpec, spec_list
from src.ui_common import C, Fonts, draw_bar, draw_panel, draw_text, key_label, wrap_text
from src.utilities import mix_color, sanitize_name

ENTER_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER)


def draw_background(surface) -> None:
    surface.fill(C["background"])
    w, h = surface.get_size()
    pygame.draw.line(surface, C["accent"], (0, 0), (w, 0), 3)


def draw_sprite(surface, spec: BeybladeSpec, center, radius_px: float, angle: float = 0.0) -> None:
    sprite = render_sprite(spec)
    zoom = max(0.05, radius_px / UNIT_PIXELS)
    rotated = pygame.transform.rotozoom(sprite, -math.degrees(angle), zoom)
    surface.blit(rotated, rotated.get_rect(center=(int(center[0]), int(center[1]))))


class Screen:
    def __init__(self, game) -> None:
        self.game = game

    def handle_event(self, event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface) -> None:
        pass


class ButtonList:
    def __init__(self, items: List[dict]) -> None:
        self.items = items
        self.index = 0
        self.rects: List[pygame.Rect] = []

    def label(self, item: dict) -> str:
        label = item["label"]
        return label() if callable(label) else label

    def enabled(self, item: dict) -> bool:
        return item.get("enabled", True)

    def draw(self, surface, fonts: Fonts, center_x: int, top: int, width: int = 380, height: int = 50, gap: int = 12) -> None:
        self.rects = []
        for i, item in enumerate(self.items):
            rect = pygame.Rect(center_x - width // 2, top + i * (height + gap), width, height)
            self.rects.append(rect)
            selected = i == self.index and self.enabled(item)
            color = C["panel_alt"] if selected else C["panel"]
            draw_panel(surface, rect, color, C["accent"] if selected else (60, 64, 72), 8, 2 if selected else 1)
            if selected:
                pygame.draw.rect(surface, C["accent"], pygame.Rect(rect.x, rect.y + 8, 4, rect.height - 16))
            text_color = C["text"] if self.enabled(item) else (100, 104, 112)
            draw_text(surface, fonts, self.label(item), 20, text_color, rect.center, "center", selected)

    def handle_event(self, event, game) -> None:
        if event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos) and i != self.index:
                    self.index = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.index = i
                    self._trigger(game)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._move(-1, game)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._move(1, game)
            elif event.key in ENTER_KEYS:
                self._trigger(game)

    def _move(self, step: int, game) -> None:
        for _ in range(len(self.items)):
            self.index = (self.index + step) % len(self.items)
            if self.enabled(self.items[self.index]):
                break
        game.sound.play("ui_click")

    def _trigger(self, game) -> None:
        item = self.items[self.index]
        if self.enabled(item):
            game.sound.play("ui_select")
            item["action"]()


def title(surface, fonts: Fonts, text: str, subtitle: str = "") -> None:
    w, _ = surface.get_size()
    draw_text(surface, fonts, text, 40, C["text"], (w // 2, 38), "midtop", True)
    if subtitle:
        draw_text(surface, fonts, subtitle, 17, C["text_dim"], (w // 2, 92), "midtop")


class BackButton:
    def __init__(self, label: str = "Back") -> None:
        self.label = label
        self.rect = pygame.Rect(0, 0, 130, 42)

    def draw(self, surface, fonts: Fonts, hover: bool) -> None:
        _, h = surface.get_size()
        self.rect.topleft = (24, h - 66)
        draw_panel(surface, self.rect, C["panel_alt"] if hover else C["panel"], (90, 94, 104), 8)
        draw_text(surface, fonts, self.label, 18, C["text"], self.rect.center, "center")

    def hit(self, event) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)


class MainMenu(Screen):
    def __init__(self, game) -> None:
        super().__init__(game)
        s = game.settings
        self.list = ButtonList([
            {"label": lambda: f"Player Name: {s.player_name}", "action": lambda: game.push(NameScreen(game))},
            {"label": "Play vs Computer", "action": lambda: game.push(ModeScreen(game))},
            {"label": "Choose Your Beyblade", "action": lambda: game.push(BeybladeScreen(game, self._chosen, "Select"))},
            {"label": "Settings", "action": lambda: game.push(SettingsScreen(game))},
            {"label": "Controls", "action": lambda: game.push(ControlsScreen(game))},
            {"label": "Exit", "action": game.quit},
        ])
        self.list.index = 1

    def _chosen(self, spec: BeybladeSpec) -> None:
        self.game.settings.beyblade_id = spec.id
        self.game.pop()

    def handle_event(self, event) -> None:
        self.list.handle_event(event, self.game)

    def draw(self, surface) -> None:
        draw_background(surface)
        w, h = surface.get_size()
        fonts = self.game.fonts
        draw_text(surface, fonts, "BEYBLADE ARENA", 64, C["text"], (w // 2, max(40, h // 2 - 300)), "midtop", True)
        draw_text(surface, fonts, "Eight elements. One stadium. Let it rip.", 18, C["text_dim"], (w // 2, max(40, h // 2 - 300) + 76), "midtop")
        self.list.draw(surface, fonts, w // 2, max(150, h // 2 - 190))


class NameScreen(Screen):
    def __init__(self, game) -> None:
        super().__init__(game)
        name = game.settings.player_name
        self.text = "" if name == config.DEFAULT_PLAYER_NAME else name
        self.back = BackButton("Cancel")

    def _confirm(self) -> None:
        self.game.settings.player_name = sanitize_name(self.text, config.PLAYER_NAME_MAX, config.DEFAULT_PLAYER_NAME)
        self.game.sound.play("ui_select")
        self.game.pop()

    def handle_event(self, event) -> None:
        if event.type == pygame.TEXTINPUT:
            for ch in event.text:
                if ch.isprintable() and len(self.text) < config.PLAYER_NAME_MAX:
                    self.text += ch
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in ENTER_KEYS:
                self._confirm()
            elif event.key == pygame.K_ESCAPE:
                self.game.pop()
        elif self.back.hit(event):
            self.game.pop()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.ok_rect.collidepoint(event.pos):
            self._confirm()

    def draw(self, surface) -> None:
        draw_background(surface)
        w, h = surface.get_size()
        fonts = self.game.fonts
        title(surface, fonts, "Player Name", "This name is shown above your Beyblade in battle.")
        box = pygame.Rect(w // 2 - 230, h // 2 - 40, 460, 64)
        draw_panel(surface, box, C["panel"], C["accent"], 8, 2)
        cursor = "|" if int(self.game.time * 2) % 2 == 0 else ""
        draw_text(surface, fonts, self.text + cursor, 30, C["text"], (box.x + 18, box.centery), "midleft")
        valid = sanitize_name(self.text, config.PLAYER_NAME_MAX, config.DEFAULT_PLAYER_NAME)
        note = f"{len(self.text)}/{config.PLAYER_NAME_MAX} characters. Empty names use \"{config.DEFAULT_PLAYER_NAME}\"."
        draw_text(surface, fonts, note, 15, C["text_dim"], (box.x, box.bottom + 10))
        draw_text(surface, fonts, f"Will be saved as: {valid}", 15, C["text_dim"], (box.x, box.bottom + 32))
        self.ok_rect = pygame.Rect(w // 2 - 80, box.bottom + 80, 160, 46)
        draw_panel(surface, self.ok_rect, C["panel_alt"], C["accent"], 8, 2)
        draw_text(surface, fonts, "Confirm", 20, C["text"], self.ok_rect.center, "center", True)
        self.back.draw(surface, fonts, self.back.rect.collidepoint(pygame.mouse.get_pos()))

    ok_rect = pygame.Rect(0, 0, 0, 0)


class CardScreen(Screen):
    def __init__(self, game, heading: str, subtitle: str, cards: List[dict], on_pick: Callable[[dict], None], selected: int = 0) -> None:
        super().__init__(game)
        self.heading = heading
        self.subtitle = subtitle
        self.cards = cards
        self.on_pick = on_pick
        self.index = selected
        self.rects: List[pygame.Rect] = []
        self.back = BackButton()

    def _pick(self) -> None:
        card = self.cards[self.index]
        if card.get("enabled", True):
            self.game.sound.play("ui_select")
            self.on_pick(card)

    def _step(self, step: int) -> None:
        self.index = (self.index + step) % len(self.cards)
        self.game.sound.play("ui_click")

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._step(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._step(1)
            elif event.key in ENTER_KEYS:
                self._pick()
            elif event.key == pygame.K_ESCAPE:
                self.game.pop()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.index = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back.hit(event):
                self.game.pop()
                return
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.index = i
                    self._pick()

    def draw(self, surface) -> None:
        draw_background(surface)
        w, h = surface.get_size()
        fonts = self.game.fonts
        title(surface, fonts, self.heading, self.subtitle)
        count = len(self.cards)
        card_w = min(290, (w - 80 - 24 * (count - 1)) // count)
        card_h = min(380, h - 240)
        x0 = (w - (card_w * count + 24 * (count - 1))) // 2
        top = 150
        self.rects = []
        for i, card in enumerate(self.cards):
            rect = pygame.Rect(x0 + i * (card_w + 24), top, card_w, card_h)
            self.rects.append(rect)
            enabled = card.get("enabled", True)
            selected = i == self.index
            draw_panel(surface, rect, C["panel_alt"] if selected and enabled else C["panel"],
                       C["accent"] if selected and enabled else (60, 64, 72), 10, 3 if selected and enabled else 1)
            color = C["text"] if enabled else (100, 104, 112)
            draw_text(surface, fonts, card["title"], 28, color, (rect.centerx, rect.y + 16), "midtop", True)
            preview = card.get("preview")
            if preview:
                preview(surface, pygame.Rect(rect.x + 10, rect.y + 60, rect.width - 20, rect.height // 2 - 20), enabled)
            y = rect.y + rect.height // 2 + 50
            for text in card.get("lines", []):
                for line in wrap_text(fonts, text, 15, rect.width - 28):
                    draw_text(surface, fonts, line, 15, C["text_dim"] if enabled else (90, 94, 102), (rect.centerx, y), "midtop")
                    y += 20
                y += 4
        self.back.draw(surface, fonts, self.back.rect.collidepoint(pygame.mouse.get_pos()))


def stadium_preview(radius: float):
    def draw(surface, rect, enabled: bool) -> None:
        r = int(min(rect.width, rect.height) / 2 * (radius / 420.0) * 0.95) + 6
        center = rect.center
        outer = mix_color(C["arena_outer"], (0, 0, 0), 0.1)
        pygame.draw.circle(surface, outer, center, r + 8)
        pygame.draw.circle(surface, C["arena_border"] if enabled else (60, 62, 68), center, r + 8, 2)
        pygame.draw.circle(surface, C["arena_main"] if enabled else (40, 42, 46), center, r)
        pygame.draw.circle(surface, C["arena_inner"] if enabled else (46, 48, 52), center, int(r * 0.55))
        pygame.draw.circle(surface, C["arena_highlight"] if enabled else (80, 82, 88), center, r, 2)
        draw_sprite_dot(surface, center, 6, enabled)

    return draw


def draw_sprite_dot(surface, center, radius: int, enabled: bool) -> None:
    pygame.draw.circle(surface, C["accent"] if enabled else (70, 72, 78), center, radius)


def mode_preview(opponents: int):
    def draw(surface, rect, enabled: bool) -> None:
        cx, cy = rect.center
        pygame.draw.circle(surface, C["player_team"], (cx, cy + 36), 14)
        for i in range(opponents):
            x = cx + (i - (opponents - 1) / 2) * 52
            pygame.draw.circle(surface, C["enemy_team"], (int(x), cy - 36), 14)
        pygame.draw.line(surface, C["arena_marking"], (cx, cy + 20), (cx, cy - 20), 2)

    return draw


class ModeScreen(CardScreen):
    def __init__(self, game) -> None:
        cards = []
        for mode, info in config.MODES.items():
            n = info["opponents"]
            cards.append({
                "title": mode, "value": mode, "preview": mode_preview(n),
                "lines": [f"You vs {n} computer opponent{'s' if n > 1 else ''}.", "Stadiums: " + ", ".join(info["stadiums"])],
            })
        super().__init__(game, "Choose Mode", "Select how many opponents you face.", cards, self._pick_mode,
                         list(config.MODES).index(game.settings.mode))

    def _pick_mode(self, card: dict) -> None:
        s = self.game.settings
        s.mode = card["value"]
        allowed = config.MODES[s.mode]["stadiums"]
        if s.stadium not in allowed:
            s.stadium = config.DEFAULT_STADIUM if config.DEFAULT_STADIUM in allowed else allowed[0]
        self.game.push(StadiumScreen(self.game))


class StadiumScreen(CardScreen):
    def __init__(self, game) -> None:
        s = game.settings
        allowed = config.MODES[s.mode]["stadiums"]
        cards = []
        for name, radius in config.STADIUM_RADII.items():
            ok = name in allowed
            lines = [config.STADIUM_DESCRIPTIONS[name], f"Playable radius: {int(radius)} units"]
            if not ok:
                lines.append(f"Not available in {s.mode}.")
            cards.append({"title": name.upper(), "value": name, "enabled": ok, "preview": stadium_preview(radius), "lines": lines})
        super().__init__(game, "Choose Stadium", f"Mode {s.mode}: available sizes depend on the number of opponents.",
                         cards, self._pick_stadium, list(config.STADIUM_RADII).index(s.stadium))

    def _pick_stadium(self, card: dict) -> None:
        self.game.settings.stadium = card["value"]
        self.game.push(DifficultyScreen(self.game))


class DifficultyScreen(CardScreen):
    def __init__(self, game) -> None:
        s = game.settings
        multi = config.MODES[s.mode]["opponents"] > 1
        text = {
            "Easy": ["Slow, forgiving decisions and imperfect aim."],
            "Medium": ["Balanced challenge with sensible tactics."],
            "Hard": ["Fast decisions, precise aim and efficient stamina use."],
        }
        if multi:
            text["Easy"].append("Opponents also fight each other.")
            text["Medium"].append("Opponents also fight each other.")
            text["Hard"].append("Opponents team up against you.")
        cards = [{"title": d, "value": d, "lines": text[d] + ["Same rules for everyone: no hidden bonuses."]} for d in config.DIFFICULTIES]
        super().__init__(game, "Choose Difficulty", "Difficulty changes AI decisions, never its stats.", cards,
                         self._pick, config.DIFFICULTIES.index(s.difficulty))

    def _pick(self, card: dict | None = None) -> None:
        card = self.cards[self.index] if card is None else card
        self.game.settings.difficulty = card["value"]
        self.game.push(BeybladeScreen(self.game, self._chosen, "Battle!"))

    def _chosen(self, spec: BeybladeSpec) -> None:
        s = self.game.settings
        s.beyblade_id = spec.id
        cfg = BattleConfig(spec.id, s.mode, s.stadium, s.difficulty, s.player_name, s.rounds_to_win)
        self.game.push(PrepScreen(self.game, cfg))


class BeybladeScreen(Screen):
    STATS = (("Attack", "attack", 130.0), ("Defence", "defence", 130.0), ("Speed", "speed", 130.0),
             ("Max HP", "max_hp", 130.0), ("Max Stamina", "max_stamina", 130.0))

    def __init__(self, game, on_confirm: Callable[[BeybladeSpec], None], confirm_label: str) -> None:
        super().__init__(game)
        self.specs = spec_list()
        self.on_confirm = on_confirm
        self.confirm_label = confirm_label
        self.index = next((i for i, s in enumerate(self.specs) if s.id == game.settings.beyblade_id), 0)
        self.card_rects: List[pygame.Rect] = []
        self.confirm_rect = pygame.Rect(0, 0, 0, 0)
        self.back = BackButton()

    def _confirm(self) -> None:
        self.game.sound.play("ui_select")
        self.on_confirm(self.specs[self.index])

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            moves = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1, pygame.K_UP: -4, pygame.K_w: -4,
                     pygame.K_DOWN: 4, pygame.K_s: 4}
            if event.key in moves:
                new = self.index + moves[event.key]
                if 0 <= new < len(self.specs):
                    self.index = new
                    self.game.sound.play("ui_click")
            elif event.key in ENTER_KEYS:
                self._confirm()
            elif event.key == pygame.K_ESCAPE:
                self.game.pop()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.card_rects):
                if rect.collidepoint(event.pos):
                    self.index = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back.hit(event):
                self.game.pop()
            elif self.confirm_rect.collidepoint(event.pos):
                self._confirm()
            else:
                for i, rect in enumerate(self.card_rects):
                    if rect.collidepoint(event.pos):
                        self.index = i

    def draw(self, surface) -> None:
        draw_background(surface)
        w, h = surface.get_size()
        fonts = self.game.fonts
        title(surface, fonts, "Choose Your Beyblade")
        grid_w = int(w * 0.52)
        cell_w, cell_h = (grid_w - 30) // 4, 140
        self.card_rects = []
        for i, spec in enumerate(self.specs):
            rect = pygame.Rect(24 + (i % 4) * (cell_w + 6), 110 + (i // 4) * (cell_h + 10), cell_w, cell_h)
            self.card_rects.append(rect)
            selected = i == self.index
            draw_panel(surface, rect, C["panel_alt"] if selected else C["panel"], C["accent"] if selected else (60, 64, 72), 8, 3 if selected else 1)
            draw_sprite(surface, spec, (rect.centerx, rect.y + 56), min(44, cell_w * 0.32), self.game.time * spec.spin_rate * 0.3)
            draw_text(surface, fonts, spec.name, 14, C["text"], (rect.centerx, rect.bottom - 30), "midtop", selected)
            draw_text(surface, fonts, spec.element, 12, spec.colors["primary"] if sum(spec.colors["primary"]) > 150 else C["text_dim"], (rect.centerx, rect.bottom - 14), "midtop")
        spec = self.specs[self.index]
        panel = pygame.Rect(grid_w + 40, 110, w - grid_w - 64, h - 200)
        draw_panel(surface, panel, C["panel"], (60, 64, 72), 10)
        draw_sprite(surface, spec, (panel.x + 100, panel.y + 100), 78, self.game.time * spec.spin_rate * 0.25)
        draw_text(surface, fonts, spec.name, 30, C["text"], (panel.x + 200, panel.y + 24), "topleft", True)
        draw_text(surface, fonts, spec.element, 18, C["text_dim"], (panel.x + 200, panel.y + 62))
        for k, key in enumerate(("primary", "secondary", "accent", "dark")):
            swatch = pygame.Rect(panel.x + 200 + k * 34, panel.y + 92, 28, 20)
            pygame.draw.rect(surface, spec.colors[key], swatch, border_radius=4)
            pygame.draw.rect(surface, (90, 94, 104), swatch, 1, border_radius=4)
        y = panel.y + 190
        for label, attr, maximum in self.STATS:
            value = getattr(spec, attr)
            draw_text(surface, fonts, label, 15, C["text_dim"], (panel.x + 20, y))
            draw_bar(surface, pygame.Rect(panel.x + 140, y + 3, panel.width - 220, 12), value / maximum, spec.colors["primary"] if sum(spec.colors["primary"]) > 150 else C["text_dim"])
            draw_text(surface, fonts, f"{int(value)}", 15, C["text"], (panel.right - 20, y), "topright")
            y += 28
        y += 8
        draw_text(surface, fonts, spec.ability_name, 20, C["text"], (panel.x + 20, y), "topleft", True)
        y += 28
        for line in wrap_text(fonts, spec.ability_description, 15, panel.width - 40):
            draw_text(surface, fonts, line, 15, C["text_dim"], (panel.x + 20, y))
            y += 20
        launch = spec.launch
        draw_text(surface, fonts, f"Launch: power x{launch.get('speed', 1):.2f}, stability {launch.get('stability', 1):.2f}, charge {launch.get('charge_rate', 1):.2f}x",
                  13, C["text_dim"], (panel.x + 20, panel.bottom - 28))
        self.confirm_rect = pygame.Rect(w - 220, h - 66, 190, 46)
        draw_panel(surface, self.confirm_rect, C["accent"], None, 8)
        draw_text(surface, fonts, self.confirm_label, 22, (255, 255, 255), self.confirm_rect.center, "center", True)
        self.back.draw(surface, fonts, self.back.rect.collidepoint(pygame.mouse.get_pos()))


class SettingsScreen(Screen):
    def __init__(self, game) -> None:
        super().__init__(game)
        s = game.settings
        self.back = BackButton()
        self.list = ButtonList([
            {"label": lambda: f"Rounds to win: {s.rounds_to_win}", "action": self._cycle_rounds},
            {"label": lambda: f"Sound: {'On' if s.sound_on else 'Off'}", "action": self._toggle_sound},
            {"label": lambda: f"Volume: {int(round(s.volume * 100))}%", "action": self._cycle_volume},
            {"label": "Back", "action": game.pop},
        ])

    def _cycle_rounds(self) -> None:
        s = self.game.settings
        options = config.ROUNDS_OPTIONS
        s.rounds_to_win = options[(options.index(s.rounds_to_win) + 1) % len(options)]

    def _toggle_sound(self) -> None:
        s = self.game.settings
        s.sound_on = not s.sound_on
        self.game.sound.set_enabled(s.sound_on)

    def _cycle_volume(self) -> None:
        s = self.game.settings
        s.volume = round((s.volume + 0.1) if s.volume < 0.99 else 0.1, 1)
        self.game.sound.volume = s.volume

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.pop()
            return
        self.list.handle_event(event, self.game)

    def draw(self, surface) -> None:
        draw_background(surface)
        w, h = surface.get_size()
        title(surface, self.game.fonts, "Settings", "Rounds to win = round victories needed to win the match.")
        self.list.draw(surface, self.game.fonts, w // 2, 170)


class ControlsScreen(Screen):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.back = BackButton()

    def handle_event(self, event) -> None:
        if (event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, *ENTER_KEYS)) or self.back.hit(event):
            self.game.pop()

    def draw(self, surface) -> None:
        draw_background(surface)
        w, h = surface.get_size()
        fonts = self.game.fonts
        title(surface, fonts, "Controls")
        y = 130
        for keys, action in config.CONTROL_LABELS:
            row = pygame.Rect(w // 2 - 380, y, 760, 40)
            draw_panel(surface, row, C["panel"], (60, 64, 72), 6)
            draw_text(surface, fonts, keys, 18, C["accent"], (row.x + 16, row.centery), "midleft", True)
            draw_text(surface, fonts, action, 17, C["text"], (row.x + 270, row.centery), "midleft")
            y += 46
        note = "Launch: wait for LET IT RIP, hold Space to charge, release inside the SWEET SPOT for a bonus. Overcharging makes the launch wobble."
        for i, line in enumerate(wrap_text(fonts, note, 15, 740)):
            draw_text(surface, fonts, line, 15, C["text_dim"], (w // 2 - 370, y + 12 + i * 20))
        self.back.draw(surface, fonts, self.back.rect.collidepoint(pygame.mouse.get_pos()))


class PrepScreen(Screen):
    AUTO_START = 6.0

    def __init__(self, game, cfg: BattleConfig) -> None:
        super().__init__(game)
        self.cfg = cfg
        self.battle = Battle(cfg)
        self.age = 0.0
        self.attached_sounded = False
        self.start_rect = pygame.Rect(0, 0, 0, 0)
        self.back = BackButton()

    def update(self, dt: float) -> None:
        self.age += dt
        if self.age >= 1.1 and not self.attached_sounded:
            self.attached_sounded = True
            self.game.sound.play("attach")
        if self.age >= self.AUTO_START:
            self._begin()

    def _begin(self) -> None:
        self.game.sound.play("ui_select")
        self.game.start_battle(self.battle)

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in ENTER_KEYS and self.age > 1.0:
                self._begin()
            elif event.key == pygame.K_ESCAPE:
                self.game.pop()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back.hit(event):
                self.game.pop()
            elif self.start_rect.collidepoint(event.pos) and self.age > 1.0:
                self._begin()

    def _draw_launcher_slot(self, surface, spec: BeybladeSpec, center, label: str, caption: str, mirror: bool) -> None:
        fonts = self.game.fonts
        progress = min(1.0, self.age / 1.0)
        ease = 1.0 - (1.0 - progress) ** 2
        body = pygame.Rect(0, 0, 190, 36)
        body.center = (center[0], center[1] + 92)
        pygame.draw.rect(surface, (46, 49, 56), body, border_radius=8)
        pygame.draw.rect(surface, (98, 104, 115), body, 2, border_radius=8)
        pygame.draw.rect(surface, spec.colors["primary"], pygame.Rect(body.x + 12, body.y + 6, 36, 24), border_radius=4)
        pygame.draw.line(surface, (200, 205, 215), (body.right, body.centery), (body.right + 24, body.centery), 4)
        pygame.draw.circle(surface, spec.colors["accent"], (body.right + 30, body.centery), 7)
        gap = int((1.0 - ease) * 24)
        for sign in (-1, 1):
            pygame.draw.line(surface, (190, 195, 205), (center[0] + sign * (58 + gap), center[1] + 66),
                             (center[0] + sign * (58 + gap), center[1] + 84), 5)
        bey_y = center[1] - int((1.0 - ease) * 70)
        draw_sprite(surface, spec, (center[0], bey_y), 52, self.age * spec.spin_rate * 0.2 * (1 if not mirror else -1))
        draw_text(surface, fonts, label, 22, C["text"], (center[0], center[1] - 96), "midbottom", True)
        draw_text(surface, fonts, caption, 15, C["text_dim"], (center[0], center[1] + 126), "midtop")
        locked = progress >= 1.0
        status = "LOCKED IN" if locked else "Attaching" + "." * (int(self.age * 4) % 4)
        draw_text(surface, fonts, status, 16, (120, 230, 150) if locked else (230, 190, 110), (center[0], center[1] + 148), "midtop", True)

    def draw(self, surface) -> None:
        draw_background(surface)
        w, h = surface.get_size()
        fonts = self.game.fonts
        title(surface, fonts, "Battle Preparation", f"{self.cfg.mode}  |  {self.cfg.stadium} stadium  |  {self.cfg.difficulty}  |  first to {self.cfg.rounds_to_win}")
        beys = self.battle.beyblades
        player = beys[0]
        self._draw_launcher_slot(surface, player.spec, (w * 0.2, h * 0.42), player.label, f"{player.spec.name}  ({player.spec.element})", False)
        foes = beys[1:]
        for i, foe in enumerate(foes):
            x = w * (0.8 if len(foes) == 1 else 0.62 + 0.2 * i * (1 if len(foes) == 2 else 0.9))
            self._draw_launcher_slot(surface, foe.spec, (min(w - 120, x), h * 0.42), foe.label, f"{foe.spec.name}  ({foe.spec.element})", True)
        mid = pygame.Rect(0, 0, 150, 150)
        mid.center = (w // 2 - (0 if len(foes) == 1 else 40), int(h * 0.42))
        stadium_preview(self.battle.stadium.radius)(surface, mid, True)
        draw_text(surface, fonts, "VS", 26, C["accent"], (mid.centerx, mid.bottom + 8), "midtop", True)
        panel = pygame.Rect(w // 2 - 330, int(h * 0.7), 660, 100)
        draw_panel(surface, panel, C["panel"], (60, 64, 72), 10)
        keys = self.game.settings.key_bindings
        lines = [
            f"Launch: hold {key_label(keys['launch'])} to charge, release to launch.  Aim: A / D or Left / Right.",
            "Release inside the SWEET SPOT for a speed bonus - overcharging makes the launch wobble.",
            "Countdown: 3 - 2 - 1 - LET IT RIP!   Launch only opens after LET IT RIP.",
        ]
        for i, line in enumerate(lines):
            draw_text(surface, fonts, line, 15, C["text"] if i == 0 else C["text_dim"], (panel.x + 18, panel.y + 12 + i * 26))
        self.start_rect = pygame.Rect(w - 240, h - 66, 210, 46)
        ready = self.age > 1.0
        draw_panel(surface, self.start_rect, C["accent"] if ready else (70, 40, 44), None, 8)
        draw_text(surface, fonts, "To the stadium (Enter)", 17, (255, 255, 255) if ready else (150, 150, 150), self.start_rect.center, "center", True)
        remaining = max(0.0, self.AUTO_START - self.age)
        draw_bar(surface, pygame.Rect(w // 2 - 150, h - 54, 300, 8), self.age / self.AUTO_START, C["accent"])
        draw_text(surface, fonts, f"Starting automatically in {remaining:.0f}s", 13, C["text_dim"], (w // 2, h - 40), "midtop")
        self.back.draw(surface, fonts, self.back.rect.collidepoint(pygame.mouse.get_pos()))
