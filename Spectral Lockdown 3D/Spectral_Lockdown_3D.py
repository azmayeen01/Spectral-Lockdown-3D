from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

import math, random, time

# ============= (1) HELPERS / MATH / UTILITIES  (Shared) =============

def clamp_value(v, lo, hi):
    # Out of boundary clamping
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def distance2_xy(ax, ay, bx, by):
    # Euclidean collision detection
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy

def now_seconds():
    # Time tracking
    return time.time()


# ============= (2) GLOBALS =============

w_width, w_height = 1000, 800
fovY = 120
quad = None

def init_game_state():
    #Initializes games
    m1_build_mansion_layout()
    m1_world_spawns_define_points()
    m1_define_room_triggers()
    m3_spawn_ghosts_initial()
    m3_spawn_items_and_mechanisms()

def reset_run():
    #Restarts game
    init_game_state()
    glutPostRedisplay()


# ============= (3) Member 1 - MAP / COLLISION =============

def m1_build_mansion_layout():
    # T-shaped hall, 4 rooms, walls and boundaries
    pass

def m1_define_room_triggers():
    # Room enter and leaving logic
    pass

def m1_collision_resolve_player_world():
    # Push back if against hitting a wall, use clamp
    pass

def m1_door_lock_unlock_system():
    """
    - locked/unlocked/openable rules
    - exit door gating (unlocks after final ghost banish)
    """
    pass

def m1_world_spawns_define_points():
    # Ghost, item, mechanism spawn points
    pass

def m1_draw_world_floor_and_walls():
    # Floors, walls, doors
    pass

def m1_draw_exit_door():
    # Difference in look of locked and unlocked door
    pass

def m1_draw_room_state_feedback():
    # Haunted vs safe room ?
    pass


# ============= (4) Member 2 — PLAYER CONTROL / CAMERA / STATUS EFFECTS / CHEAT =============

def m2_handle_keyboard_input(key, x, y):
    """
    - movement (WASD), rotation
    - interact key (banish/item pickup trigger)
    - camera toggle (FPS <-> TPS)
    - restart / debug toggles
    """
    pass

def m2_handle_special_keys(key, x, y):
    """
    Special keys (arrows):
    - camera angle/height adjustments
    """
    pass

def m2_handle_mouse_input(button, state, x, y):
    """
    - camera toggle on right click
    - interact/shoot placeholder (no combat, but can use as interact)
    """
    pass

def m2_update_player_movement():
    """
    - rotation + forward/back motion
    - integrates with Member 1 collision resolution
    """
    pass

def m2_camera_setup():
    """
    - FPS view (primary) (first person)
    - Close TPS (third person)
    """
    pass

def m2_camera_mode_rules():
    """
    - exploration mode vs chase mode adjustments
    - clamp camera so it doesn't clip into walls (logic + clamps)
    """
    pass

def m2_player_status_effect_system():
    """
    - slow, freeze, invert controls, camera drift/disorient
    - effect application + decay over time
    """
    pass

def m2_cheat_debug_system():
    """
    - freeze ghosts / show ghost states
    - disable effects
    - quick teleport-to-room (optional)
    """
    pass

def m2_draw_player_model_tps():
    """
    Draw player body model for TPS mode
    """
    pass

def m2_draw_player_fps_rig():
    """
    Draw FPS arms/rig model for FPS mode
    """
    pass


# ============= (5) Member 3 — GHOST AI / ITEMS / BANISH / PROGRESSION / FINAL =============

def m3_spawn_ghosts_initial():
    """
    Create 2-3 normal ghosts + their room assignments:
    - positions from Member 1 spawn points
    - unique ghost type tags
    """
    pass

def m3_spawn_final_warden_if_ready():
    """
    Spawn the Final Warden ghost after enough clears:
    - sets final phase active
    - starts countdown timer
    """
    pass

def m3_ghost_state_machine_update():
    """
    Ghost FSM per ghost:
    - idle/roam -> alert -> chase -> search -> retreat/reset
    - includes per-type behavior differences
    """
    pass

def m3_ghost_behavior_patrol():
    # Patrol logic for a ghost type
    pass

def m3_ghost_behavior_ambush():
    # Ambush logic for a ghost type
    pass

def m3_ghost_behavior_drifter():
    """Member 3: Hallway drifter pressure ghost behavior."""
    pass

def m3_final_warden_phase_logic():
    """
    Final boss multi-phase behavior:
    - phases triggered by time remaining or player actions
    - changes chase rules (not just speed)
    """
    pass

