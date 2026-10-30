from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check() -> int:
    from src import config
    from src.beyblade_data import all_specs
    from src.sound_synth import SOUND_BUILDERS

    specs = all_specs()
    print(f"Project root: {config.PROJECT_ROOT}")
    print(f"Beyblades loaded: {', '.join(specs)}")
    missing = [name for name in SOUND_BUILDERS if not (config.SOUNDS_DIR / f"{name}.wav").exists()]
    print("Sound files: all present" if not missing else f"Sound files missing (will be synthesized at runtime): {missing}")
    try:
        import pygame

        print(f"pygame {pygame.version.ver} available")
    except ImportError:
        print("pygame is not installed - run: pip install -r requirements.txt")
        return 1
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return check()
    try:
        import pygame  # noqa: F401
    except ImportError:
        print("pygame is not installed. Run:  pip install -r requirements.txt")
        return 1
    from src.game import Game

    Game().run()
    return 0


if __name__ == "__main__": # Run the main.py file after setup
    sys.exit(main())
