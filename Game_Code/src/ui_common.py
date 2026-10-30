from __future__ import annotations

from typing import Dict, Optional, Tuple

from src import config
from src.utilities import Color, hex_to_rgb, mix_color

C = {name: hex_to_rgb(value) for name, value in config.COLORS.items() if value.startswith("#")}


class Fonts:
    def __init__(self) -> None:
        import pygame

        self._pygame = pygame
        self._cache: Dict[Tuple[int, bool], object] = {}
        self._name = pygame.font.match_font("segoeui,arial,helvetica,dejavusans,liberationsans")

    def get(self, size: int, bold: bool = False):
        key = (size, bold)
        if key not in self._cache:
            font = self._pygame.font.Font(self._name, size)
            font.set_bold(bold)
            self._cache[key] = font
        return self._cache[key]


def draw_text(surface, fonts: Fonts, string: str, size: int, color: Color, pos: Tuple[float, float],
              anchor: str = "topleft", bold: bool = False):
    font = fonts.get(size, bold)
    image = font.render(string, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    surface.blit(image, rect)
    return rect


def draw_panel(surface, rect, color: Color = None, border: Optional[Color] = None, radius: int = 8, width: int = 1) -> None:
    import pygame

    pygame.draw.rect(surface, color or C["panel"], rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, width, border_radius=radius)


def draw_bar(surface, rect, ratio: float, fill: Color, back: Color = (20, 22, 26), border: Color = (70, 75, 85)) -> None:
    import pygame

    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surface, back, rect, border_radius=3)
    if ratio > 0.0:
        inner = pygame.Rect(rect.x, rect.y, max(2, int(rect.width * ratio)), rect.height)
        pygame.draw.rect(surface, fill, inner, border_radius=3)
    pygame.draw.rect(surface, border, rect, 1, border_radius=3)


def hp_color(ratio: float) -> Color:
    return mix_color(C["hp_low"], C["hp"], max(0.0, min(1.0, (ratio - 0.2) / 0.5)))


def key_label(name: str) -> str:
    names = {"left shift": "L-Shift", "space": "Space", "escape": "Esc"}
    return names.get(name, name.upper())


def wrap_text(fonts: Fonts, string: str, size: int, max_width: int):
    font = fonts.get(size)
    lines, current = [], ""
    for word in string.split():
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
