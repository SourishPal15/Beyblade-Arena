import unittest

from src import config, combat
from src.collision import ContactTracker, overlapping, resolve_pair
from src.utilities import Vec2
from tests.helpers import make_battle, place, run


class CollisionTests(unittest.TestCase):
    def setUp(self):
        self.battle = make_battle("inferno_fang", "gale_phantom")
        self.a, self.b = self.battle.beyblades

    def test_overlap_detection(self):
        place(self.a, 0, 0)
        place(self.b, self.a.radius + self.b.radius - 1.0, 0)
        self.assertTrue(overlapping(self.a, self.b))
        place(self.b, self.a.radius + self.b.radius + 1.0, 0)
        self.assertFalse(overlapping(self.a, self.b))

    def test_head_on_conserves_momentum_and_separates(self):
        place(self.a, 0, 0)
        place(self.b, self.a.radius + self.b.radius - 1.0, 0)
        self.a.vel = Vec2(200, 0)
        self.b.vel = Vec2(-100, 0)
        ma, mb = self.a.effective_mass, self.b.effective_mass
        before = ma * self.a.vel.x + mb * self.b.vel.x
        result = resolve_pair(self.a, self.b)
        after = ma * self.a.vel.x + mb * self.b.vel.x
        self.assertAlmostEqual(before, after, places=6)
        self.assertGreater(result.closing, 0)
        self.assertLess((self.a.vel - self.b.vel).dot(result.normal), 0)
        self.assertGreaterEqual((self.b.pos - self.a.pos).length(), self.a.radius + self.b.radius - 1e-6)

    def test_heavier_beyblade_is_displaced_less(self):
        heavy = make_battle("titan_breaker", "gale_phantom")
        a, b = heavy.beyblades
        place(a, 0, 0)
        place(b, a.radius + b.radius - 1.0, 0)
        a.vel = Vec2(150, 0)
        b.vel = Vec2(-150, 0)
        resolve_pair(a, b)
        self.assertLess(abs(a.vel.x - 150), abs(b.vel.x + 150))

    def test_no_stuck_overlap_from_same_position(self):
        place(self.a, 0, 0)
        place(self.b, 0, 0)
        ContactTracker().process([self.a, self.b], config.PHYSICS_DT)
        self.assertGreaterEqual(self.a.pos.distance_to(self.b.pos), self.a.radius + self.b.radius - 1e-6)

    def test_impact_and_ram_fire_once_per_contact(self):
        tracker = ContactTracker()
        place(self.a, 0, 0)
        place(self.b, self.a.radius + self.b.radius - 1.0, 0)
        self.a.vel = Vec2(300, 0)
        first = tracker.process([self.a, self.b], config.PHYSICS_DT)[0]
        self.assertTrue(first.impact)
        self.assertGreater(first.ram_ab, 0.0)
        place(self.b, self.a.radius + self.b.radius - 1.0, 0)
        self.a.vel = Vec2(300, 0)
        second = tracker.process([self.a, self.b], config.PHYSICS_DT)[0]
        self.assertFalse(second.impact)
        self.assertEqual(second.ram_ab, 0.0)

    def test_continuous_contact_does_not_spam_impacts(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        a, b = battle.beyblades
        place(a, 0, 0)
        place(b, 60, 0)
        a.vel = Vec2(300, 0)
        battle.set_input(a, Vec2(1, 0), False)
        run(battle, 1.0)
        collisions = [e for e in battle.drain_events() if e.kind == "collision"]
        self.assertLessEqual(len(collisions), 5)

    def test_ram_damage_hits_opponent_not_teammate(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        a, b = battle.beyblades
        hp_before = b.hp
        amount = combat.ram_damage(a, b, 250.0)
        self.assertGreater(combat.apply_damage(battle, b, amount, a, "ram"), 0)
        self.assertLess(b.hp, hp_before)
        battle2 = make_battle("inferno_fang", None, mode="1v2", difficulty="Hard")
        ai1, ai2 = battle2.beyblades[1], battle2.beyblades[2]
        self.assertEqual(ai1.team, ai2.team)
        self.assertFalse(battle2.are_opponents(ai1, ai2))
        place(ai1, 0, 0)
        place(ai2, ai1.radius + ai2.radius - 2.0, 0)
        ai1.vel = Vec2(300, 0)
        hp = (ai1.hp, ai2.hp)
        run(battle2, 0.5)
        self.assertEqual((ai1.hp, ai2.hp), hp)

    def test_frozen_beyblade_is_immovable(self):
        place(self.a, 0, 0)
        place(self.b, self.a.radius + self.b.radius - 1.0, 0)
        self.b.add_effect("frozen", 6.0, drain_mult=1.2)
        self.a.vel = Vec2(300, 0)
        start = self.b.pos.copy()
        resolve_pair(self.a, self.b)
        self.assertEqual(self.b.vel.length(), 0.0)
        self.assertEqual(self.b.pos.x, start.x)
        self.assertLess(self.a.vel.x, 300)

    def test_contact_does_not_damage_every_frame(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        a, b = battle.beyblades
        place(a, 0, 0)
        place(b, a.radius + b.radius - 1.0, 0)
        run(battle, 0.5)
        damage_events = [e for e in battle.drain_events() if e.kind == "damage" and e.data["damage_kind"] != "grind"]
        self.assertEqual(damage_events, [])


if __name__ == "__main__":
    unittest.main()
