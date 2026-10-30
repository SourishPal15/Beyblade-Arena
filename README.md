# Beyblade Arena

A top-down 2D Beyblade battle game developed using Python and Pygame. The game features physics-based movement, real-time combat, stamina management, special abilities, AI opponents, and a launcher-based start sequence inspired by the Beyblade series.

## About the Project

Beyblade Arena is a playable game project that recreates the excitement of Beyblade battles in a 2D environment. Players can launch, control, and battle using elemental Beyblades, each with distinct statistics and abilities.

The game combines physics-based simulation, combat mechanics, resource management, and computer-controlled opponents to create a more interactive experience than a conventional arcade game.

All graphics are rendered procedurally, and sound effects are synthesised programmatically, eliminating the need for externally downloaded visual and audio assets.

## Why I Built This Project

I created this project to explore game development with Python and Pygame while building something more complex than a basic arcade game.

The project provided an opportunity to work with:

* Game physics, movement, momentum, and collision detection.
* Real-time input handling and responsive controls.
* Game state management, including menus, rounds, pauses, and results.
* Artificial intelligence with multiple difficulty levels.
* Combat systems involving health, stamina, cooldowns, and special abilities.
* Procedural graphics, particle effects, animations, and synthesised sound.
* Modular code organisation, configuration, and automated testing.

The goal was to combine these concepts into a complete, interactive game while improving my programming, problem-solving, and software development skills.

## Features

### Gameplay

* Launcher-based launch sequence with a countdown, aiming, charging, and release mechanics.
* Three battle modes: 1v1, 1v2, and 1v3 against computer opponents.
* Three AI difficulty levels: Easy, Medium, and Hard.
* Three stadium sizes: Small, Medium, and Large.
* Physics-based movement with momentum, friction, spin, collisions, and wall bounces.
* Health and stamina management.
* Multiple combat actions, including standard attacks, dashes, special abilities, health restoration, and stamina recovery.
* Cooldowns and stamina costs for combat actions.
* Configurable rounds-to-win options: 3, 5, or 7 round victories.

### Visuals and Audio

* Procedurally rendered graphics.
* Synthesised sound effects.
* Particle effects and movement trails.
* Screen-shake effects and visual feedback during combat.
* In-game HUD displaying relevant gameplay information.
* Pause menu and match results screen.
* Sound toggle and volume controls.

### Game Systems

* Modular architecture separating game systems and supporting components.
* External JSON configuration for Beyblade statistics.
* Dedicated modules for simulation, launching, AI, user interface, and rendering.
* Automated tests covering core gameplay mechanics.
* Command-line checks for verifying dependencies and game data.

## Video Demonstration

Watch the gameplay demonstration of Beyblade Arena, showcasing the launcher sequence, combat mechanics, special abilities, AI opponents, and overall gameplay.

**Gameplay Video:** 

https://github.com/user-attachments/assets/a14fc02f-bb2c-47c3-b9e0-d814490761c5

## Technologies Used

* **Python** — Core programming language.
* **Pygame** — Game window, input handling, rendering, and audio playback.
* **JSON** — Storage of game configuration and Beyblade statistics.
* **pytest** — Automated test execution.
* **Git** — Version control.

## Controls

### During a Battle

| Key           | Action                   |
| ------------- | ------------------------ |
| W / A / S / D | Steer the Beyblade       |
| Left Shift    | Dash                     |
| Space         | Attack                   |
| Q             | Activate special ability |
| E             | Restore health           |
| Hold R        | Recover stamina          |
| Esc           | Pause the game           |

### Launch Sequence

| Key                | Action              |
| ------------------ | ------------------- |
| A / D              | Aim the launch      |
| Left / Right Arrow | Aim the launch      |
| Hold Space         | Charge the launcher |
| Release Space      | Launch the Beyblade |

The launch sequence begins with a countdown. Once the launch prompt appears, charge the launcher and release at the appropriate time to launch.

## Project Structure

```text
Beyblade_Game/
│
├── .pytest_cache/
│
├── assets/
│   └── sounds/
│
├── data/
│   └── beyblades.json
│
├── docs/
│   ├── GAME_DESIGN.md
│   ├── CONTROLS.md
│   └── DEVELOPMENT.md
│
├── src/
│   ├── config and game configuration
│   ├── data loading
│   ├── simulation and physics
│   ├── launch system
│   ├── AI opponent logic
│   ├── user interface
│   └── rendering
│
├── tests/
│   ├── physics tests
│   ├── collision tests
│   ├── stamina tests
│   ├── ability tests
│   ├── launch tests
│   ├── round tests
│   ├── AI tests
│   └── asset tests
│
├── .gitignore
├── main.py
├── pytest.ini
├── README.md
└── requirements.txt
```

