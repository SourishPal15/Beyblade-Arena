from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src import abilities, combat, config, physics
from src.abilities import Gust, StoneWall, Thorn, ThunderStrike, Vortex, WorldEffect
from src.beyblade import Beyblade
from src.beyblade_data import all_specs
from src.collision import ContactResult, ContactTracker
from src.launch_system import Launcher
from src.stadium import Stadium
from src.utilities import Vec2, clamp, sanitize_name


@dataclass
class BattleConfig:
    beyblade_id: str
    mode: str = "1v1"
    stadium: str = config.DEFAULT_STADIUM
    difficulty: str = config.DEFAULT_DIFFICULTY
    player_name: str = config.DEFAULT_PLAYER_NAME
    rounds_to_win: int = config.DEFAULT_ROUNDS_TO_WIN
    seed: Optional[int] = None

    def validate(self) -> None:
        if self.mode not in config.MODES:
            raise ValueError(f"Unknown mode: {self.mode}")
        if self.stadium not in config.MODES[self.mode]["stadiums"]:
            raise ValueError(f"Stadium {self.stadium} is not available in mode {self.mode}")
        if self.difficulty not in config.DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {self.difficulty}")
        if self.rounds_to_win not in config.ROUNDS_OPTIONS:
            raise ValueError(f"Unsupported rounds to win: {self.rounds_to_win}")
        if self.beyblade_id not in all_specs():
            raise ValueError(f"Unknown Beyblade: {self.beyblade_id}")


@dataclass
class Event:
    kind: str
    pos: Optional[Vec2] = None
    data: dict = field(default_factory=dict)


