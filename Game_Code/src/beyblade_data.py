from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from src.config import BEYBLADE_DATA_FILE
from src.utilities import Color, hex_to_rgb

STAT_KEYS = (
    "max_hp", "max_stamina", "attack", "defence", "speed", "mass", "accel_mult", "turn",
    "friction", "spin_rate", "radius", "dash_strength", "collision_resistance", "restitution",
)


@dataclass(frozen=True)
class BeybladeSpec:
    id: str
    name: str
    element: str
    description: str
    colors: Dict[str, Color]
    max_hp: float
    max_stamina: float
    attack: float
    defence: float
    speed: float
    mass: float
    accel_mult: float
    turn: float
    friction: float
    spin_rate: float
    radius: float
    dash_strength: float
    collision_resistance: float
    restitution: float
    ability: Dict[str, object] = field(default_factory=dict)
    launch: Dict[str, float] = field(default_factory=dict)

    @property
    def ability_name(self) -> str:
        return str(self.ability["name"])

    @property
    def ability_description(self) -> str:
        return str(self.ability["description"])

    @property
    def ability_cooldown(self) -> float:
        return float(self.ability["cooldown"])


def parse_spec(raw: dict) -> BeybladeSpec:
    stats = raw["stats"]
    missing = [key for key in STAT_KEYS if key not in stats]
    if missing:
        raise ValueError(f"Beyblade {raw.get('id')} is missing stats: {missing}")
    colors = {name: hex_to_rgb(value) for name, value in raw["colors"].items()}
    return BeybladeSpec(
        id=raw["id"],
        name=raw["name"],
        element=raw["element"],
        description=raw["description"],
        colors=colors,
        ability=dict(raw["ability"]),
        launch={k: float(v) for k, v in raw.get("launch", {}).items()},
        **{key: float(stats[key]) for key in STAT_KEYS},
    )


def load_specs(path: Path = BEYBLADE_DATA_FILE) -> Dict[str, BeybladeSpec]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Beyblade data file not found: {path}") from error
    specs: Dict[str, BeybladeSpec] = {}
    for entry in raw["beyblades"]:
        spec = parse_spec(entry)
        specs[spec.id] = spec
    return specs


_CACHE: Dict[str, BeybladeSpec] = {}


def all_specs() -> Dict[str, BeybladeSpec]:
    if not _CACHE:
        _CACHE.update(load_specs())
    return _CACHE


def spec_list() -> List[BeybladeSpec]:
    return list(all_specs().values())


def get_spec(spec_id: str) -> BeybladeSpec:
    return all_specs()[spec_id]
