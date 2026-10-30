from __future__ import annotations

from dataclasses import dataclass

from src import config


@dataclass
class Settings:
    player_name: str = config.DEFAULT_PLAYER_NAME
    beyblade_id: str = "inferno_fang"
    rounds_to_win: int = config.DEFAULT_ROUNDS_TO_WIN
    sound_on: bool = True
    volume: float = config.SOUND_DEFAULT_VOLUME
    mode: str = "1v1"
    stadium: str = config.DEFAULT_STADIUM
    difficulty: str = config.DEFAULT_DIFFICULTY
    key_bindings: dict = None

    def __post_init__(self) -> None:
        if self.key_bindings is None:
            self.key_bindings = dict(config.KEY_BINDINGS)
