import random
import unittest

from src import config
from src.ai_opponent import PROFILES, AIController
from src.abilities import Vortex
from src.battle import Battle, BattleConfig
from src.utilities import Vec2
from tests.helpers import make_battle, place, run

DT = config.PHYSICS_DT


def simulate_round(battle, limit=400.0):
    steps = 0
    while battle.phase not in ("round_over", "match_over") and steps < limit / DT:
        battle.step(DT)
        steps += 1
    return steps * DT


class AITests(unittest.TestCase):
    def test_difficulty_profiles_differ_in_decisions_not_stats(self):
        easy, medium, hard = (PROFILES[d] for d in config.DIFFICULTIES)
        self.assertGreater(easy.interval[0], medium.interval[0])
        self.assertGreater(medium.interval[0], hard.interval[0])
        self.assertGreater(easy.aim_error, medium.aim_error)
        self.assertGreater(medium.aim_error, hard.aim_error)
        self.assertGreater(easy.mistake_chance, hard.mistake_chance)
        self.assertLess(easy.ability_chance, hard.ability_chance)
        for name, profile in PROFILES.items():
            self.assertEqual(profile.interval, config.AI_INTERVALS[name])
        stats = []
        for difficulty in config.DIFFICULTIES:
            battle = Battle(BattleConfig("inferno_fang", "1v1", "Medium", difficulty, seed=5))
            b = battle.beyblades[1]
            stats.append((b.max_hp, b.max_stamina, b.attack, b.defence, b.speed_limit(), b.spec.id))
        self.assertEqual(len(set(stats)), 1)

    def test_ai_moves_attacks_dashes_and_uses_abilities(self):
        seen = set()
        for seed in range(6):
            battle = Battle(BattleConfig("inferno_fang", "1v1", "Medium", "Hard", seed=seed), player_ai=True)
            simulate_round(battle)
            seen |= {e.kind for e in battle.drain_events()}
        self.assertTrue({"attack", "dash", "ability", "collision"} <= seen, seen)

    def test_ai_can_lose_and_battle_ends(self):
        winners = set()
        for seed in range(6):
            battle = Battle(BattleConfig("inferno_fang", "1v1", "Medium", "Medium", seed=seed), player_ai=True)
            simulate_round(battle)
            self.assertEqual(battle.phase, "round_over")
            losers = [b for b in battle.beyblades if not b.alive]
            self.assertEqual(len(losers), 1)
            winners.add(battle.round_winner)
        self.assertEqual(winners, {0, 1})

    def test_ai_never_pays_for_rejected_actions(self):
        battle = Battle(BattleConfig("thunder_blitz", "1v1", "Medium", "Hard", seed=2), player_ai=True)
        rejected = []
        while battle.phase != "round_over":
            battle.step(DT)
            rejected += [e.data["reason"] for e in battle.drain_events() if e.kind == "action_rejected"]
        self.assertNotIn("stamina", rejected)
        self.assertNotIn("frozen", rejected)
        self.assertNotIn("full_hp", rejected)

    def test_ai_recovers_stamina_when_safe(self):
        battle = make_battle("inferno_fang", "gale_phantom", ai=True, difficulty="Medium")
        foe = battle.beyblades[1]
        place(battle.player, 0, 200)
        place(foe, 0, -200)
        foe.stamina = 10.0
        controller = battle.controllers[foe.uid]
        controller.rng = random.Random(1)
        controller.profile = PROFILES["Hard"]
        controller.timer = 0.0
        battle.controllers = {foe.uid: controller}
        run(battle, 0.5)
        self.assertEqual(controller.mode, "recover")
        run(battle, 2.0)
        self.assertGreater(foe.stamina, 25.0)

    def test_ai_escapes_hostile_vortex(self):
        battle = make_battle("tidal_surge", "inferno_fang", ai=True, difficulty="Hard")
        owner, foe = battle.beyblades
        battle.controllers = {foe.uid: battle.controllers[foe.uid]}
        place(owner, 0, 200)
        place(foe, 60, 0)
        vortex = Vortex(owner, Vec2(0, 0), owner.spec.ability)
        battle.add_world_effect(vortex)
        run(battle, 3.0)
        self.assertFalse(vortex.contains(foe.pos))

    def test_ai_stays_away_from_walls(self):
        battle = Battle(BattleConfig("inferno_fang", "1v1", "Small", "Hard", seed=9), player_ai=True)
        worst = 0.0
        while battle.phase != "round_over" and battle.time < 60:
            battle.step(DT)
            if battle.phase == "active":
                worst = max(worst, max(b.pos.length() for b in battle.beyblades))
        self.assertLess(worst, battle.stadium.radius - 18)

    def test_team_ai_targets_player_and_never_teammates(self):
        battle = Battle(BattleConfig("inferno_fang", "1v2", "Medium", "Hard", seed=7))
        for _ in range(int(12 / DT)):
            battle.step(DT)
        for b in battle.beyblades[1:]:
            controller = battle.controllers[b.uid]
            if controller.target_uid is not None:
                self.assertEqual(controller.target_uid, battle.player.uid)

    def test_free_for_all_ai_can_target_each_other(self):
        battle = make_battle("inferno_fang", None, mode="1v2", difficulty="Easy", ai=True)
        a, b = battle.beyblades[1], battle.beyblades[2]
        self.assertIn(b, battle.opponents_of(a))
        self.assertIn(a, battle.opponents_of(b))

    def test_ai_ignores_eliminated_targets(self):
        battle = make_battle("inferno_fang", "gale_phantom", ai=True)
        foe = battle.beyblades[1]
        controller = battle.controllers[foe.uid]
        battle.player.alive = False
        self.assertEqual(battle.opponents_of(foe), [])
        controller.timer = 0.0
        controller.update(battle, DT)
        self.assertIn(controller.mode, ("attack", "idle"))

    def test_hard_team_flanks_from_different_sides(self):
        battle = make_battle("inferno_fang", None, mode="1v2", difficulty="Hard", ai=True)
        a, b = battle.beyblades[1], battle.beyblades[2]
        place(battle.player, 0, 150)
        place(a, -200, -150)
        place(b, 200, -150)
        for uid in (a.uid, b.uid):
            c = battle.controllers[uid]
            c.mode, c.target_pos = "attack", battle.player.pos.copy()
        move_a = battle.controllers[a.uid]._movement(battle)
        move_b = battle.controllers[b.uid]._movement(battle)
        self.assertNotAlmostEqual(move_a.x, move_b.x, places=2)


if __name__ == "__main__":
    unittest.main()
