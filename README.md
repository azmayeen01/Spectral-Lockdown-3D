# Spectral Lockdown 3D

A 3D survival-horror game built from scratch in **Python with PyOpenGL and GLUT** (no game engine). You are trapped in a haunted mansion: explore the rooms, collect items, banish the ghosts, then survive a timed showdown with the Warden to unlock the exit.

Built as the team project for **CSE423: Computer Graphics** at BRAC University (2025).

---

## Gameplay

The mansion is a central hallway leading to a top corridor, with four rooms on either side.

1. **Explore and collect.** Find the **Charm Item** in Room 2, a **Health Orb** in Room 3, and a **Time Shard** in Room 4. Room 4's door stays locked until you hold the Charm.
2. **Banish the ghosts.**
   - The **wispy ghost** roams the main hallway. Contact slows you for 3 seconds. Lure it out and banish it at the **magic circle in Room 3**.
   - The **segmented ghost** sleeps in Room 2 and chases you when you get close. Contact freezes you for 1 second. Banish it at the **Room 2 altar** using the Charm Item.
3. **Face the Warden.** Clearing both ghosts gives you the **Seal** and wakes the Warden in the top corridor. A **75-second timer** starts, and the Warden speeds up as time runs out. Each hit costs 2 HP. The Time Shard adds 15 seconds.
4. **Escape.** Banish the Warden with the Seal, then reach the now-unlocked exit door.

You start with **5 HP**. You lose if your HP reaches zero or the final timer runs out.

## Controls

| Key | Action |
|---|---|
| `W` `A` `S` `D` | Move forward / strafe left / back / strafe right |
| `←` `→` | Turn left / right |
| `↑` `↓` | Move the third-person camera closer / farther |
| `C` or right-click | Toggle first-person / third-person camera |
| `E` or left-click | Interact: pick up items, banish, open doors, use the exit |
| `R` | Restart the run |
| `V` | Cheat: freeze all ghosts and disable their damage |

## Features

- **Procedurally laid-out mansion** with a hallway, top corridor, four rooms, inner walls, ceilings and openable or locked doors
- **Collision detection** against walls and doorways, with zone tracking (which hallway or room the player is in)
- **Two camera modes:** first-person and a third-person camera clamped to the mansion bounds so it doesn't clip through walls
- **Ghost AI as a state machine:** sleep → roam → chase, with per-ghost speeds, chase radius and contact effects
- **Status effects:** slow, freeze, and damage cooldowns, shown live on the HUD (heads-up display)
- **Progression system:** inventory, item-gated doors, altar and magic-circle banishing, and a timed final phase with an accelerating boss
- **Hand-built 3D models** for the player, ghosts and Warden from OpenGL primitives, with simple animation
- **Frame-rate-independent updates** using a delta-time game loop

## Tech stack

- **Python 3**
- **PyOpenGL** (`OpenGL.GL`, `OpenGL.GLU`) for rendering
- **GLUT / freeglut** for the window, input and main loop

## Running the game

### Option 1: Use the bundled OpenGL files (Windows)

The project folder includes a copy of PyOpenGL with the freeglut DLLs (dynamic link libraries), so the game runs without installing anything extra on Windows.

```bash
git clone https://github.com/azmayeen01/Spectral-Lockdown-3D.git
cd "Spectral-Lockdown-3D/Spectral Lockdown 3D"
python Spectral_Lockdown_3D.py
```

Keep `Spectral_Lockdown_3D.py` in the same folder as the `OpenGL/` directory, or Python won't find the library.

### Option 2: Install PyOpenGL yourself

```bash
pip install PyOpenGL PyOpenGL_accelerate
```

- **Linux:** also install freeglut, e.g. `sudo apt install freeglut3-dev`
- **macOS:** GLUT ships with the system

Then run `python Spectral_Lockdown_3D.py`.

## Code structure

Everything lives in `Spectral_Lockdown_3D.py`, organised into sections:

| Section | Responsibility |
|---|---|
| Helpers | Math utilities: clamping, squared-distance checks, angle conversion |
| Globals and game state | Player, camera, health, inventory, timers; `init_game_state()` resets a run |
| Map and collision | Mansion layout, walls, doors, exit, collision resolution, zone detection |
| Player, camera and status effects | Input handling, movement, FPS/TPS cameras, slow/freeze effects, cheat mode |
| Ghost AI and progression | Ghost and Warden AI, items, banishing, Seal, final-phase timer |
| HUD | On-screen health, zone, effects, timer and messages |
| Game loop | `update_game()` runs each frame from GLUT's idle callback; `showScreen()` draws in a fixed order |

The other `.py` files (`Hello_openGL.py`, `Lets_draw_sth.py`, `3D_OpenGL_Intro.py`) are the course's introductory OpenGL examples and are not part of the game.

## Team

Developed by a team of three, with the code split by module:

| Member | Module |
|---|---|
| Azmayeen Aftab | Player control, cameras, status effects and cheat mode |
| Fatima Rahman | Ghost AI, items, banishing, progression and the final phase |
| Nazia Nissa | Map, mansion layout and collision |
