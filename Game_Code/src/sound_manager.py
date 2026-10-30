from __future__ import annotations

import time
from typing import Dict, Optional

from src import config, sound_synth

MIN_INTERVAL = {
    "hit_light": 0.08, "hit_heavy": 0.12, "wall": 0.12, "dash": 0.1, "attack": 0.1,
    "recover": 0.5, "restore": 0.5, "ui_click": 0.03, "countdown_tick": 0.2,
}


class SoundManager:
    def __init__(self, enabled: bool = True, volume: float = config.SOUND_DEFAULT_VOLUME) -> None:
        self.enabled = enabled
        self.volume = volume
        self.available = False
        self._mixer = None
        self._sounds: Dict[str, object] = {}
        self._last_played: Dict[str, float] = {}
        self._loop_channel = None
        self._loop_sound = None
        self._init_mixer()

    def _init_mixer(self) -> None:
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(sound_synth.SAMPLE_RATE, -16, 1, 512)
            pygame.mixer.set_num_channels(24)
            self._mixer = pygame.mixer
            self.available = True
        except Exception:
            self.available = False

    def _load(self, name: str):
        if name in self._sounds:
            return self._sounds[name]
        sound = None
        if self.available:
            path = config.SOUNDS_DIR / f"{name}.wav"
            try:
                if path.exists():
                    sound = self._mixer.Sound(str(path))
                elif name in sound_synth.SOUND_BUILDERS:
                    sound = self._mixer.Sound(buffer=sound_synth.SOUND_BUILDERS[name]())
            except Exception:
                sound = None
        self._sounds[name] = sound
        return sound

    def preload(self) -> None:
        for name in sound_synth.SOUND_BUILDERS:
            self._load(name)

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled or not self.available:
            return
        now = time.monotonic()
        interval = MIN_INTERVAL.get(name, 0.0)
        if interval and now - self._last_played.get(name, -1.0) < interval:
            return
        sound = self._load(name)
        if sound is None:
            return
        self._last_played[name] = now
        sound.set_volume(max(0.0, min(1.0, volume * self.volume)))
        sound.play()

    def play_ability(self, spec_id: str) -> None:
        self.play(f"ability_{spec_id}", 1.0)

    def update_spin_loop(self, level: float) -> None:
        if not self.available:
            return
        if not self.enabled or level <= 0.02:
            self.stop_loop()
            return
        if self._loop_channel is None or not self._loop_channel.get_busy():
            self._loop_sound = self._load("spin_loop")
            if self._loop_sound is None:
                return
            self._loop_channel = self._loop_sound.play(loops=-1)
        if self._loop_channel is not None:
            self._loop_channel.set_volume(max(0.0, min(1.0, level * 0.35 * self.volume)))

    def stop_loop(self) -> None:
        if self._loop_channel is not None:
            self._loop_channel.stop()
            self._loop_channel = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.stop_all()

    def stop_all(self) -> None:
        self.stop_loop()
        if self.available:
            try:
                self._mixer.stop()
            except Exception:
                pass

    def shutdown(self) -> None:
        self.stop_all()
        if self.available:
            try:
                self._mixer.quit()
            except Exception:
                pass
            self.available = False