The `.pytest_cache/` directory is generated by pytest and is not required to run the game. It may be recreated when tests are executed.

## Installation

### Prerequisites

Make sure you have the following installed:

* Python 3.9 or newer.
* Visual Studio Code or another Python-compatible editor.
* Git, if you intend to clone the repository.

Python 3.12 was used during development.

### 1. Clone the Repository

If you are downloading the project from GitHub, open a terminal and run:

```bash
git clone <repository-url>
```

Replace `<repository-url>` with your repository's Git URL.

Alternatively, download the repository as a ZIP file and extract it.

### 2. Open the Project

Open Visual Studio Code and select:

**File → Open Folder → Beyblade_Game**

Open a terminal using **Terminal → New Terminal**.

Make sure the terminal is located in the project's root directory, where `main.py` and `requirements.txt` are present.

### 3. Create a Virtual Environment

On Windows, run:

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\activate
```

A successful activation typically displays `(.venv)` at the beginning of your terminal prompt.

### 4. Install Dependencies

Install the required Python packages:

```powershell
python -m pip install -r requirements.txt
```

Wait for the installation to finish before proceeding.

## Running the Game

From the project's root directory, execute:

```powershell
python main.py
```

The game should open in a separate window.

Use the menus to configure your match, select the battle mode and difficulty, and begin playing.

## Checking the Installation

The project includes a command-line check that verifies important components without opening the game window.

Run:

```powershell
python main.py --check
```

This check reports information about the loaded Beyblade data, sound files, and Pygame availability.

If the check reports an error, review the message and verify that the required dependencies and project files are available.

## Running Tests

The project includes automated tests for core gameplay mechanics.

Run the test suite with:

```powershell
python -m pytest
```

Alternatively, use Python's built-in unittest test runner:

```powershell
python -m unittest discover -s tests -t .
```

These tests help verify the behaviour of the simulation, collisions, stamina management, abilities, launching, rounds, AI, and asset handling.

**Note:** Automated tests primarily cover the core game logic. The Pygame interface, rendering, input handling, and audio playback may require additional manual testing.

## Sound Generation

The game uses synthesised sound effects. If you need to regenerate the sound files, run:

```powershell
python -m src.sound_synth
```

This step is optional when the generated sound files are already present.

## Configuration and Customisation

Some game settings can be modified through the project's configuration files.

* `src/config.py` — Game configuration and key bindings.
* `data/beyblades.json` — Beyblade statistics and balance values.
* `docs/GAME_DESIGN.md` — Game mechanics and design details.
* `docs/CONTROLS.md` — Detailed control reference.
* `docs/DEVELOPMENT.md` — Development notes and technical information.

Modifying configuration values allows you to experiment with gameplay balance and behaviour without redesigning the entire game.

## Current Status and Limitations

Beyblade Arena is an actively testable game project, but some aspects may need further refinement.

* The core simulation has an automated test suite.
* The Pygame interface, rendering, controls, and audio require further testing in a real game window.
* Gameplay balance may need adjustment based on actual matches.
* The stadium walls are solid, so elimination occurs through health depletion or spin-out rather than ring-out.
* Key bindings can be configured in the source code, but an in-game key-rebinding interface is not currently available.
* Additional improvements could include gameplay balancing, stadium hazards, and expanded configuration options.

## Future Improvements

Potential improvements include:

* Further balancing of gameplay mechanics and AI difficulty.
* Additional stadium hazards and environmental interactions.
* An in-game key-rebinding interface.
* Improved visual effects, animations, and audio feedback.
* Expanded gameplay modes and additional mechanics.
* More extensive testing of the graphical interface and real-time gameplay.

## License

This project is licensed under the **MIT License**.

You are free to use, copy, modify, merge, publish, distribute, sublicense, and sell copies of the software, subject to the conditions of the MIT License.

See the [LICENSE](LICENSE) file for the complete license text.

---

**Beyblade Arena** is a personal game development project built with Python and Pygame, combining interactive gameplay, physics simulation, AI, and procedural effects in a single application.
