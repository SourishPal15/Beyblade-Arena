import unittest

from src import config, stamina
from src.utilities import Vec2
from tests.helpers import make_battle, place, run


class StaminaTests(unittest.TestCase):
    def setUp(self):
        self.battle = make_battle("inferno_fang", "gale_phantom")
        self.p = self.battle.player
        place(self.p, 0, 0)

    def test_action_costs_are_percent_of_max(self):
        self.assertEqual(stamina.action_cost(100, "dash"), 10)
        self.assertEqual(stamina.action_cost(100, "attack"), 20)
        self.assertEqual(stamina.action_cost(110, "special"), 82.5)
        self.assertEqual(stamina.action_cost(100, "restore"), 75)

    def test_insufficient_stamina_rejects_without_partial_charge(self):
        self.p.stamina = 5.0
        ok, reason = self.battle.perform_action(self.p, "dash")
        self.assertFalse(ok)
        self.assertEqual(reason, "stamina")
        self.assertEqual(self.p.stamina, 5.0)
        self.assertEqual(self.p.cooldowns["dash"], 0.0)

    def test_dash_charges_once_even_when_requested_twice(self):
        before = self.p.stamina
        self.battle.request_action(self.p, "dash")
        self.battle.request_action(self.p, "dash")
        self.battle.step(config.PHYSICS_DT)
        spent = before - self.p.stamina
        self.assertAlmostEqual(spent, 10.0, delta=0.1)
        self.assertGreater(self.p.cooldowns["dash"], 0.9)

    def test_attack_and_special_costs(self):
        before = self.p.stamina
        self.assertTrue(self.battle.perform_action(self.p, "attack")[0])
        self.assertAlmostEqual(before - self.p.stamina, 20.0, places=6)
        self.p.stamina = 100.0
        self.assertTrue(self.battle.perform_action(self.p, "special")[0])
        self.assertAlmostEqual(100.0 - self.p.stamina, 75.0, places=6)

    def test_recovery_rate_is_twenty_percent_per_second(self):
        self.p.stamina = 0.0
        self.battle.set_input(self.p, Vec2(), True)
        run(self.battle, 1.0)
        self.assertAlmostEqual(self.p.stamina, 20.0, delta=1.0)
        run(self.battle, 4.5)
        self.assertGreaterEqual(self.p.stamina, 99.0)
        self.assertLessEqual(self.p.stamina, self.p.max_stamina)

    def test_recovery_is_interrupted_by_steering_and_actions(self):
        self.p.stamina = 10.0
        self.battle.set_input(self.p, Vec2(), True)
        run(self.battle, 0.3)
        self.assertTrue(self.p.recovering)
        self.battle.set_input(self.p, Vec2(1, 0), True)
        self.battle.step(config.PHYSICS_DT)
        self.assertFalse(self.p.recovering)

    def test_recovery_stops_translation_but_not_spin(self):
        self.p.stamina = 10.0
        self.p.vel = Vec2(200, 0)
        self.battle.set_input(self.p, Vec2(), True)
        run(self.battle, 1.5)
        self.assertLess(self.p.vel.length(), 5.0)
        self.assertGreater(self.p.spin, 0.9)

    def test_infernal_breaker_halves_costs(self):
        self.assertEqual(self.p.action_cost("dash"), 10.0)
        self.assertTrue(self.battle.perform_action(self.p, "special")[0])
        self.assertTrue(self.p.charged)
        self.assertAlmostEqual(self.p.action_cost("dash"), 5.0)
        self.assertAlmostEqual(self.p.action_cost("attack"), 10.0)

    def test_status_drain_multipliers_stack_multiplicatively(self):
        self.assertEqual(self.p.drain_multiplier, 1.0)
        self.p.add_effect("frozen", 6.0, drain_mult=config.FROZEN_DRAIN_MULT)
        self.assertAlmostEqual(self.p.drain_multiplier, 1.2)
        self.p.add_effect("poison", 5.0, drain_mult=config.POISON_DRAIN_MULT, speed_mult=0.8, rate=0.04)
        self.assertAlmostEqual(self.p.drain_multiplier, 1.2 * 1.15)

    def test_passive_drain_is_time_based(self):
        a = make_battle()
        b = make_battle()
        run(a, 1.0, 1 / 120)
        for _ in range(60):
            b.step(1 / 60)
        self.assertAlmostEqual(a.player.stamina, b.player.stamina, places=3)
        expected = 100 - 100 * config.PASSIVE_DRAIN_RATE
        self.assertAlmostEqual(a.player.stamina, expected, places=2)

    def test_frozen_stamina_drains_twenty_percent_faster(self):
        a = make_battle()
        b = make_battle()
        b.player.add_effect("frozen", 6.0, drain_mult=1.2)
        run(a, 2.0)
        run(b, 2.0)
        self.assertAlmostEqual((100 - b.player.stamina) / (100 - a.player.stamina), 1.2, places=2)

    def test_restore_hp_cost_amount_and_cooldown(self):
        self.p.hp = 30.0
        self.assertTrue(self.battle.perform_action(self.p, "restore")[0])
        self.assertAlmostEqual(self.p.hp, 80.0)
        self.assertAlmostEqual(self.p.stamina, 25.0)
        self.assertEqual(self.p.cooldowns["restore"], config.ACTION_COOLDOWN["restore"])
        self.p.hp = 60.0
        self.p.stamina = 100.0
        ok, reason = self.battle.perform_action(self.p, "restore")
        self.assertEqual((ok, reason), (False, "cooldown"))

    def test_restore_rejected_at_full_hp_without_cost(self):
        ok, reason = self.battle.perform_action(self.p, "restore")
        self.assertEqual((ok, reason), (False, "full_hp"))
        self.assertEqual(self.p.stamina, 100.0)

    def test_restore_never_exceeds_max_hp(self):
        self.p.hp = 90.0
        self.battle.perform_action(self.p, "restore")
        self.assertEqual(self.p.hp, self.p.max_hp)

    def test_stamina_never_negative_or_above_max(self):
        self.p.stamina = 0.1
        run(self.battle, 5.0)
        self.assertGreaterEqual(self.p.stamina, 0.0)
        self.p.stamina = 99.9
        self.battle.set_input(self.p, Vec2(), True)
        run(self.battle, 2.0)
        self.assertLessEqual(self.p.stamina, self.p.max_stamina)

    def test_zero_time_does_not_change_stamina(self):
        before = self.p.stamina
        self.battle.advance(0.0)
        self.assertEqual(self.p.stamina, before)

    def test_incompatible_actions_resolved_deterministically(self):
        self.p.hp = 40.0
        self.battle.request_action(self.p, "dash")
        self.battle.request_action(self.p, "restore")
        self.battle.step(config.PHYSICS_DT)
        self.assertGreater(self.p.hp, 40.0)
        self.assertGreater(self.p.restore_lock, 0.0)
        self.assertEqual(self.p.cooldowns["dash"], 0.0)


if __name__ == "__main__":
    unittest.main()
