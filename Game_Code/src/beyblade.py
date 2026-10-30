from __future__ import annotations

from typing import Dict, List, Optional, Set

from src import config, stamina
from src.beyblade_data import BeybladeSpec
from src.utilities import Vec2, clamp


class StatusEffect:
    __slots__ = ("kind", "remaining", "duration", "data")

    def __init__(self, kind: str, duration: float, data: Optional[dict] = None) -> None:
        self.kind = kind
        self.remaining = duration
        self.duration = duration
        self.data = data or {}


class Beyblade:
    def __init__(
        self,
        spec: BeybladeSpec,
        uid: int,
        team: int,
        label: str,
        is_player: bool = False,
        position: Optional[Vec2] = None,
    ) -> None:
        self.spec = spec
        self.uid = uid
        self.team = team
        self.label = label
        self.is_player = is_player
        self.ability = None
        self.aim_override: Optional[Vec2] = None
        self.steer = Vec2()
        self.recover_input = False
        self.pending: Set[str] = set()
        self.reset_for_round(position or Vec2())

    def reset_for_round(self, position: Vec2) -> None:
        spec = self.spec
        self.pos = position.copy()
        self.vel = Vec2()
        self.ext_accel = Vec2()
        self.facing = Vec2(0.0, -1.0)
        self.hp = spec.max_hp
        self.stamina = spec.max_stamina
        self.defence_mult = 1.0
        self.spin = 1.0
        self.angle = 0.0
        self.spin_dir = 1.0 if self.uid % 2 == 0 else -1.0
        self.angular_velocity = 0.0
        self.launched = False
        self.spin_target = 1.0
        self.alive = True
        self.eliminated_at: Optional[float] = None
        self.elimination_reason = ""
        self.effects: Dict[str, StatusEffect] = {}
        self.cooldowns: Dict[str, float] = {"dash": 0.0, "attack": 0.0, "restore": 0.0, "special": 0.0}
        self.attack_window = 0.0
        self.attack_hit: Set[int] = set()
        self.dash_timer = 0.0
        self.restore_lock = 0.0
        self.recover_lock = 0.0
        self.recover_block = 0.0
        self.recovering = False
        self.wall_cooldown = 0.0
        self.steer = Vec2()
        self.recover_input = False
        self.aim_override = None
        self.pending.clear()

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def max_hp(self) -> float:
        return self.spec.max_hp

    @property
    def max_stamina(self) -> float:
        return self.spec.max_stamina

    @property
    def mass(self) -> float:
        return self.spec.mass

    @property
    def radius(self) -> float:
        return self.spec.radius

    @property
    def friction(self) -> float:
        return self.spec.friction

    @property
    def turn(self) -> float:
        return self.spec.turn

    @property
    def spin_rate(self) -> float:
        return self.spec.spin_rate

    @property
    def effective_mass(self) -> float:
        return self.spec.mass * self.spec.collision_resistance

    @property
    def inverse_mass(self) -> float:
        if not self.alive or self.frozen:
            return 0.0
        return 1.0 / self.effective_mass

    def has_effect(self, kind: str) -> bool:
        return kind in self.effects

    @property
    def frozen(self) -> bool:
        return "frozen" in self.effects

    @property
    def poisoned(self) -> bool:
        return "poison" in self.effects

    @property
    def venomous(self) -> bool:
        return "venomous" in self.effects

    @property
    def invulnerable(self) -> bool:
        return "venomous" in self.effects

    @property
    def charged(self) -> bool:
        return "charged" in self.effects

    def add_effect(self, kind: str, duration: float, refresh: bool = True, **data: float) -> bool:
        existing = self.effects.get(kind)
        if existing is not None:
            if not refresh:
                return False
            existing.remaining = duration
            existing.duration = duration
            existing.data = data
            return False
        self.effects[kind] = StatusEffect(kind, duration, data)
        return True

    def remove_effect(self, kind: str) -> None:
        self.effects.pop(kind, None)

    def clear_effects(self) -> None:
        self.effects.clear()

    def _effect_product(self, key: str) -> float:
        value = 1.0
        for effect in self.effects.values():
            value *= effect.data.get(key, 1.0)
        return value

    @property
    def attack(self) -> float:
        if self.venomous:
            return 0.0
        return self.spec.attack * self._effect_product("attack_mult")

    @property
    def defence(self) -> float:
        return self.spec.defence * self.defence_mult

    @property
    def cost_multiplier(self) -> float:
        return self._effect_product("cost_mult")

    @property
    def drain_multiplier(self) -> float:
        value = self._effect_product("drain_mult")
        return value

    def action_cost(self, action: str) -> float:
        return stamina.action_cost(self.max_stamina, action, self.cost_multiplier)

    def can_afford(self, action: str) -> bool:
        return self.stamina + 1e-9 >= self.action_cost(action)

    def spend_stamina(self, amount: float) -> bool:
        if amount < 0 or self.stamina + 1e-9 < amount:
            return False
        self.stamina = max(0.0, self.stamina - amount)
        return True

    @property
    def stamina_ratio(self) -> float:
        return clamp(self.stamina / self.max_stamina, 0.0, 1.0)

    @property
    def hp_ratio(self) -> float:
        return clamp(self.hp / self.max_hp, 0.0, 1.0)

    @property
    def low_spin(self) -> bool:
        return self.spin < config.LOW_SPIN

    def performance_factor(self) -> float:
        stamina_part = 0.7 + 0.3 * clamp(self.stamina_ratio / 0.3, 0.0, 1.0)
        spin_range = config.LOW_SPIN + 0.15 - config.SPIN_ELIMINATION
        spin_part = 0.7 + 0.3 * clamp((self.spin - config.SPIN_ELIMINATION) / spin_range, 0.0, 1.0)
        return stamina_part * spin_part

    @property
    def base_speed(self) -> float:
        return self.spec.speed * config.SPEED_PER_STAT * self.performance_factor()

    def speed_limit(self) -> float:
        limit = self.base_speed * self._effect_product("speed_mult")
        for effect in self.effects.values():
            limit = max(limit, effect.data.get("limit", 0.0))
        return limit

    def steering_acceleration(self) -> float:
        boost = 1.0
        for effect in self.effects.values():
            boost *= max(1.0, effect.data.get("speed_mult", 1.0))
        return self.base_speed * boost * config.BASE_DRAG * self.friction * self.spec.accel_mult

    def can_steer(self) -> bool:
        return self.alive and not self.frozen and not self.recovering

    def tick(self, dt: float) -> List[str]:
        expired: List[str] = []
        for kind in list(self.effects):
            effect = self.effects[kind]
            effect.remaining -= dt
            if effect.remaining <= 0.0:
                del self.effects[kind]
                expired.append(kind)
        for key, value in self.cooldowns.items():
            self.cooldowns[key] = max(0.0, value - dt)
        self.attack_window = max(0.0, self.attack_window - dt)
        if self.attack_window == 0.0:
            self.attack_hit.clear()
        self.dash_timer = max(0.0, self.dash_timer - dt)
        self.restore_lock = max(0.0, self.restore_lock - dt)
        self.recover_lock = max(0.0, self.recover_lock - dt)
        self.recover_block = max(0.0, self.recover_block - dt)
        self.wall_cooldown = max(0.0, self.wall_cooldown - dt)
        if self.recovering:
            self.stamina = stamina.apply_recovery(self.stamina, self.max_stamina, dt)
        else:
            self.stamina = stamina.apply_drain(self.stamina, self.max_stamina, self.drain_multiplier, dt)
        return expired

    def cancel_recovery(self, lock: float = 0.0) -> None:
        self.recovering = False
        self.recover_lock = max(self.recover_lock, lock)

    def eliminate(self, time: float, reason: str) -> None:
        self.alive = False
        self.hp = max(0.0, self.hp)
        self.eliminated_at = time
        self.elimination_reason = reason
        self.recovering = False
        self.effects.clear()
        self.steer = Vec2()
        self.pending.clear()
        self.attack_window = 0.0
