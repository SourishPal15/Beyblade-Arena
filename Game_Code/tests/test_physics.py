import math
import unittest

from src import config
from src.battle import Battle, BattleConfig
from src.stadium import Stadium
from src.utilities import Vec2
from tests.helpers import make_battle, place, run


class PhysicsTests(unittest.TestCase):
    def test_initial_state_matches_spec(self):
        b = make_battle("titan_breaker").player
        self.assertEqual(b.hp, 125)
        self.assertEqual(b.stamina, 100)
        self.assertEqual(b.mass, 1.35)
        self.assertEqual(b.vel.length(), 0.0)
        self.assertTrue(b.alive)

    def test_steering_accelerates_instead_of_teleporting(self):
        battle = make_battle(ai=False)
        p = battle.player
        place(p, 0, 0)
        battle.set_input(p, Vec2(1, 0), False)
        battle.step(config.PHYSICS_DT)
        self.assertLess(p.vel.length(), 0.05 * p.speed_limit())
        self.assertLess(p.pos.x, 1.0)
        run(battle, 0.5)
        self.assertGreater(p.vel.length(), 0.3 * p.speed_limit())
        self.assertLessEqual(p.vel.length(), p.speed_limit() * 1.01)

    def test_diagonal_is_normalized(self):
        speeds = []
        for direction in (Vec2(1, 0), Vec2(1, 1)):
            battle = make_battle()
            place(battle.player, -100, 0)
            battle.set_input(battle.player, direction, False)
            run(battle, 0.5)
            speeds.append(battle.player.vel.length())
        self.assertAlmostEqual(speeds[0], speeds[1], delta=speeds[0] * 0.01)

    def test_friction_slows_and_spin_continues(self):
        battle = make_battle()
        p = battle.player
        place(p, 0, 0)
        p.vel = Vec2(150, 0)
        run(battle, 1.0)
        self.assertLess(p.vel.length(), 150 * math.exp(-config.BASE_DRAG * 0.9 * p.friction))
        self.assertGreater(p.vel.length(), 1.0)
        self.assertGreater(p.spin, 0.9)

    def test_spin_decay_is_independent_of_translation(self):
        still = make_battle()
        moving = make_battle()
        place(still.player, 0, 0)
        place(moving.player, -150, 0)
        moving.set_input(moving.player, Vec2(1, 0), False)
        run(still, 1.0)
        run(moving, 1.0)
        self.assertGreater(moving.player.vel.length(), 100.0)
        self.assertLess(moving.player.pos.length(), moving.stadium.radius - 30)
        expected = math.exp(-config.SPIN_DECAY * 1.0)
        self.assertAlmostEqual(still.player.spin, expected, places=3)
        self.assertAlmostEqual(moving.player.spin, expected, places=3)

    def test_frame_rate_independence(self):
        results = []
        for fps in (30, 144):
            battle = make_battle()
            place(battle.player, 0, 0)
            battle.set_input(battle.player, Vec2(1, 0), False)
            for _ in range(fps):
                battle.advance(1.0 / fps)
            results.append(battle.player.pos.x)
        self.assertAlmostEqual(results[0], results[1], delta=3.0)

    def test_large_frame_time_is_clamped(self):
        battle = make_battle()
        steps = battle.advance(30.0)
        self.assertLessEqual(steps, config.MAX_STEPS_PER_FRAME)

    def test_wall_keeps_beyblade_inside_and_loses_energy(self):
        battle = make_battle(stadium="Small")
        p = battle.player
        place(p, 150, 0)
        p.vel = Vec2(700, 0)
        limit = battle.stadium.radius - p.radius
        farthest = 0.0
        for _ in range(360):
            battle.step(config.PHYSICS_DT)
            farthest = max(farthest, p.pos.length())
        self.assertLessEqual(farthest, limit + 1e-6)
        self.assertLess(p.vel.length(), 700)

    def test_stadium_sizes_change_real_geometry(self):
        radii = [Stadium(n).radius for n in ("Small", "Medium", "Large")]
        self.assertEqual(radii, [220.0, 320.0, 420.0])
        for name in ("Small", "Large"):
            battle = make_battle(stadium=name)
            self.assertEqual(battle.stadium.radius, config.STADIUM_RADII[name])
            for b in battle.beyblades:
                self.assertLessEqual(b.pos.length(), battle.stadium.radius - b.radius)

    def test_unknown_stadium_rejected(self):
        with self.assertRaises(ValueError):
            Stadium("Huge")


if __name__ == "__main__":
    unittest.main()