def m3_apply_ghost_effects_on_contact():
    """
    Detect ghost contact / proximity and apply effects:
    - decides WHICH effect to apply based on ghost type
    - triggers Member 2 timers/stacking
    """
    pass

def m3_spawn_items_and_mechanisms():
    """
    Item + banish mechanism spawns:
    - room-tied item placement
    - magic circle / altar spots
    - ensures correct item exists for correct ghost
    """
    pass

def m3_item_pickup_logic():
    """
    Player picks up items (proximity + interact key):
    - inventory update
    - feedback to player
    """
    pass

def m3_banish_interaction_logic():
    """
    Banish system:
    - validate: correct room + correct item + correct mechanism
    - optional: hold-in-circle timer or 2-step activation
    - banish success clears ghost + removes its effects
    """
    pass

def m3_room_clear_progression_update():
    """
    Update room state:
    - haunted -> cleared -> safe
    - informs Member 1 door unlocking / safe zones
    """
    pass

def m3_final_phase_timer_update():
    """
    Countdown logic during final phase:
    - timer decreases
    - escalations at milestones (behavior changes, locks, etc.)
    """
    pass

def m3_win_lose_evaluation():
    """
    Game end conditions (implemented as state machine, not just if-else):
    - lose: timer expired in final phase OR player health depleted
    - win: final warden banished + player reaches exit trigger
    """
    pass

def m3_draw_ghosts():
    """
    Draw ghosts (simple solids):
    - different shape cues per ghost type
    - optional: pulse/hover motion
    """
    pass

def m3_draw_items_and_mechanisms():
    """
    Draw items and banish circles/mechanisms:
    - visible enough for gameplay
    """
    pass


# ============= HUD and TEXT =============

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    # Texts
    pass

def draw_hud_overlay():
    # HUD
    pass


# ============= (7) UPDATE LOOP (Idle) =============

def update_game():
    m2_player_status_effect_system()
    m2_update_player_movement()
    m1_collision_resolve_player_world()
    m1_door_lock_unlock_system()
    m3_ghost_state_machine_update()
    m3_apply_ghost_effects_on_contact()
    m3_item_pickup_logic()
    m3_banish_interaction_logic()
    m3_room_clear_progression_update()
    m3_spawn_final_warden_if_ready()
    m3_final_phase_timer_update()
    m3_win_lose_evaluation()
    m2_camera_mode_rules()
    m2_cheat_debug_system()

def idle():
    update_game()
    glutPostRedisplay()


# ============= (8) DRAW LOOP (showScreen) — Draw in consistent order =============

def showScreen():
    """
    Display callback:
    - Clear buffers, set viewport
    - Member 2: setup camera
    - Member 1: draw world (floor/walls/doors/exit)
    - Member 3: draw ghosts, items, mechanisms
    - Member 2: draw player model (TPS) OR fps rig (FPS)
    - HUD text
    - Swap buffers
    """
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, w_width, w_height)

    setupCamera()

    # World first
    m1_draw_world_floor_and_walls()
    m1_draw_exit_door()
    m1_draw_room_state_feedback()

    # Entities
    m3_draw_items_and_mechanisms()
    m3_draw_ghosts()

    m2_draw_player_model_tps()
    m2_draw_player_fps_rig()

    glutSwapBuffers()


# ============= LISTENERS =============

def keyboardListener(key, x, y):
    # Reset
    if key == b'r' or key == b'R':
        reset_run()
        return

    # Forward to Member 2 input system
    m2_handle_keyboard_input(key, x, y)
    glutPostRedisplay()

def specialKeyListener(key, x, y):
    m2_handle_special_keys(key, x, y)
    glutPostRedisplay()

def mouseListener(button, state, x, y):
    """Dispatch to Member 2 mouse handler."""
    m2_handle_mouse_input(button, state, x, y)
    glutPostRedisplay()


# ============= CAMERA =============

def setupCamera():
    """Dispatch to Member 2 camera setup (FPS/TPS)."""
    m2_camera_setup()


# ============= MAIN =============

def main():
    """
    - GLUT init / window config
    - Create shared quadric if needed (group decides)
    - init_game_state()
    - Register callbacks: showScreen, keyboardListener, specialKeyListener, mouseListener, idle
    - main loop
    """
    global quad

    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(w_width, w_height)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"Spectral Lockdown (Skeleton)")

    quad = gluNewQuadric()

    # Initialize game state once
    init_game_state()

    # Register callbacks
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)

    glutMainLoop()


if __name__ == "__main__":
    main()
