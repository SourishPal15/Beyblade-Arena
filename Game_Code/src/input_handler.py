from __future__ import annotations

from typing import Dict

from src import config
from src.battle import Battle
from src.utilities import Vec2

ONE_SHOT_ACTIONS = ("dash", "attack", "special", "restore")


class InputHandler:
    def __init__(self, bindings: Dict[str, str] = None) -> None:
        import pygame

        self._pygame = pygame
        self.bindings = dict(bindings or config.KEY_BINDINGS)
        self.keys = {action: pygame.key.key_code(name) for action, name in self.bindings.items()}

    def handle_keydown(self, event, battle: Battle) -> None:
        for action in ONE_SHOT_ACTIONS:
            if event.key == self.keys[action]:
                battle.request_action(battle.player, action)

    def poll(self, battle: Battle) -> None:
        pressed = self._pygame.key.get_pressed()
        k = self.keys
        horizontal = float(pressed[k["right"]]) - float(pressed[k["left"]])
        vertical = float(pressed[k["down"]]) - float(pressed[k["up"]])
        player = battle.player
        if battle.phase == "active":
            battle.set_input(player, Vec2(horizontal, vertical), bool(pressed[k["recover"]]))
            return
        aim = horizontal + float(pressed[k["aim_right"]]) - float(pressed[k["aim_left"]])
        battle.set_launch_input(player, bool(pressed[k["launch"]]), max(-1.0, min(1.0, aim)))
        battle.set_input(player, Vec2(), False)
