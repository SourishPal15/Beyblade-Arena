import math
import random
import unittest
from unittest import mock

from src import config
from src.battle import Battle, BattleConfig
from src.beyblade_data import get_spec
from src.launch_system import (
    ATTACHING, CHARGING, RELEASED, WAITING, Launcher, charge_power, clamp_aim, compute_launch,
    launch_speed, timing_quality,
)
from src.utilities import Vec2, from_angle

DT = config.PHYSICS_DT


def advance(launcher, seconds, hold=False, aim=0.0, can_charge=True):
    events = []
    for _ in range(int(round(seconds / DT))):
        events += launcher.update(DT, hold, aim, can_charge)
    return events


def ready_launcher(spec_id="inferno_fang"):
    launcher = Launcher(get_spec(spec_id), -math.pi / 2, random.Random(1))
    advance(launcher, config.ATTACH_TIME + 0.1)
    return launcher


class PowerAndVelocityTests(unittest.TestCase):
    def setUp(self):
        self.spec = get_spec("inferno_fang")

    def test_charge_is_progressive_and_capped(self):
        values = [charge_power(t / 10, self.spec) for t in range(0, 40)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(charge_power(0.0, self.spec), 0.0)
        self.assertEqual(charge_power(99.0, self.spec), 1.0)

    def test_thunder_charges_faster_than_inferno(self):
        self.assertGreater(charge_power(0.8, get_spec("thunder_blitz")), charge_power(0.8, self.spec))

    def test_speed_grows_with_power_below_overcharge(self):
        speeds = [launch_speed(self.spec, p / 20) for p in range(0, 14)]
        self.assertEqual(speeds, sorted(speeds))
        self.assertGreater(speeds[-1], speeds[0] * 2)

    def test_sweet_spot_bonus_and_quality_labels(self):
        self.assertEqual(timing_quality(0.8), "perfect")
        self.assertEqual(timing_quality(0.5), "good")
        self.assertEqual(timing_quality(0.1), "weak")
        self.assertEqual(timing_quality(1.0), "overcharged")
        self.assertGreater(launch_speed(self.spec, 0.72), launch_speed(self.spec, 0.71) * 1.05)

    def test_full_power_is_not_automatically_best(self):
        self.assertGreater(launch_speed(self.spec, 0.85), launch_speed(self.spec, 1.0))
        spread = []
        for seed in range(200):
            result = compute_launch(self.spec, 0.0, 0.0, 1.0, random.Random(seed))
            spread.append(result.velocity.angle())
        self.assertGreater(max(spread) - min(spread), math.radians(8))
        perfect = compute_launch(self.spec, 0.0, 0.0, 0.8, random.Random(1))
        self.assertAlmostEqual(perfect.velocity.angle(), 0.0, places=6)

    def test_stability_reduces_overcharge_wobble(self):
        def spread(spec_id):
            spec = get_spec(spec_id)
            angles = [compute_launch(spec, 0.0, 0.0, 1.0, random.Random(i)).velocity.angle() for i in range(300)]
            return max(angles) - min(angles)

        self.assertLess(spread("tidal_surge"), spread("inferno_fang"))

    def test_beyblade_specific_launch_traits_differ(self):
        speeds = {sid: launch_speed(get_spec(sid), 0.5) for sid in ("inferno_fang", "tidal_surge", "titan_breaker")}
        self.assertEqual(len(set(round(v, 3) for v in speeds.values())), 3)

    def test_direction_follows_aim_and_is_clamped_inward(self):
        base = -math.pi / 2
        for aim_deg in (-200, -75, -30, 0, 30, 75, 200):
            result = compute_launch(self.spec, base, math.radians(aim_deg), 0.8, random.Random(1))
            inward = from_angle(base)
            self.assertGreater(result.velocity.dot(inward), 0, aim_deg)
        self.assertAlmostEqual(clamp_aim(10.0), config.LAUNCH_ANGLE_MAX)
        result = compute_launch(self.spec, base, math.radians(30), 0.8, random.Random(1))
        self.assertAlmostEqual(result.angle, base + math.radians(30))
        self.assertAlmostEqual(result.velocity.length(), launch_speed(self.spec, 0.8))


class LauncherStateTests(unittest.TestCase):
    def test_attach_then_waiting(self):
        launcher = Launcher(get_spec("inferno_fang"), 0.0, random.Random(1))
        self.assertEqual(launcher.state, ATTACHING)
        events = advance(launcher, config.ATTACH_TIME * 0.5)
        self.assertEqual(launcher.state, ATTACHING)
        events += advance(launcher, config.ATTACH_TIME * 0.6)
        self.assertEqual(launcher.state, WAITING)
        self.assertIn("attached", events)

    def test_charge_then_release_launches_once(self):
        launcher = ready_launcher()
        advance(launcher, 0.1, hold=False)
        events = advance(launcher, 0.5, hold=True)
        self.assertEqual(launcher.state, CHARGING)
        self.assertIn("charge_start", events)
        self.assertGreater(launcher.power, 0.1)
        events = advance(launcher, 0.05, hold=False)
        self.assertIn("released", events)
        self.assertEqual(launcher.state, RELEASED)
        self.assertIsNotNone(launcher.take_release())
        self.assertIsNone(launcher.take_release())

    def test_duplicate_launch_is_impossible(self):
        launcher = ready_launcher()
        advance(launcher, 0.1)
        advance(launcher, 0.4, hold=True)
        advance(launcher, 0.05)
        launcher.take_release()
        events = advance(launcher, 3.0, hold=True)
        events += advance(launcher, 0.2, hold=False)
        events += advance(launcher, 1.0, hold=True)
        self.assertEqual(events, [])
        self.assertIsNone(launcher.take_release())
        self.assertFalse(launcher.force_release())

    def test_button_held_from_before_never_starts_charging(self):
        launcher = Launcher(get_spec("inferno_fang"), -math.pi / 2, random.Random(1))
        advance(launcher, config.ATTACH_TIME + 0.5, hold=True)
        advance(launcher, 2.0, hold=True)
        self.assertEqual(launcher.state, WAITING)
        advance(launcher, 0.1, hold=False)
        advance(launcher, 0.2, hold=True)
        self.assertEqual(launcher.state, CHARGING)

    def test_cannot_charge_before_launch_window(self):
        launcher = ready_launcher()
        advance(launcher, 0.1)
        advance(launcher, 1.0, hold=True, can_charge=False)
        self.assertEqual(launcher.state, WAITING)

    def test_aim_changes_within_limits(self):
        launcher = ready_launcher()
        advance(launcher, 0.5, aim=1.0)
        self.assertGreater(launcher.aim, 0.0)
        advance(launcher, 5.0, aim=1.0)
        self.assertAlmostEqual(launcher.aim, config.LAUNCH_ANGLE_MAX)
        advance(launcher, 10.0, aim=-1.0)
        self.assertAlmostEqual(launcher.aim, -config.LAUNCH_ANGLE_MAX)

    def test_power_stops_at_max_while_holding(self):
        launcher = ready_launcher()
        advance(launcher, 0.1)
        advance(launcher, 6.0, hold=True)
        self.assertEqual(launcher.power, 1.0)
        self.assertEqual(launcher.state, CHARGING)

    def test_force_release_uses_power_floor(self):
        launcher = ready_launcher()
        self.assertTrue(launcher.force_release())
        self.assertGreaterEqual(launcher.result.power, config.LAUNCH_POWER_FLOOR)


class BattleLaunchFlowTests(unittest.TestCase):
    def run_until(self, battle, phase, limit=30.0):
        for _ in range(int(limit / DT)):
            if battle.phase == phase:
                return True
            battle.step(DT)
        return False

    def test_full_sequence_in_order_and_no_combat_before_active(self):
        battle = Battle(BattleConfig("inferno_fang", seed=4), player_ai=True)
        seen = []
        kinds = []
        for _ in range(int(20 / DT)):
            if not seen or seen[-1] != battle.phase:
                seen.append(battle.phase)
            self.assertEqual(battle.combat_enabled, battle.phase == "active")
            if battle.phase == "active":
                break
            battle.step(DT)
            kinds += [e.kind for e in battle.drain_events()]
        self.assertEqual(seen, ["prep", "countdown", "launch", "flight", "active"])
        for kind in ("attached", "countdown", "let_it_rip", "charge_start", "launch", "battle_start"):
            self.assertIn(kind, kinds)
        self.assertLess(kinds.index("attached"), kinds.index("countdown"))
        self.assertLess(kinds.index("countdown"), kinds.index("let_it_rip"))
        self.assertLess(kinds.index("let_it_rip"), kinds.index("launch"))
        self.assertNotIn("damage", kinds)
        self.assertTrue(all(b.launched for b in battle.beyblades))
        for b in battle.beyblades:
            self.assertLess(b.pos.length(), battle.stadium.radius - b.radius + 1e-6)

    def test_countdown_numbers_three_two_one(self):
        battle = Battle(BattleConfig("inferno_fang", seed=4), player_ai=True)
        numbers = []
        for _ in range(int(8 / DT)):
            battle.step(DT)
            numbers += [e.data["number"] for e in battle.drain_events() if e.kind == "countdown"]
        self.assertEqual(numbers, [3, 2, 1])

    def test_countdown_timing_is_configurable(self):
        def time_to_launch_phase():
            battle = Battle(BattleConfig("inferno_fang", seed=4), player_ai=True)
            steps = 0
            while battle.phase != "launch" and steps < 20 / DT:
                battle.step(DT)
                steps += 1
            return steps * DT

        normal = time_to_launch_phase()
        with mock.patch.object(config, "COUNTDOWN_STEP_TIME", 0.3):
            fast = time_to_launch_phase()
        self.assertLess(fast, normal - 1.0)

    def test_player_charges_and_releases_through_battle(self):
        battle = Battle(BattleConfig("inferno_fang", seed=4))
        self.assertTrue(self.run_until(battle, "launch"))
        player = battle.player
        for _ in range(int(0.15 / DT)):
            battle.set_launch_input(player, False, 0.0)
            battle.step(DT)
        for _ in range(int(1.1 / DT)):
            battle.set_launch_input(player, True, 0.0)
            battle.step(DT)
        self.assertFalse(player.launched)
        battle.set_launch_input(player, False, 0.0)
        battle.step(DT)
        self.assertTrue(player.launched)
        self.assertGreater(player.vel.length(), 100)
        inward = (battle.stadium.center - player.pos).normalized()
        self.assertGreater(player.vel.normalized().dot(inward), 0.9)
        self.assertEqual(battle.launchers[player.uid].result.quality, "perfect")

    def test_idle_player_is_auto_launched_after_timeout(self):
        battle = Battle(BattleConfig("inferno_fang", seed=4))
        self.assertTrue(self.run_until(battle, "active", 40.0))
        self.assertTrue(battle.player.launched)

    def test_launch_input_ignored_during_active_battle(self):
        battle = make_active()
        before = battle.launchers[battle.player.uid].state
        battle.set_launch_input(battle.player, True, 1.0)
        self.assertNotIn(battle.player.uid, battle.launch_inputs)
        self.assertEqual(battle.launchers[battle.player.uid].state, before)

    def test_restart_resets_launch_state(self):
        battle = Battle(BattleConfig("inferno_fang", seed=4), player_ai=True)
        self.assertTrue(self.run_until(battle, "active"))
        battle.restart_match()
        self.assertEqual(battle.phase, "prep")
        for b in battle.beyblades:
            self.assertFalse(b.launched)
            self.assertEqual(b.vel.length(), 0.0)
            self.assertEqual(battle.launchers[b.uid].state, ATTACHING)
            self.assertAlmostEqual(b.pos.length(), battle.stadium.radius - config.LAUNCH_EDGE_OFFSET)
        self.assertEqual(battle.world_effects, [])
        self.assertTrue(self.run_until(battle, "active"))

    def test_ai_launch_follows_same_rules_and_differs_by_difficulty(self):
        def launches(difficulty):
            qualities, powers = [], []
            for seed in range(12):
                battle = Battle(BattleConfig("inferno_fang", "1v1", "Medium", difficulty, seed=seed), player_ai=True)
                self.run_until(battle, "flight")
                for b in battle.beyblades:
                    result = battle.launchers[b.uid].result
                    qualities.append(result.quality)
                    powers.append(result.power)
                    self.assertLessEqual(result.power, 1.0)
                    self.assertLessEqual(result.velocity.length(), launch_speed(b.spec, 1.0) * 1.2)
            return qualities, powers

        hard_q, hard_p = launches("Hard")
        easy_q, easy_p = launches("Easy")
        self.assertGreater(hard_q.count("perfect") / len(hard_q), 0.8)
        self.assertLess(easy_q.count("perfect") / len(easy_q), hard_q.count("perfect") / len(hard_q))
        self.assertGreater(max(easy_p) - min(easy_p), max(hard_p) - min(hard_p))

    def test_launch_positions_are_inside_the_arena(self):
        for name, radius in config.STADIUM_RADII.items():
            battle = Battle(BattleConfig("titan_breaker", "1v1", name))
            for b in battle.beyblades:
                self.assertLessEqual(b.pos.length(), radius - b.radius)


def make_active():
    battle = Battle(BattleConfig("inferno_fang", seed=4))
    battle.controllers.clear()
    battle.begin_active_immediately()
    return battle


if __name__ == "__main__":
    unittest.main()
