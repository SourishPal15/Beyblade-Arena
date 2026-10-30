import math
import unittest

from src import combat, config
from src.abilities import Thorn, ThunderStrike, Vortex, thorn_damage
from src.beyblade_data import get_spec
from src.utilities import Vec2
from tests.helpers import make_battle, place, run


class InfernoTests(unittest.TestCase):
    def test_charged_state_buffs_and_expires_without_stacking(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        p = battle.player
        base_limit = p.speed_limit()
        base_attack = p.attack
        self.assertTrue(battle.perform_action(p, "special")[0])
        self.assertAlmostEqual(p.attack, base_attack * 1.3)
        ratio = p.speed_limit() / base_limit
        self.assertGreater(ratio, 1.1)
        self.assertLess(ratio, 1.3)
        self.assertEqual(battle.can_perform(p, "special")[1], "cooldown")
        p.cooldowns["special"] = 0.0
        p.stamina = 100.0
        ok, reason = battle.can_perform(p, "special")
        self.assertEqual((ok, reason), (False, "active"))
        self.assertEqual(p.cooldowns["special"], 0.0)
        run(battle, 7.5)
        self.assertTrue(p.charged)
        run(battle, 0.6)
        self.assertFalse(p.charged)
        self.assertAlmostEqual(p.attack, base_attack)

    def test_special_sets_cooldown(self):
        battle = make_battle("inferno_fang", "gale_phantom")
        battle.perform_action(battle.player, "special")
        self.assertEqual(battle.player.cooldowns["special"], 14.0)


class TidalTests(unittest.TestCase):
    def _vortex_battle(self):
        battle = make_battle("tidal_surge", "inferno_fang")
        owner, target = battle.beyblades
        place(owner, -150, 0)
        place(target, 0, 0)
        target.add_effect("frozen", 20.0, drain_mult=1.0)
        battle.add_world_effect(Vortex(owner, Vec2(0, 0), owner.spec.ability))
        return battle, owner, target

    def test_vortex_damage_is_time_based_not_frame_based(self):
        results = []
        for dt, steps in ((1 / 120, 120), (1 / 60, 60), (1 / 240, 240)):
            battle, _, target = self._vortex_battle()
            for _ in range(steps):
                battle.step(dt)
            results.append(target.max_hp - target.hp)
        expected = 0.25 * 100.0
        for lost in results:
            self.assertAlmostEqual(lost, expected, delta=expected * 0.03)

    def test_vortex_drains_stamina_quarter_per_second(self):
        battle, _, target = self._vortex_battle()
        before = target.stamina
        run(battle, 1.0)
        self.assertAlmostEqual(before - target.stamina, 25.0 + 0.6 * 1.2, delta=1.5)

    def test_vortex_pulls_slows_and_can_be_escaped(self):
        battle = make_battle("tidal_surge", "inferno_fang")
        owner, target = battle.beyblades
        place(owner, -200, -200)
        place(target, 60, 0)
        vortex = Vortex(owner, Vec2(0, 0), owner.spec.ability)
        battle.add_world_effect(vortex)
        run(battle, 0.2)
        self.assertTrue(target.has_effect("vortex_slow"))
        self.assertLess(target.pos.x, 60.0)
        battle.set_input(target, Vec2(1, 0), False)
        run(battle, 3.0)
        self.assertFalse(vortex.contains(target.pos))
        self.assertGreater(target.hp, 0)
        hp = target.hp
        run(battle, 0.5)
        self.assertEqual(target.hp, hp)

    def test_vortex_expires_and_ignores_owner(self):
        battle, owner, target = self._vortex_battle()
        place(owner, 10, 0)
        hp = owner.hp
        run(battle, 8.2)
        self.assertEqual(owner.hp, hp)
        self.assertEqual([e for e in battle.world_effects if isinstance(e, Vortex)], [])

    def test_activation_places_vortex_inside_stadium(self):
        battle = make_battle("tidal_surge", "inferno_fang", stadium="Small")
        owner = battle.player
        place(owner, 0, 190)
        battle.set_input(owner, Vec2(0, 1), False)
        battle.perform_action(owner, "special")
        vortex = next(e for e in battle.world_effects if isinstance(e, Vortex))
        self.assertLessEqual(vortex.center.length(), battle.stadium.radius - 40 + 1e-6)


class VerdantTests(unittest.TestCase):
    def setUp(self):
        self.params = get_spec("verdant_reaper").ability

    def test_distance_damage_formula(self):
        base = self.params["base_damage"]
        self.assertAlmostEqual(thorn_damage(self.params, 0), base)
        self.assertAlmostEqual(thorn_damage(self.params, 125), base * 1.5)
        self.assertAlmostEqual(thorn_damage(self.params, 250), base * 2.0)
        self.assertAlmostEqual(thorn_damage(self.params, 900), base * 2.0)

    def _setup(self, target_hp):
        battle = make_battle("verdant_reaper", "gale_phantom")
        owner, target = battle.beyblades
        place(owner, -200, 0)
        place(target, 0, 0)
        target.hp = target_hp
        owner.hp = 50.0
        return battle, owner, target

    def test_lifesteal_uses_actual_damage_and_slows(self):
        battle, owner, target = self._setup(5.0)
        thorn = Thorn(owner, target.pos.copy(), Vec2(), self.params, set())
        thorn.travelled = 400
        thorn.update(battle, 0.001)
        self.assertEqual(target.hp, 0.0)
        self.assertAlmostEqual(owner.hp, 52.5)
        self.assertAlmostEqual(target.effects["thorn_slow"].data["speed_mult"], 0.7)
        self.assertFalse(thorn.alive)

    def test_lifesteal_cannot_overheal(self):
        battle, owner, target = self._setup(100.0)
        owner.hp = owner.max_hp - 1.0
        thorn = Thorn(owner, target.pos.copy(), Vec2(), self.params, set())
        thorn.travelled = 400
        thorn.update(battle, 0.001)
        self.assertEqual(owner.hp, owner.max_hp)

    def test_same_volley_hits_target_once(self):
        battle, owner, target = self._setup(100.0)
        group = set()
        first = Thorn(owner, target.pos.copy(), Vec2(), self.params, group)
        second = Thorn(owner, target.pos.copy(), Vec2(), self.params, group)
        first.update(battle, 0.001)
        hp = target.hp
        second.update(battle, 0.001)
        self.assertEqual(target.hp, hp)
        self.assertTrue(second.alive)

    def test_activation_spawns_fan_that_lasts_four_seconds(self):
        battle, owner, target = self._setup(100.0)
        place(target, 0, -250)
        target.add_effect("frozen", 20.0, drain_mult=1.0)
        owner.aim_override = Vec2(1, 0)
        battle.perform_action(owner, "special")
        thorns = [e for e in battle.world_effects if isinstance(e, Thorn)]
        self.assertEqual(len(thorns), 5)
        run(battle, 4.2)
        self.assertEqual([e for e in battle.world_effects if isinstance(e, Thorn)], [])


class TitanTests(unittest.TestCase):
    def _setup(self):
        battle = make_battle("titan_breaker", "gale_phantom")
        owner, target = battle.beyblades
        place(owner, 0, 0)
        place(target, 120, 0)
        target.add_effect("frozen", 30.0, drain_mult=1.0)
        battle.perform_action(owner, "special")
        return battle, owner, target

    def test_four_walls_do_not_trap_owner(self):
        battle = make_battle("titan_breaker", "gale_phantom")
        owner = battle.player
        place(owner, 0, 0)
        place(battle.beyblades[1], 0, -250)
        battle.perform_action(owner, "special")
        walls = [e for e in battle.world_effects if e.kind == "stone_wall"]
        self.assertEqual(len(walls), 4)
        run(battle, 0.4)
        for wall in walls:
            left, top, right, bottom = wall.rect()
            cx = min(max(owner.pos.x, left), right)
            cy = min(max(owner.pos.y, top), bottom)
            self.assertGreater(math.hypot(owner.pos.x - cx, owner.pos.y - cy), owner.radius)

    def test_wall_hit_damages_once_and_halves_defence_once(self):
        battle, owner, target = self._setup()
        base_defence = target.defence
        run(battle, 0.6)
        self.assertAlmostEqual(target.defence, base_defence * 0.5)
        hp = target.hp
        self.assertLess(hp, target.max_hp)
        run(battle, 1.5)
        self.assertAlmostEqual(target.defence, base_defence * 0.5)
        damage = [e for e in battle.drain_events() if e.kind == "stone_hit"]
        self.assertEqual(len(damage), 1)

    def test_walls_expire_after_ten_seconds_and_defence_resets_next_round(self):
        battle, owner, target = self._setup()
        run(battle, 0.6)
        run(battle, 9.5)
        self.assertEqual([e for e in battle.world_effects if e.kind == "stone_wall"], [])
        target.reset_for_round(target.pos)
        self.assertEqual(target.defence, get_spec("gale_phantom").defence)

    def test_walls_never_extend_outside_arena(self):
        battle = make_battle("titan_breaker", "gale_phantom", stadium="Small")
        owner = battle.player
        place(owner, 150, 0)
        place(battle.beyblades[1], -150, 0)
        battle.perform_action(owner, "special")
        for wall in battle.world_effects:
            if wall.kind != "stone_wall":
                continue
            left, top, right, bottom = wall.rect()
            for x, y in ((left, top), (right, top), (left, bottom), (right, bottom)):
                self.assertLessEqual(math.hypot(x, y), battle.stadium.radius + 1.0)


class ThunderTests(unittest.TestCase):
    def test_stamina_steal_transfers_exactly(self):
        battle = make_battle("thunder_blitz", "gale_phantom")
        owner, target = battle.beyblades
        owner.stamina, target.stamina = 20.0, 80.0
        strike = ThunderStrike(owner, target, owner.spec.ability)
        strike.update(battle, 0.4)
        self.assertAlmostEqual(owner.stamina, 80.0)
        self.assertAlmostEqual(target.stamina, 20.0)
        self.assertTrue(owner.has_effect("speed_boost"))

    def test_steal_is_capped_by_free_capacity(self):
        battle = make_battle("thunder_blitz", "gale_phantom")
        owner, target = battle.beyblades
        owner.stamina, target.stamina = 50.0, 100.0
        total = owner.stamina + target.stamina
        ThunderStrike(owner, target, owner.spec.ability).update(battle, 0.4)
        self.assertAlmostEqual(owner.stamina, 95.0)
        self.assertAlmostEqual(owner.stamina + target.stamina, total)

    def test_speed_boost_doubles_limit_for_five_seconds_without_stacking(self):
        battle = make_battle("thunder_blitz", "gale_phantom")
        owner, target = battle.beyblades
        limit = owner.speed_limit()
        owner.add_effect("speed_boost", 5.0, speed_mult=2.0)
        self.assertAlmostEqual(owner.speed_limit(), limit * 2.0)
        owner.add_effect("speed_boost", 5.0, speed_mult=2.0)
        self.assertAlmostEqual(owner.speed_limit(), limit * 2.0)
        run(battle, 5.1)
        self.assertFalse(owner.has_effect("speed_boost"))

    def test_requires_valid_living_enemy_and_charges_nothing_otherwise(self):
        battle = make_battle("thunder_blitz", "gale_phantom")
        owner, target = battle.beyblades
        target.alive = False
        ok, reason = battle.perform_action(owner, "special")
        self.assertEqual((ok, reason), (False, "no_target"))
        self.assertEqual(owner.stamina, owner.max_stamina)

    def test_never_targets_teammates(self):
        battle = make_battle("thunder_blitz", None, mode="1v2", difficulty="Hard")
        owner = battle.player
        enemy = battle.nearest_opponent(owner)
        self.assertNotEqual(enemy.team, owner.team)
        ally_strike = ThunderStrike(battle.beyblades[1], battle.beyblades[2], get_spec("thunder_blitz").ability)
        stamina = battle.beyblades[2].stamina
        ally_strike.update(battle, 0.5)
        self.assertEqual(battle.beyblades[2].stamina, stamina)

    def test_full_activation_flow(self):
        battle = make_battle("thunder_blitz", "gale_phantom")
        owner, target = battle.beyblades
        target.stamina = 80.0
        self.assertTrue(battle.perform_action(owner, "special")[0])
        run(battle, 0.5)
        self.assertLess(target.stamina, 30.0)
        self.assertTrue(owner.has_effect("speed_boost"))


class GaleTests(unittest.TestCase):
    def test_gust_pushes_opponents_away_and_repositions_caster(self):
        battle = make_battle("gale_phantom", "inferno_fang")
        owner, target = battle.beyblades
        place(owner, 0, 0)
        place(target, 100, 0)
        owner.aim_override = Vec2(-1, 0)
        self.assertTrue(battle.perform_action(owner, "special")[0])
        self.assertGreater(target.vel.x, 100.0)
        self.assertLess(owner.vel.x, -400.0)
        self.assertTrue(owner.has_effect("repositioning"))
        run(battle, 1.0)
        self.assertLessEqual(owner.pos.length(), battle.stadium.radius - owner.radius + 1e-6)
        self.assertGreater(owner.hp, 0)
        self.assertFalse(owner.invulnerable)

    def test_gust_ignores_teammates_and_out_of_range(self):
        battle = make_battle("gale_phantom", None, mode="1v2", difficulty="Hard")
        owner, a, b = battle.beyblades
        place(owner, 0, 0)
        place(a, 100, 0)
        place(b, 300, 0)
        battle.perform_action(owner, "special")
        self.assertGreater(a.vel.x, 0)
        self.assertEqual(b.vel.length(), 0.0)


class FrostTests(unittest.TestCase):
    def test_freezes_every_opponent_for_six_seconds(self):
        battle = make_battle("frostbite_requiem", None, mode="1v3", stadium="Large", difficulty="Easy")
        owner = battle.player
        self.assertTrue(battle.perform_action(owner, "special")[0])
        foes = battle.opponents_of(owner)
        self.assertEqual(len(foes), 3)
        self.assertTrue(all(f.frozen for f in foes))
        self.assertFalse(owner.frozen)
        run(battle, 5.9)
        self.assertTrue(all(f.frozen for f in foes))
        run(battle, 0.3)
        self.assertFalse(any(f.frozen for f in foes))

    def test_frozen_cannot_act_but_can_be_damaged(self):
        battle = make_battle("frostbite_requiem", "inferno_fang")
        owner, target = battle.beyblades
        battle.perform_action(owner, "special")
        for action in ("dash", "attack", "special"):
            self.assertEqual(battle.can_perform(target, action), (False, "frozen"))
        place(target, 50, 50)
        battle.set_input(target, Vec2(1, 0), False)
        run(battle, 1.0)
        self.assertEqual(target.pos.x, 50)
        self.assertGreater(combat.apply_damage(battle, target, 5.0, owner), 0)

    def test_freeze_is_not_extended_by_recast(self):
        battle = make_battle("frostbite_requiem", "inferno_fang")
        owner, target = battle.beyblades
        battle.perform_action(owner, "special")
        run(battle, 4.0)
        remaining = target.effects["frozen"].remaining
        owner.ability.activate(battle, owner)
        self.assertAlmostEqual(target.effects["frozen"].remaining, remaining, places=6)

    def test_frozen_drain_multiplier(self):
        battle = make_battle("frostbite_requiem", "inferno_fang")
        battle.perform_action(battle.player, "special")
        self.assertAlmostEqual(battle.beyblades[1].drain_multiplier, 1.2)


class VenomTests(unittest.TestCase):
    def test_invulnerable_zero_attack_and_expires(self):
        battle = make_battle("venom_viper", "inferno_fang")
        owner, foe = battle.beyblades
        self.assertTrue(battle.perform_action(owner, "special")[0])
        self.assertEqual(owner.attack, 0.0)
        self.assertEqual(combat.apply_damage(battle, owner, 50.0, foe), 0.0)
        self.assertEqual(owner.hp, owner.max_hp)
        self.assertEqual(battle.can_perform(owner, "attack"), (False, "no_attack"))
        run(battle, 8.1)
        self.assertFalse(owner.venomous)
        self.assertGreater(combat.apply_damage(battle, owner, 10.0, foe), 0.0)

    def test_touch_poisons_with_time_based_damage(self):
        battle = make_battle("venom_viper", "inferno_fang")
        owner, foe = battle.beyblades
        place(owner, 0, 0)
        place(foe, owner.radius + foe.radius - 1.0, 0)
        foe.add_effect("frozen", 60.0, drain_mult=1.0)
        owner.add_effect("venomous", 8.0)
        battle.step(config.PHYSICS_DT)
        self.assertTrue(foe.poisoned)
        place(foe, 300, 0)
        foe.hp = foe.max_hp
        run(battle, 5.2)
        self.assertFalse(foe.poisoned)
        lost = foe.max_hp - foe.hp
        self.assertAlmostEqual(lost, 0.03 * foe.max_hp * 5.0, delta=foe.max_hp * 0.03)

    def test_poison_slows_and_raises_drain(self):
        battle = make_battle("venom_viper", "inferno_fang")
        foe = battle.beyblades[1]
        limit = foe.speed_limit()
        foe.add_effect("poison", 5.0, drain_mult=1.15, speed_mult=0.8, rate=0.04)
        self.assertAlmostEqual(foe.speed_limit(), limit * 0.8)
        self.assertAlmostEqual(foe.drain_multiplier, 1.15)

    def test_no_poison_without_active_state_or_on_teammates(self):
        battle = make_battle("venom_viper", "inferno_fang")
        owner, foe = battle.beyblades
        place(owner, 0, 0)
        place(foe, owner.radius + foe.radius - 1.0, 0)
        battle.step(config.PHYSICS_DT)
        self.assertFalse(foe.poisoned)

    def test_state_does_not_pass_through_wall(self):
        battle = make_battle("venom_viper", "inferno_fang")
        owner = battle.player
        owner.add_effect("venomous", 8.0)
        place(owner, 0, 0)
        battle.set_input(owner, Vec2(1, 0), False)
        run(battle, 4.0)
        self.assertLessEqual(owner.pos.length(), battle.stadium.radius - owner.radius + 1e-6)
        self.assertGreater(owner.vel.length() + owner.pos.length(), 0)


class CooldownTests(unittest.TestCase):
    def test_every_ability_applies_its_own_cooldown_and_blocks_recast(self):
        for spec_id in ("inferno_fang", "tidal_surge", "verdant_reaper", "titan_breaker", "thunder_blitz",
                        "gale_phantom", "frostbite_requiem", "venom_viper"):
            battle = make_battle(spec_id, "gale_phantom" if spec_id != "gale_phantom" else "inferno_fang")
            p = battle.player
            self.assertTrue(battle.perform_action(p, "special")[0], spec_id)
            self.assertEqual(p.cooldowns["special"], get_spec(spec_id).ability_cooldown)
            self.assertGreaterEqual(p.cooldowns["special"], 12.0)
            self.assertLessEqual(p.cooldowns["special"], 18.0)
            p.stamina = p.max_stamina
            self.assertEqual(battle.perform_action(p, "special")[1], "cooldown")


if __name__ == "__main__":
    unittest.main()
