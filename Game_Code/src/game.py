from __future__ import annotations

from typing import List

from src import config
from src.battle import Battle
from src.settings import Settings


class Game:
    def __init__(self) -> None:
        import pygame

        pygame.init()
        self.pygame = pygame
        self.settings = Settings()
        pygame.display.set_caption(config.GAME_TITLE)
        pygame.display.set_mode(config.WINDOW_SIZE, pygame.RESIZABLE)
        from src.sound_manager import SoundManager
        from src.ui_common import Fonts

        self.fonts = Fonts()
        self.sound = SoundManager(self.settings.sound_on, self.settings.volume)
        self.clock = pygame.time.Clock()
        self.time = 0.0
        self.running = True
        self.stack: List[object] = []
        from src.menus import MainMenu

        self.push(MainMenu(self))

    @property
    def screen(self):
        return self.stack[-1]

    def push(self, screen) -> None:
        self.stack.append(screen)

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()

    def replace(self, screen) -> None:
        self.stack[-1] = screen

    def goto_main(self) -> None:
        from src.menus import MainMenu

        self.sound.stop_all()
        self.stack = [MainMenu(self)]

    def start_battle(self, battle: Battle) -> None:
        from src.battle_scene import BattleScene

        self.push(BattleScene(self, battle))

    def quit(self) -> None:
        self.running = False

    def _handle_resize(self, event) -> None:
        pygame = self.pygame
        min_w, min_h = config.MIN_WINDOW_SIZE
        if event.w < min_w or event.h < min_h:
            pygame.display.set_mode((max(min_w, event.w), max(min_h, event.h)), pygame.RESIZABLE)

    def run(self) -> None:
        pygame = self.pygame
        try:
            while self.running:
                dt = min(self.clock.tick(config.FPS) / 1000.0, config.MAX_FRAME_TIME)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.VIDEORESIZE:
                        self._handle_resize(event)
                    else:
                        self.screen.handle_event(event)
                if not self.running:
                    break
                self.time += dt
                screen = self.screen
                screen.update(dt)
                screen.draw(pygame.display.get_surface())
                pygame.display.flip()
        finally:
            self.sound.shutdown()
            pygame.quit()
