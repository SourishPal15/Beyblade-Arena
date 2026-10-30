from __future__ import annotations

from src import config
from src.abilities import create_ability
from src.battle import Battle, BattleConfig
from src.beyblade_data import get_spec
from src.utilities import Vec2


def swap_spec(battle: Battle, index: int, spec_id: str) -> None:
    bey = battle.beyblades[index]
    bey.spec = get_spec(spec_id)
    bey.ability = create_ability(bey.spec)
    bey.reset_for_round(bey.pos)


def make_battle(player="inferno_fang", opponent="venom_viper", mode="1v1", stadium="Medium",
                difficulty="Medium", seed=1, active=True, ai=False, rounds=3) -> Battle:
    battle = Battle(BattleConfig(player, mode, stadium, difficulty, "Tester", rounds, seed))
    if opponent is not None:
        swap_spec(battle, 1, opponent)
    if not ai:
        battle.controllers.clear()
    if active:
        battle.begin_active_immediately()
    return battle


def run(battle: Battle, seconds: float, dt: float = config.PHYSICS_DT) -> None:
    for _ in range(int(round(seconds / dt))):
        battle.step(dt)


def place(bey, x: float, y: float) -> None:
    bey.pos = Vec2(x, y)
    bey.vel = Vec2()