class Battle:
    def __init__(self, cfg: BattleConfig, player_ai: bool = False) -> None:
        cfg.validate()
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.stadium = Stadium(cfg.stadium)
        self.opponent_count = int(config.MODES[cfg.mode]["opponents"])
        self.team_mode = cfg.difficulty == "Hard" and self.opponent_count >= 2
        self.beyblades: List[Beyblade] = []
        self.player: Beyblade
        self.controllers: Dict[int, object] = {}
        self.world_effects: List[WorldEffect] = []
        self.events: List[Event] = []
        self.contacts = ContactTracker()
        self.team_last_special: Dict[int, float] = {}
        self._grind_emitted: Dict[Tuple[int, int], float] = {}
        self.launchers: Dict[int, Launcher] = {}
        self.launch_inputs: Dict[int, Tuple[bool, float]] = {}
        self.launch_timer = 0.0
        self.flight_timer = 0.0
        self._countdown_tick = -1
        self.time = 0.0
        self.accumulator = 0.0
        self.phase = "prep"
        self.phase_timer = config.PREP_TIME
        self.round_number = 0
        self.round_winner: Optional[int] = None
        self.round_draw = False
        self.match_winner: Optional[int] = None
        self._build_participants(player_ai)
        self.scores: Dict[int, int] = {b.team: 0 for b in self.beyblades}
        self.start_round()

    @property
    def combat_enabled(self) -> bool:
        return self.phase == "active"

    @property
    def rounds_to_win(self) -> int:
        return self.cfg.rounds_to_win

    def _build_participants(self, player_ai: bool) -> None:
        from src.ai_opponent import AIController

        specs = all_specs()
        player_spec = specs[self.cfg.beyblade_id]
        pool = [spec for spec_id, spec in specs.items() if spec_id != player_spec.id]
        opponents = self.rng.sample(pool, self.opponent_count)
        positions = self.stadium.spawn_positions(1 + self.opponent_count)
        player_label = sanitize_name(self.cfg.player_name, config.PLAYER_NAME_MAX, config.DEFAULT_PLAYER_NAME)
        self.player = Beyblade(player_spec, 0, 0, player_label, True, positions[0])
        self.beyblades.append(self.player)
        for index, spec in enumerate(opponents, start=1):
            team = 1 if self.team_mode else index
            self.beyblades.append(Beyblade(spec, index, team, spec.name, False, positions[index]))
        for b in self.beyblades:
            b.ability = abilities.create_ability(b.spec)
            if not b.is_player or player_ai:
                self.controllers[b.uid] = AIController(b, self.cfg.difficulty, random.Random(self.rng.random()))

    def alive_beyblades(self) -> List[Beyblade]:
        return [b for b in self.beyblades if b.alive]

    def are_opponents(self, a: Beyblade, b: Beyblade) -> bool:
        return a.uid != b.uid and a.team != b.team

    def opponents_of(self, b: Beyblade) -> List[Beyblade]:
        return [o for o in self.beyblades if o.alive and o.team != b.team]

    def allies_of(self, b: Beyblade) -> List[Beyblade]:
        return [o for o in self.beyblades if o.alive and o.team == b.team and o.uid != b.uid]

    def nearest_opponent(self, b: Beyblade) -> Optional[Beyblade]:
        candidates = self.opponents_of(b)
        if not candidates:
            return None
        return min(candidates, key=lambda o: (o.pos - b.pos).length_sq())

    def aim_direction(self, b: Beyblade) -> Vec2:
        if b.aim_override is not None and not b.aim_override.is_zero():
            return b.aim_override.normalized()
        if not b.steer.is_zero(1e-3):
            return b.steer.normalized()
        if b.vel.length() > 30.0:
            return b.vel.normalized()
        return b.facing.normalized()

    def hostile_vortex_at(self, b: Beyblade) -> Optional[Vortex]:
        for effect in self.world_effects:
            if isinstance(effect, Vortex) and effect.owner.team != b.team and effect.contains(b.pos):
                return effect
        return None

    def emit(self, kind: str, pos: Optional[Vec2] = None, **data) -> None:
        self.events.append(Event(kind, pos, data))

    def drain_events(self) -> List[Event]:
        events, self.events = self.events, []
        return events

    def add_world_effect(self, effect: WorldEffect) -> None:
        self.world_effects.append(effect)

    def set_input(self, b: Beyblade, move: Vec2, recover: bool) -> None:
        if not self.combat_enabled or not b.alive:
            b.steer = Vec2()
            b.recover_input = False
            return
        b.steer = move.normalized() if move.length() > 1e-6 else Vec2()
        b.recover_input = recover

    def request_action(self, b: Beyblade, action: str) -> bool:
        if not self.combat_enabled or not b.alive:
            return False
        b.pending.add(action)
        return True

    def can_perform(self, b: Beyblade, action: str) -> Tuple[bool, str]:
        return combat.check_action(self, b, action)

    def start_round(self) -> None:
        self.round_number += 1
        self.world_effects.clear()
        self.contacts.reset()
        self.team_last_special.clear()
        self._grind_emitted.clear()
        self.launchers.clear()
        self.launch_inputs.clear()
        positions = self.stadium.launch_positions(len(self.beyblades))
        for b, pos in zip(self.beyblades, positions):
            b.reset_for_round(pos)
            base_angle = (self.stadium.center - pos).angle()
            b.facing = (self.stadium.center - pos).normalized()
            self.launchers[b.uid] = Launcher(b.spec, base_angle, random.Random(self.rng.random()))
        for controller in self.controllers.values():
            controller.reset()
        self.round_winner = None
        self.round_draw = False
        self.launch_timer = 0.0
        self.flight_timer = 0.0
        self.phase = "prep"
        self.phase_timer = config.PREP_TIME
        self._countdown_tick = -1
        self.emit("round_start", number=self.round_number)

    def in_play(self) -> List[Beyblade]:
        return [b for b in self.beyblades if b.alive and b.launched]

    def set_launch_input(self, b: Beyblade, hold: bool, aim: float) -> None:
        if self.phase in ("prep", "countdown", "launch") and not b.launched:
            self.launch_inputs[b.uid] = (hold, aim)

    def begin_active_immediately(self) -> None:
        positions = self.stadium.spawn_positions(len(self.beyblades))
        for b, pos in zip(self.beyblades, positions):
            b.pos = pos.copy()
            b.vel = Vec2()
            b.launched = True
            b.spin = 1.0
            b.spin_target = 1.0
            launcher = self.launchers[b.uid]
            launcher.state = "released"
            launcher.attach = 1.0
        self.phase = "active"
        self.launch_inputs.clear()

    def restart_match(self) -> None:
        self.round_number = 0
        self.scores = {team: 0 for team in self.scores}
        self.match_winner = None
        self.time = 0.0
        self.accumulator = 0.0
        self.events.clear()
        self.start_round()

    def advance(self, frame_dt: float) -> int:
        self.accumulator += clamp(frame_dt, 0.0, config.MAX_FRAME_TIME)
        steps = 0
        while self.accumulator >= config.PHYSICS_DT and steps < config.MAX_STEPS_PER_FRAME:
            self.step(config.PHYSICS_DT)
            self.accumulator -= config.PHYSICS_DT
            steps += 1
        if steps >= config.MAX_STEPS_PER_FRAME:
            self.accumulator = 0.0
        return steps

    def step(self, dt: float) -> None:
        if self.phase == "prep":
            self._step_prep(dt)
        elif self.phase == "countdown":
            self._step_countdown(dt)
        elif self.phase == "launch":
            self._step_launch(dt)
        elif self.phase == "flight":
            self._step_flight(dt)
        elif self.phase == "active":
            self._step_active(dt)
        elif self.phase == "round_over":
            self._step_round_over(dt)

    def _update_launchers(self, dt: float, can_charge: bool) -> None:
        for b in self.beyblades:
            launcher = self.launchers[b.uid]
            hold, aim = self.launch_inputs.get(b.uid, (False, 0.0))
            for name in launcher.update(dt, hold, aim, can_charge):
                if name == "attached":
                    self.emit("attached", b.pos.copy(), target=b.uid)
                elif name == "charge_start":
                    self.emit("charge_start", b.pos.copy(), target=b.uid)
            if not b.launched:
                b.spin = launcher.display_spin
                physics.spin_visual_only(b, dt)

    def _apply_releases(self) -> None:
        for b in self.beyblades:
            result = self.launchers[b.uid].take_release()
            if result is None or b.launched:
                continue
            b.launched = True
            b.vel = result.velocity.copy()
            b.facing = result.velocity.normalized()
            b.spin = config.LAUNCH_START_SPIN
            b.spin_target = result.spin
            self.emit(
                "launch", b.pos.copy(), target=b.uid, power=result.power, quality=result.quality,
                direction=result.velocity.normalized(),
            )

    def _step_prep(self, dt: float) -> None:
        self._update_launchers(dt, False)
        self.phase_timer -= dt
        if self.phase_timer <= 0.0 and all(l.attached for l in self.launchers.values()):
            self.phase = "countdown"
            self.phase_timer = config.COUNTDOWN_STEPS * config.COUNTDOWN_STEP_TIME
            self._countdown_tick = -1

    def _step_countdown(self, dt: float) -> None:
        self._update_launchers(dt, False)
        self.phase_timer -= dt
        tick = max(1, int(math.ceil(self.phase_timer / config.COUNTDOWN_STEP_TIME - 1e-9)))
        if self.phase_timer > 0.0 and tick != self._countdown_tick:
            self._countdown_tick = tick
            self.emit("countdown", number=tick)
        if self.phase_timer <= 0.0:
            self.phase = "launch"
            self.launch_timer = 0.0
            self.emit("let_it_rip")

    def _step_launch(self, dt: float) -> None:
        self.launch_timer += dt
        for b in self.beyblades:
            controller = self.controllers.get(b.uid)
            if controller is not None and not b.launched:
                controller.update_launch(self, dt)
        self._update_launchers(dt, True)
        if self.launch_timer >= config.LAUNCH_TIMEOUT:
            for launcher in self.launchers.values():
                launcher.force_release()
        self._apply_releases()
        self._flight_physics(dt)
        if all(b.launched for b in self.beyblades):
            self.phase = "flight"
            self.flight_timer = 0.0

    def _flight_physics(self, dt: float) -> None:
        flying = self.in_play()
        for b in flying:
            if b.spin < b.spin_target:
                b.spin = min(b.spin_target, b.spin + config.LAUNCH_SPIN_RAMP * dt)
            b.steer = Vec2()
            physics.integrate(b, dt)
        self._handle_contacts(self.contacts.process(flying, dt), dt)
        self._collide_boundaries()

    def _step_flight(self, dt: float) -> None:
        self.flight_timer += dt
        self._flight_physics(dt)
        limit = self.stadium.radius * config.FLIGHT_SETTLE_FRACTION
        inside = all(b.pos.length() <= limit for b in self.in_play())
        if (inside and self.flight_timer >= config.FLIGHT_MIN_TIME) or self.flight_timer >= config.FLIGHT_MAX_TIME:
            self.phase = "active"
            self.emit("battle_start")

    def _step_active(self, dt: float) -> None:
        self.time += dt
        for b in self.alive_beyblades():
            controller = self.controllers.get(b.uid)
            if controller is not None:
                controller.update(self, dt)
        self._update_recovery()
        self._process_actions()
        self._update_world_effects(dt)
        for b in self.alive_beyblades():
            for kind in b.tick(dt):
                self.emit("effect_end", b.pos.copy(), target=b.uid, effect=kind)
            if b.poisoned:
                rate = b.effects["poison"].data["rate"]
                combat.apply_damage(self, b, rate * b.max_hp * dt, None, "poison")
        for b in self.alive_beyblades():
            physics.integrate(b, dt)
        self._handle_contacts(self.contacts.process(self.in_play(), dt), dt)
        self._collide_boundaries()
        self._resolve_attack_windows()
        self._check_eliminations()
        self._check_round_end()

    def _step_round_over(self, dt: float) -> None:
        for b in self.beyblades:
            if b.alive:
                b.steer = Vec2()
                physics.integrate(b, dt)
                physics.resolve_arena_wall(b, self.stadium.radius)
            else:
                physics.spin_visual_only(b, dt)
        self.phase_timer -= dt
        if self.phase_timer <= 0.0:
            if self.match_winner is not None:
                self.phase = "match_over"
                self.emit("match_over", winner=self.match_winner)
            else:
                if self.round_draw:
                    self.round_number -= 1
                self.start_round()

    def _update_recovery(self) -> None:
        for b in self.alive_beyblades():
            ok, _ = combat.check_action(self, b, "recover")
            if ok and not b.recovering and b.stamina_ratio > 0.98:
                ok = False
            want = (
                b.recover_input and ok and b.steer.is_zero(1e-3)
                and b.recover_lock <= 0.0 and b.recover_block <= 0.0
            )
            if want and not b.recovering:
                b.recovering = True
                self.emit("recover_start", b.pos.copy(), target=b.uid)
            elif not want and b.recovering:
                b.recovering = False

    def _process_actions(self) -> None:
        for b in self.alive_beyblades():
            if not b.pending:
                continue
            requested = set(b.pending)
            b.pending.clear()
            for action in config.ACTION_ORDER:
                if action in requested:
                    self.perform_action(b, action)

    def perform_action(self, b: Beyblade, action: str) -> Tuple[bool, str]:
        ok, reason = combat.check_action(self, b, action)
        if not ok:
            self.emit("action_rejected", b.pos.copy(), target=b.uid, action=action, reason=reason)
            return False, reason
        cost = b.action_cost(action)
        b.spend_stamina(cost)
        b.cancel_recovery(config.RECOVER_LOCK)
        if action == "dash":
            self._do_dash(b)
        elif action == "attack":
            self._do_attack(b)
        elif action == "special":
            b.ability.activate(self, b)
            b.cooldowns["special"] = b.spec.ability_cooldown
            self.team_last_special[b.team] = self.time
            self.emit("ability", b.pos.copy(), caster=b.uid, spec_id=b.spec.id)
        elif action == "restore":
            gained = combat.heal(b, b.max_hp * config.RESTORE_HP_FRACTION)
            b.cooldowns["restore"] = config.ACTION_COOLDOWN["restore"]
            b.restore_lock = config.RESTORE_LOCK
            self.emit("restore", b.pos.copy(), target=b.uid, gained=gained)
        return True, ""

    def _do_dash(self, b: Beyblade) -> None:
        if not b.steer.is_zero(1e-3):
            direction = b.steer.normalized()
        elif b.vel.length() > 20.0:
            direction = b.vel.normalized()
        else:
            direction = b.facing.normalized()
        strength = b.spec.dash_strength
        b.vel = (b.vel + direction * strength).clamp_length(b.speed_limit() + strength)
        b.dash_timer = config.DASH_TIME
        b.cooldowns["dash"] = config.ACTION_COOLDOWN["dash"]
        self.emit("dash", b.pos.copy(), target=b.uid, direction=direction)

    def _do_attack(self, b: Beyblade) -> None:
        if not b.steer.is_zero(1e-3):
            direction = b.steer.normalized()
        elif b.vel.length() > 20.0:
            direction = b.vel.normalized()
        else:
            direction = b.facing.normalized()
        b.vel = b.vel + direction * (config.ATTACK_LUNGE / b.effective_mass)
        b.attack_window = config.ATTACK_WINDOW
        b.attack_hit = set()
        b.cooldowns["attack"] = config.ACTION_COOLDOWN["attack"]
        self.emit("attack", b.pos.copy(), target=b.uid, direction=direction)

    def _resolve_attack_windows(self) -> None:
        for attacker in self.alive_beyblades():
            if attacker.attack_window <= 0.0:
                continue
            for target in self.opponents_of(attacker):
                if target.uid in attacker.attack_hit:
                    continue
                reach = attacker.radius + target.radius + config.ATTACK_REACH
                if (target.pos - attacker.pos).length() <= reach:
                    attacker.attack_hit.add(target.uid)
                    combat.resolve_attack_hit(self, attacker, target)

    def _update_world_effects(self, dt: float) -> None:
        for effect in list(self.world_effects):
            effect.update(self, dt)
        self.world_effects = [e for e in self.world_effects if e.alive]

    def _handle_contacts(self, results: List[ContactResult], dt: float) -> None:
        for r in results:
            if self.are_opponents(r.a, r.b):
                self._grind(r, dt)
            if r.impact:
                self.emit(
                    "collision", r.point.copy(), a=r.a.uid, b=r.b.uid,
                    intensity=clamp(r.closing / config.REFERENCE_IMPACT_SPEED, 0.1, 2.0),
                )
            for attacker, defender in ((r.a, r.b), (r.b, r.a)):
                if not self.are_opponents(attacker, defender):
                    continue
                if attacker.venomous:
                    abilities.apply_poison(self, attacker, defender)
            for attacker, defender, speed in ((r.a, r.b, r.ram_ab), (r.b, r.a, r.ram_ba)):
                if speed <= 0.0 or not self.are_opponents(attacker, defender) or attacker.attack_window > 0.0:
                    continue
                combat.apply_damage(self, defender, combat.ram_damage(attacker, defender, speed), attacker, "ram")

    def _grind(self, r: ContactResult, dt: float) -> None:
        for attacker, defender in ((r.a, r.b), (r.b, r.a)):
            dps = config.GRIND_DPS * (attacker.attack / 100.0) * combat.defence_factor(defender.defence) * 2.0
            combat.apply_damage(self, defender, dps * dt, attacker, "grind")
        for b in (r.a, r.b):
            b.spin = max(0.0, b.spin * (1.0 - config.GRIND_SPIN_LOSS_PER_SECOND * dt))
        key = (min(r.a.uid, r.b.uid), max(r.a.uid, r.b.uid))
        if self.time - self._grind_emitted.get(key, -1.0) >= config.GRIND_EVENT_INTERVAL:
            self._grind_emitted[key] = self.time
            self.emit("grind", r.point.copy(), a=r.a.uid, b=r.b.uid)

    def _collide_boundaries(self) -> None:
        walls = [e for e in self.world_effects if isinstance(e, StoneWall)]
        for b in self.in_play():
            for wall in walls:
                hit, impact, _ = physics.resolve_rect(b, *wall.rect())
                if not hit:
                    continue
                if impact > 40.0 and b.wall_cooldown <= 0.0:
                    b.wall_cooldown = 0.15
                    self.emit("wall_hit", b.pos.copy(), target=b.uid, intensity=clamp(impact / 250.0, 0.2, 1.5), stone=True)
                if b.team != wall.owner.team and b.uid not in wall.hit_targets:
                    wall.hit_targets.add(b.uid)
                    self._stone_hit(wall, b)
            impact = physics.resolve_arena_wall(b, self.stadium.radius)
            if impact > 40.0 and b.wall_cooldown <= 0.0:
                b.wall_cooldown = 0.15
                self.emit("wall_hit", b.pos.copy(), target=b.uid, intensity=clamp(impact / 250.0, 0.2, 1.5), stone=False)

    def _stone_hit(self, wall: StoneWall, target: Beyblade) -> None:
        p = wall.params
        damage = float(p["damage"]) * combat.defence_factor(target.defence) * 2.0
        dealt = combat.apply_damage(self, target, damage, wall.owner, "stone")
        broken = wall.group["broken"]
        if target.uid not in broken:
            broken.add(target.uid)
            target.defence_mult *= float(p["defence_mult"])
        self.emit("stone_hit", target.pos.copy(), target=target.uid, damage=dealt)

    def _check_eliminations(self) -> None:
        for b in self.alive_beyblades():
            if b.hp <= 0.0:
                self._eliminate(b, "hp")
            elif b.spin <= config.SPIN_ELIMINATION and not b.invulnerable:
                self._eliminate(b, "spin")

    def _eliminate(self, b: Beyblade, reason: str) -> None:
        b.eliminate(self.time, reason)
        self.emit("eliminated", b.pos.copy(), target=b.uid, reason=reason)

    def _check_round_end(self) -> None:
        alive = self.alive_beyblades()
        teams = {b.team for b in alive}
        if len(teams) > 1:
            return
        self.round_draw = len(teams) == 0
        self.round_winner = None if self.round_draw else next(iter(teams))
        if self.round_winner is not None:
            self.scores[self.round_winner] += 1
            if self.scores[self.round_winner] >= self.rounds_to_win:
                self.match_winner = self.round_winner
        self.world_effects.clear()
        for b in self.beyblades:
            b.clear_effects()
            b.steer = Vec2()
            b.recover_input = False
            b.recovering = False
            b.pending.clear()
            b.attack_window = 0.0
            b.aim_override = None
        self.phase = "round_over"
        self.phase_timer = config.MATCH_END_TIME if self.match_winner is not None else config.ROUND_END_TIME
        self.emit("round_over", winner=self.round_winner, draw=self.round_draw, match_winner=self.match_winner)

    def player_score(self) -> int:
        return self.scores[self.player.team]

    def best_opposing_score(self) -> int:
        others = [score for team, score in self.scores.items() if team != self.player.team]
        return max(others) if others else 0
