from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from src import config
from src.beyblade import Beyblade
from src.utilities import Vec2, clamp

if TYPE_CHECKING:
    from src.battle import Battle


def defence_factor(defence: float) -> float:
    return 100.0 / (100.0 + max(0.0, defence))


def impact_factor(relative_speed: float) -> float:
    low, high = config.IMPACT_FACTOR_RANGE
    return clamp(relative_speed / config.REFERENCE_IMPACT_SPEED, low, high)


def standard_damage(attacker: Beyblade, defender: Beyblade, relative_speed: float) -> float:
    raw = (
        config.STANDARD_BASE_DAMAGE
        * (attacker.attack / 100.0)
        * defence_factor(defender.defence)
        * impact_factor(relative_speed)
    )
    low, high = config.STANDARD_DAMAGE_RANGE
    return clamp(raw, low, high) if attacker.attack > 0.0 else 0.0


def ram_damage(attacker: Beyblade, defender: Beyblade, approach_speed: float) -> float:
    raw = (
        config.RAM_BASE_DAMAGE
        * (attacker.attack / 100.0)
        * defence_factor(defender.defence)
        * impact_factor(approach_speed)
    )
    low, high = config.RAM_DAMAGE_RANGE
    return clamp(raw, low, high) if attacker.attack > 0.0 else 0.0


def apply_damage(
    battle: "Battle", target: Beyblade, amount: float, source: Optional[Beyblade] = None, kind: str = "hit"
) -> float:
    if amount <= 0.0 or not target.alive or target.invulnerable or not battle.combat_enabled:
        return 0.0
    actual = min(target.hp, amount)
    target.hp -= actual
    target.hp = clamp(target.hp, 0.0, target.max_hp)
    target.cancel_recovery()
    target.recover_block = config.DAMAGE_RECOVER_BLOCK
    if kind != "grind" or actual > 0.0:
        battle.emit("damage", target.pos, target=target.uid, amount=actual, damage_kind=kind)
    return actual


def heal(target: Beyblade, amount: float) -> float:
    if amount <= 0.0 or not target.alive:
        return 0.0
    new_hp = min(target.max_hp, target.hp + amount)
    gained = new_hp - target.hp
    target.hp = new_hp
    return gained


def check_action(battle: "Battle", b: Beyblade, action: str) -> Tuple[bool, str]:
    if not battle.combat_enabled or not b.alive:
        return False, "inactive"
    if action == "recover":
        if b.frozen:
            return False, "frozen"
        if b.stamina >= b.max_stamina - 1e-9:
            return False, "full_stamina"
        if b.dash_timer > 0.0 or b.attack_window > 0.0 or b.restore_lock > 0.0:
            return False, "busy"
        return True, ""
    if action in ("dash", "attack", "special") and b.frozen:
        return False, "frozen"
    if b.cooldowns.get(action, 0.0) > 0.0:
        return False, "cooldown"
    if action in ("dash", "attack") and b.restore_lock > 0.0:
        return False, "busy"
    if action == "attack" and b.attack <= 0.0:
        return False, "no_attack"
    if action == "restore":
        if b.hp >= b.max_hp - 1e-9:
            return False, "full_hp"
        if b.dash_timer > 0.0:
            return False, "busy"
    if action == "special":
        ok, reason = b.ability.validate(battle, b)
        if not ok:
            return False, reason
    if not b.can_afford(action):
        return False, "stamina"
    return True, ""


def resolve_attack_hit(battle: "Battle", attacker: Beyblade, target: Beyblade) -> float:
    offset = target.pos - attacker.pos
    normal = offset.normalized() if not offset.is_zero() else Vec2(1.0, 0.0)
    relative_speed = max(0.0, (attacker.vel - target.vel).dot(normal))
    damage = standard_damage(attacker, target, relative_speed)
    dealt = apply_damage(battle, target, damage, attacker, "attack")
    if not target.frozen:
        knock = config.ATTACK_KNOCKBACK * (attacker.attack / 100.0) * impact_factor(relative_speed) / target.effective_mass
        target.vel = target.vel + normal * knock
    attacker.vel = attacker.vel - normal * (config.ATTACK_KNOCKBACK * 0.25 / attacker.effective_mass)
    battle.emit(
        "attack_hit", target.pos - normal * target.radius, attacker=attacker.uid, target=target.uid,
        intensity=clamp(relative_speed / config.REFERENCE_IMPACT_SPEED, 0.5, 1.5), damage=dealt,
    )
    return dealt
