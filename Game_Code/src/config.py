from __future__ import annotations

import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
SOUNDS_DIR = ASSETS_DIR / "sounds"
BEYBLADE_DATA_FILE = DATA_DIR / "beyblades.json"

GAME_TITLE = "Beyblade Arena"
WINDOW_SIZE = (1280, 720)
MIN_WINDOW_SIZE = (960, 600)
FPS = 60

PHYSICS_HZ = 120
PHYSICS_DT = 1.0 / PHYSICS_HZ
MAX_FRAME_TIME = 0.25
MAX_STEPS_PER_FRAME = int(MAX_FRAME_TIME * PHYSICS_HZ) + 2

STADIUM_RADII = {"Small": 220.0, "Medium": 320.0, "Large": 420.0}
DEFAULT_STADIUM = "Medium"
STADIUM_RIM_WIDTH = 40.0
STADIUM_DESCRIPTIONS = {
    "Small": "Fast and aggressive. Little room to run, high wall pressure.",
    "Medium": "Balanced. Space for dashes, abilities and evasion.",
    "Large": "Tactical. Long approaches and room to reposition.",
}

MODES = {
    "1v1": {"opponents": 1, "stadiums": ("Small", "Medium", "Large")},
    "1v2": {"opponents": 2, "stadiums": ("Medium", "Large")},
    "1v3": {"opponents": 3, "stadiums": ("Large",)},
}
DIFFICULTIES = ("Easy", "Medium", "Hard")
DEFAULT_DIFFICULTY = "Medium"
ROUNDS_OPTIONS = (3, 5, 7)
DEFAULT_ROUNDS_TO_WIN = 3

PLAYER_NAME_MAX = 16
DEFAULT_PLAYER_NAME = "Player"

PREP_TIME = 1.6
COUNTDOWN_STEPS = 3
COUNTDOWN_STEP_TIME = 0.8
LAUNCH_TIMEOUT = 6.0
FLIGHT_MIN_TIME = 0.6
FLIGHT_MAX_TIME = 1.8
FLIGHT_SETTLE_FRACTION = 0.85
ATTACH_TIME = 1.0
RELEASE_ANIM_TIME = 0.45
CHARGE_TIME = 1.5
AIM_RATE = math.radians(70.0)
LAUNCH_ANGLE_MAX = math.radians(75.0)
LAUNCH_POWER_FLOOR = 0.30
LAUNCH_SPEED_FLOOR = 0.35
SWEET_SPOT = (0.72, 0.88)
SWEET_SPOT_BONUS = 1.18
OVERCHARGE_THRESHOLD = 0.93
OVERCHARGE_JITTER = math.radians(9.0)
LAUNCH_START_SPIN = 0.45
LAUNCH_SPIN_RAMP = 1.0
LAUNCH_EDGE_OFFSET = 30.0
ROUND_END_TIME = 3.2
MATCH_END_TIME = 4.0

ACTION_COST_FRACTION = {"dash": 0.10, "attack": 0.20, "special": 0.75, "restore": 0.75}
ACTION_COOLDOWN = {"dash": 1.0, "attack": 0.7, "restore": 10.0}
ACTION_ORDER = ("special", "restore", "attack", "dash")
RESTORE_HP_FRACTION = 0.50
RECOVERY_RATE = 0.20
PASSIVE_DRAIN_RATE = 0.006
FROZEN_DRAIN_MULT = 1.20
POISON_DRAIN_MULT = 1.15

DASH_TIME = 0.25
ATTACK_WINDOW = 0.30
ATTACK_REACH = 14.0
ATTACK_LUNGE = 260.0
ATTACK_KNOCKBACK = 330.0
RESTORE_LOCK = 0.35
RECOVER_LOCK = 0.30
DAMAGE_RECOVER_BLOCK = 0.60

SPEED_PER_STAT = 2.5
BASE_DRAG = 1.6
RECOVERY_DAMPING = 5.0
OVERSPEED_DECAY = 3.0
MAX_ABSOLUTE_SPEED = 900.0

SPIN_DECAY = 0.0085
SPIN_ELIMINATION = 0.15
LOW_SPIN = 0.35
SPIN_LOSS_COLLISION = 0.00020
SPIN_LOSS_WALL = 0.00012
SPIN_VISUAL_RATE = 1.0

WALL_RESTITUTION = 0.65
MIN_IMPACT_SPEED = 35.0
IMPACT_COOLDOWN = 0.25
RAM_MIN_SPEED = 90.0
RAM_COOLDOWN = 0.60
RAM_BASE_DAMAGE = 11.0
GRIND_DPS = 1.6
GRIND_SPIN_LOSS_PER_SECOND = 0.004
GRIND_EVENT_INTERVAL = 0.12
REFERENCE_IMPACT_SPEED = 200.0
IMPACT_FACTOR_RANGE = (0.75, 1.50)

STANDARD_BASE_DAMAGE = 10.0
STANDARD_DAMAGE_RANGE = (2.0, 28.0)
RAM_DAMAGE_RANGE = (1.0, 22.0)

SPAWN_RING_FRACTION = 0.60

AI_INTERVALS = {"Easy": (0.40, 0.65), "Medium": (0.22, 0.40), "Hard": (0.12, 0.25)}

MAX_PARTICLES = 1400
SHAKE_MAX = 14.0

SOUND_DEFAULT_VOLUME = 0.7

KEY_BINDINGS = {
    "up": "w",
    "left": "a",
    "down": "s",
    "right": "d",
    "dash": "left shift",
    "attack": "space",
    "special": "q",
    "restore": "e",
    "recover": "r",
    "launch": "space",
    "aim_left": "left",
    "aim_right": "right",
    "pause": "escape",
}

CONTROL_LABELS = [
    ("W / A / S / D", "Steer (acceleration and momentum)"),
    ("Left Shift", "Dash - 10% stamina"),
    ("Space", "Standard attack - 20% stamina"),
    ("Q", "Signature ability - 75% stamina"),
    ("E", "Restore HP (+50% max) - 75% stamina"),
    ("R (hold)", "Recover stamina - 20% per second, stand still"),
    ("Space (launch)", "Hold to charge the launcher, release to launch"),
    ("A / D or Left / Right (launch)", "Adjust launch direction"),
    ("Esc", "Pause"),
]

COLORS = {
    "background": "#191B20",
    "panel": "#25282E",
    "panel_alt": "#30343B",
    "text": "#F0F2F5",
    "text_dim": "#AEB5BF",
    "accent": "#E32636",
    "arena_main": "#292B30",
    "arena_inner": "#34373D",
    "arena_outer": "#191B20",
    "arena_border": "#626873",
    "arena_highlight": "#AEB5BF",
    "arena_marking": "#41454D",
    "hp": "#4FD17A",
    "hp_low": "#E3574F",
    "stamina": "#4FA8E8",
    "player_team": "#3FD0C9",
    "enemy_team": "#E8645A",
}
