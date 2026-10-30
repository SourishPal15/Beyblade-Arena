# Controls

All gameplay bindings live in `KEY_BINDINGS` in `src/config.py`.

## In battle

| Key | Action | Stamina cost |
| --- | --- | --- |
| W / A / S / D | Steer (acceleration and momentum, diagonals normalised) | none |
| Left Shift | Dash (1 s cooldown) | 10% of max |
| Space | Standard attack (0.7 s cooldown) | 20% of max |
| Q | Signature ability (12-18 s cooldown, see README) | 75% of max |
| E | Restore HP: +50% of max HP (10 s cooldown) | 75% of max |
| R (hold) | Recover stamina: +20% of max per second, you stand still | none |
| Esc | Pause menu | none |

Dash, attack, ability and restore are one-shot: holding the key does nothing extra.
Recovery stops as soon as you steer, act, or take damage.

## Launch sequence (start of every round)

| Key | Action |
| --- | --- |
| A / D or Left / Right | Adjust launch direction (up to 75 degrees either side of the centre) |
| Space (hold) | Charge the launcher. Only works after LET IT RIP! |
| Space (release) | Launch |

Release inside the SWEET SPOT marker for a speed bonus. Above 93% the launch wobbles. A key held
down before LET IT RIP! does not count: release it and press again. If you never launch, the launcher
fires on its own after 6 seconds at the minimum power.

## Menus

Mouse click/hover, or Up/Down/Left/Right (also W/A/S/D), Enter to confirm, Esc to go back.
Name entry: type, Backspace to delete, Enter to confirm (max 16 characters).
