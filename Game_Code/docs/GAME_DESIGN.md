# Game design

Top-down 2D Beyblade battles on a circular blackish-grey stadium. The physics are a configurable
arcade model, not real-world Beyblade physics.

## Battle flow

`prep` (launchers attach) -> `countdown` (3, 2, 1) -> `launch` (LET IT RIP!, hold and release Space)
-> `flight` (launched Beyblades travel into the arena, combat disabled) -> `active` -> `round_over`
-> next round or `match_over`. This sequence runs at the start of every round. Combat, damage and
actions are only accepted in `active`.

## Launch system (`src/launch_system.py`)

* Launchers sit on the stadium rim. A Beyblade launches from there and its own velocity carries it in.
* Power rises linearly while Space is held and stops at 100%. Charge time is 1.5 s divided by the
  Beyblade's `charge_rate`.
* Speed = base speed x `launch.speed` x (0.35 + 0.65 x power). Power inside 72-88% (sweet spot) gives
  x1.18. Above 93% the direction wobbles; Beyblade `launch.stability` reduces the wobble.
* Direction is clamped to +/-75 degrees from the line to the stadium centre, so a launch can never
  point out of the arena. Opening strategies (centre, wide, edge) emerge from physics.
* Initial spin is 85-100% depending on power, ramping up during flight.
* The AI uses the same `Launcher` object and charge rules. Easy picks random power and aim, Hard aims
  at the opponent and releases inside the sweet spot, with a shorter reaction delay.
* A launcher cannot fire twice, and a button held before LET IT RIP! cannot start a charge.

## Physics

* Fixed timestep 120 Hz with an accumulator; frame time is clamped to 0.25 s and catch-up steps are
  capped. Rendering is separate.
* Steering applies acceleration along the input direction (extra lateral grip from `turn`). Drag is
  `v *= exp(-drag * dt)`. Speed above the current limit decays smoothly, so dashes and knockback work.
* Spin is separate from velocity: `spin *= exp(-decay * dt)`. Collisions and wall hits above 35 u/s
  cost a little spin. Low spin and low stamina reduce top speed.
* Circle-circle collisions use relative normal velocity, inverse effective masses (mass x collision
  resistance) and restitution. Overlap is corrected positionally. Frozen Beyblades are immovable.
* Wall rule (documented choice): the circular wall is solid, reflects with restitution 0.65 and there
  is no ring-out. The Beyblade centre stays within `radius - body radius`.

## Elimination

A Beyblade is eliminated when HP reaches 0, or spin falls to 15% (spin-out; deferred while Venom
Viper is invulnerable). Stamina at 0 does not eliminate; it only weakens the Beyblade and speeds spin
decay slightly.

## Damage

* Standard attack (Space): short lunge plus a 0.3 s hit window with reach 14 units. Damage =
  10 x attack/100 x 100/(100+defence) x impact factor (0.75-1.5, from relative speed / 200).
* Ram damage: moving into an opponent at 90+ u/s deals the same formula with base 11, once per 0.6 s
  per direction.
* Grind damage (design addition): sustained contact between opponents deals ~1.6 HP/s scaled by
  attack and defence. This prevents stalemates where two Beyblades press against each other with no
  stamina left. Teammates never damage each other.
* No damage outside the `active` phase. Visual effects never change gameplay state.

## Stamina

Cost = percent of max stamina x active cost multiplier. Passive drain is 0.6% of max per second,
multiplied by status multipliers (frozen 1.2, poison 1.15, Infernal Breaker 0.5; multiplicative).
Recovery (R) restores 20% of max per second and suspends drain; it cannot be used while frozen.

## Signature abilities

| Beyblade | Ability | Effect |
| --- | --- | --- |
| Inferno Fang | Infernal Breaker | 8 s: attack x1.3, speed x1.25, stamina costs and drain halved. Cannot be re-cast while active. |
| Tidal Surge | Abyssal Vortex | 8 s vortex (radius 105) 90 units ahead. Opponents inside lose 25% max HP and 25% max stamina per second, are pulled in and slowed to 55% speed. Steering out escapes it. |
| Verdant Reaper | Thornstorm | 5 ricocheting thorns for 4 s. Damage = 24 x (1 + travel/250, capped at +100%), scaled by defence, max 30. Slows 30% for 3 s, heals 50% of damage actually dealt. One hit per target per volley. |
| Titan Breaker | Earthshatter | Four solid walls (N/E/S/W) for 10 s. First contact per wall damages and halves that target's Defence for the round (once per activation). |
| Thunder Blitz | Thunder | Needs a living opponent. 0.35 s lock-on, then bolt: steals 75% of the target's stamina (capped by free capacity), 6 base damage, own speed x2 for 5 s. |
| Gale Phantom | Phantom Cyclone | Radius 170 gust pushes opponents outward (force / effective mass) while Gale bursts at 560 u/s. No invulnerability. |
| Frostbite Requiem | Absolute Zero | Freezes every opponent for 6 s: no move, dash, attack, ability or recover; drain x1.2. Still damageable. Not extended by re-casting. |
| Venom Viper | Venomous Touch | 8 s: Attack 0, invulnerable, can move. Touching an opponent poisons for 5 s (3% max HP/s, drain x1.15, speed x0.8). |

Abilities cost 75% stamina, have 12-18 s cooldowns (stored per Beyblade in `data/beyblades.json`)
and follow the same validation as every other action.

## Rounds and teams

* `rounds_to_win` is 3, 5 or 7: the number of round victories needed to win the match.
* 1v1 allows all stadiums, 1v2 Medium and Large, 1v3 Large only.
* Easy and Medium: every Beyblade is its own team (free-for-all). Hard with 2+ opponents: the AI
  Beyblades share one team against the player. Teams get no stat bonuses.
* Round ends when one team remains. Simultaneous elimination is a draw; it is replayed without score.

## AI

Difficulty only changes decisions: decision interval (Easy 0.40-0.65 s, Medium 0.22-0.40 s, Hard
0.12-0.25 s), aim error, target prediction, mistake chance, ability/attack/dash probability, stamina
and HP thresholds, wall margin and escape skill. Hard team members flank from different sides and
stagger abilities. The AI uses `battle.can_perform` before requesting an action.
