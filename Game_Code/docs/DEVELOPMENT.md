# Development notes

## Architecture

The simulation core never imports pygame, so it can be tested headlessly.

* `src/config.py` - all tunable constants, key names, colours, paths.
* `data/beyblades.json` - per-Beyblade statistics, colours, ability parameters and launch traits.
* `src/beyblade_data.py` - loads the JSON into frozen `BeybladeSpec` objects.
* `src/beyblade.py` - `Beyblade` entity (state, status effects, cooldowns, stamina helpers).
* `src/stamina.py`, `src/physics.py`, `src/collision.py`, `src/combat.py` - rules.
* `src/abilities.py` - one `Ability` class per signature move plus world entities
  (`Vortex`, `Thorn`, `StoneWall`, `ThunderStrike`, `Gust`).
* `src/launch_system.py` - `Launcher` state machine and launch maths.
* `src/ai_opponent.py` - `AIController` with three `AIProfile`s.
* `src/battle.py` - `Battle`: phases, step order, actions, rounds, events.
* Presentation (needs pygame): `game.py`, `battle_scene.py`, `menus.py`, `battle_ui.py`,
  `visual_effects.py`, `beyblade_art.py`, `particles.py`, `camera.py`, `input_handler.py`,
  `sound_manager.py`, `ui_common.py`. `sound_synth.py` is pure Python.

Presentation reads state and consumes `Battle.drain_events()`; it never changes gameplay values.

## Active step order (`Battle._step_active`)

1. AI decisions and inputs. 2. Recovery state. 3. Queued actions in fixed priority
(special, restore, attack, dash). 4. World effects (vortex, thorns, walls, strikes).
5. Effect/cooldown/stamina ticks and poison. 6. Integration. 7. Beyblade collisions, ram, grind, venom touch.
8. Wall and stone-wall collisions. 9. Attack windows. 10. Eliminations. 11. Round end.

## Adding a Beyblade

1. Add an entry to `data/beyblades.json` (stats, colours, `ability.type`, `launch`).
2. Add an `Ability` subclass in `src/abilities.py` and register it in `ABILITY_TYPES`.
3. Add a design to `DESIGNS` in `src/beyblade_art.py`, a palette in `visual_effects.PALETTES`
   (and `EMIT_RATE`), a sound builder `ability_<id>` in `src/sound_synth.py`, an AI range in
   `ai_opponent.SPECIAL_RANGE`. Run `python -m src.sound_synth` to regenerate WAVs.

## Sounds

`python -m src.sound_synth` writes every WAV in `assets/sounds/`. If a file is missing the sound
manager synthesises it in memory; if audio cannot be initialised the game runs silently.

## Tests

`python -m pytest` or `python -m unittest discover -s tests -t .`. Tests are deterministic (seeded RNG,
fixed timestep) and cover physics, collisions, stamina, all eight abilities, the launch system,
rounds/modes, the AI and data/asset loading.
