import unittest

from src import combat, config
from src.battle import Battle, BattleConfig
from src.utilities import Vec2
from tests.helpers import make_battle, run


def finish_round(battle, winner_index=0):
    for b in battle.beyblades:
        if b.uid != battle.beyblades[winner_index].uid and b.team != battle.beyblades[winner_index].team:
            b.hp = 0.0
    battle.step(config.PHYSICS_DT)


def wait_for_next_round(battle):
    for _ in range(int(10 / config.PHYSICS_DT)):
        if battle.phase != "round_over":
            return
        battle.step(config.PHYSICS_DT)


class ModeTests(unittest.TestCase):
    def test_opponent_counts_and_distinct_choices(self):
        for mode, count, stadium in (("1v1", 1, "Small"), ("1v2", 2, "Medium"), ("1v3", 3, "Large")):
            battle = Battle(BattleConfig("inferno_fang", mode, stadium, "Easy", seed=3))
            self.assertEqual(len(battle.beyblades), count + 1)
            ids = [b.spec.id for b in battle.beyblades]
            self.assertEqual(len(set(ids)), len(ids))
            self.assertEqual(battle.beyblades[0].spec.id, "inferno_fang")

    def test_stadium_availability_depends_on_mode(self):
        for mode, stadium in (("1v2", "Small"), ("1v3", "Small"), ("1v3", "Medium")):
            with self.assertRaises(ValueError):
                BattleConfig("inferno_fang", mode, stadium).validate()
        for stadium in ("Small", "Medium", "Large"):
            BattleConfig("inferno_fang", "1v1", stadium).validate()
        BattleConfig("inferno_fang", "1v2", "Large").validate()

    def test_invalid_options_rejected(self):
        for kwargs in ({"difficulty": "Insane"}, {"rounds_to_win": 4}, {"mode": "2v2"}):
            with self.assertRaises(ValueError):
                BattleConfig("inferno_fang", **kwargs).validate()
        with self.assertRaises(ValueError):
            BattleConfig("nobody").validate()

    def test_team_rules_by_difficulty(self):
        for mode, stadium in (("1v2", "Medium"), ("1v3", "Large")):
            for difficulty in ("Easy", "Medium"):
                battle = Battle(BattleConfig("inferno_fang", mode, stadium, difficulty, seed=2))
                self.assertFalse(battle.team_mode)
                self.assertEqual(len({b.team for b in battle.beyblades}), len(battle.beyblades))
            hard = Battle(BattleConfig("inferno_fang", mode, stadium, "Hard", seed=2))
            self.assertTrue(hard.team_mode)
            self.assertEqual({b.team for b in hard.beyblades[1:]}, {1})
            self.assertEqual(hard.player.team, 0)

    def test_hard_duel_is_not_team_mode(self):
        battle = Battle(BattleConfig("inferno_fang", "1v1", "Medium", "Hard"))
        self.assertFalse(battle.team_mode)

    def test_player_name_is_label_but_spec_name_unchanged(self):
        battle = Battle(BattleConfig("inferno_fang", player_name="Alex"))
        self.assertEqual(battle.player.label, "Alex")
        self.assertEqual(battle.player.name, "Inferno Fang")
        self.assertEqual(battle.beyblades[1].label, battle.beyblades[1].spec.name)

    def test_blank_name_falls_back_to_default(self):
        battle = Battle(BattleConfig("inferno_fang", player_name="   "))
        self.assertEqual(battle.player.label, config.DEFAULT_PLAYER_NAME)


class RoundTests(unittest.TestCase):
    def test_team_member_elimination_does_not_end_round(self):
        battle = make_battle("inferno_fang", None, mode="1v2", difficulty="Hard")
        battle.beyblades[1].hp = 0.0
        battle.step(config.PHYSICS_DT)
        self.assertFalse(battle.beyblades[1].alive)
        self.assertEqual(battle.phase, "active")
        battle.beyblades[2].hp = 0.0
        battle.step(config.PHYSICS_DT)
        self.assertEqual(battle.phase, "round_over")
        self.assertEqual(battle.round_winner, 0)
        self.assertEqual(battle.scores[0], 1)

    def test_player_elimination_gives_round_to_opposing_team(self):
        battle = make_battle("inferno_fang", None, mode="1v3", stadium="Large", difficulty="Hard")
        battle.player.hp = 0.0
        battle.step(config.PHYSICS_DT)
        self.assertEqual(battle.phase, "round_over")
        self.assertEqual(battle.round_winner, 1)
        self.assertEqual(battle.scores[1], 1)

    def test_free_for_all_last_survivor_wins(self):
        battle = make_battle("inferno_fang", None, mode="1v2", difficulty="Medium")
        battle.beyblades[0].hp = 0.0
        battle.beyblades[1].hp = 0.0
        battle.step(config.PHYSICS_DT)
        self.assertEqual(battle.round_winner, battle.beyblades[2].team)

    def test_simultaneous_elimination_is_a_draw_with_no_score(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        for b in battle.beyblades:
            b.hp = 0.0
        battle.step(config.PHYSICS_DT)
        self.assertTrue(battle.round_draw)
        self.assertEqual(sum(battle.scores.values()), 0)
        number = battle.round_number
        wait_for_next_round(battle)
        self.assertEqual(battle.round_number, number)
        self.assertEqual(battle.phase, "prep")

    def test_spin_out_eliminates(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        battle.beyblades[1].spin = 0.1
        battle.step(config.PHYSICS_DT)
        self.assertFalse(battle.beyblades[1].alive)
        self.assertEqual(battle.beyblades[1].elimination_reason, "spin")

    def test_hp_never_negative_and_eliminated_cannot_act(self):
        battle = make_battle("inferno_fang", None, mode="1v2", difficulty="Easy")
        target = battle.beyblades[1]
        combat.apply_damage(battle, target, 9999.0, battle.player)
        self.assertEqual(target.hp, 0.0)
        battle.step(config.PHYSICS_DT)
        self.assertFalse(target.alive)
        self.assertEqual(battle.can_perform(target, "attack"), (False, "inactive"))
        self.assertFalse(battle.request_action(target, "dash"))
        self.assertEqual(combat.apply_damage(battle, target, 5.0, battle.player), 0.0)

    def test_no_damage_outside_active_phase(self):
        battle = make_battle("inferno_fang", "gale_phantom", active=False)
        self.assertEqual(combat.apply_damage(battle, battle.beyblades[1], 10.0, battle.player), 0.0)

    def test_match_ends_at_rounds_to_win_for_each_setting(self):
        for rounds in config.ROUNDS_OPTIONS:
            battle = make_battle("inferno_fang", "gale_phantom", rounds=rounds)
            for won in range(rounds):
                self.assertIsNone(battle.match_winner)
                finish_round(battle)
                self.assertEqual(battle.scores[0], won + 1)
                if won < rounds - 1:
                    wait_for_next_round(battle)
                    self.assertEqual(battle.phase, "prep")
                    battle.begin_active_immediately()
            self.assertEqual(battle.match_winner, 0)
            wait_for_next_round(battle)
            self.assertEqual(battle.phase, "match_over")

    def test_round_reset_restores_everything(self):
        battle = make_battle("titan_breaker", "gale_phantom")
        p, foe = battle.beyblades
        battle.perform_action(p, "special")
        foe.defence_mult = 0.5
        foe.add_effect("poison", 5.0, drain_mult=1.15, speed_mult=0.8, rate=0.04)
        foe.stamina = 3.0
        p.hp = 20.0
        finish_round(battle)
        self.assertEqual(battle.world_effects, [])
        self.assertEqual(foe.effects, {})
        wait_for_next_round(battle)
        for b in battle.beyblades:
            self.assertEqual(b.hp, b.max_hp)
            self.assertEqual(b.stamina, b.max_stamina)
            self.assertEqual(b.defence_mult, 1.0)
            self.assertEqual(b.effects, {})
            self.assertTrue(all(v == 0.0 for v in b.cooldowns.values()))
            self.assertFalse(b.launched)
        self.assertEqual(battle.world_effects, [])
        self.assertEqual(battle.scores[0], 1)

    def test_restart_match_resets_scores_and_launch_state(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        finish_round(battle)
        battle.restart_match()
        self.assertEqual(battle.scores[0], 0)
        self.assertEqual(battle.round_number, 1)
        self.assertEqual(battle.phase, "prep")
        self.assertIsNone(battle.match_winner)
        self.assertTrue(all(l.state == "attaching" for l in battle.launchers.values()))

    def test_input_cannot_leak_into_next_round(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        battle.request_action(battle.player, "attack")
        finish_round(battle)
        self.assertEqual(battle.player.pending, set())
        self.assertFalse(battle.request_action(battle.player, "attack"))


if __name__ == "__main__":
    unittest.main()
