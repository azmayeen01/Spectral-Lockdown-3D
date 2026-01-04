from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math, random, time

# ============= (1) HELPERS / MATH / UTILITIES  (Shared) =============

def clamp_value(v, lo, hi):                         # Out of boundary clamping
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def distance2_xy(ax, ay, bx, by):    # Euclidean collision detection
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy

def now_seconds():                   # Time tracking
    return time.time()

def deg_to_rad(d):
    return d * math.pi / 180.0

def forward_xy(yaw_deg):
    a = deg_to_rad(yaw_deg)
    return math.cos(a), math.sin(a)

# ============= (2) GLOBALS =============
w_width, w_height = 800, 600
fovY = 120
quad = None
g_length = 1000

HALL = {}
ROOMS = {}
WALLS = []
EXIT_DOOR = None
BOUNDS = None
DOORS = {}    
ROOM_STATE = {}
CURRENT_ZONE = ("hall", "stem")
PLAYER_ZONE = ("hall", "stem")  # cached zone-of-player for current frame
LAST_VALID_POS = [0.0, 0.0]
SPAWNS = {}
CEIL_H , SLOW_T, FREEZE_T, HURT_CD = 260.0, 0.0, 0.0, 0.0        
GAME_ITEMS = []
ALTARS = {}
INVENTORY = set()
FINAL_PHASE_ACTIVE = False
FINAL_PHASE_TIMER = 0.0
FINAL_WARDEN_BANISHED = False
SHADOW_ROOM_ID = None
SHADOW_ROOM_ACTIVE = False       # True after warden phase starts
SHADOW_ROOM_DONE = False         # True once player stayed long enough
SHADOW_ROOM_TIMER, SHADOW_REQUIRED_T = 0.0, 2.5

# ---------------- CHEAT MODE ----------------
CHEAT_FREEZE_GHOSTS = False      # Toggle: freeze all ghosts + warden AI
CHEAT_GHOST_NO_DAMAGE = True     # Optional: when frozen, ghosts also can't damage you
PLAYER_POS = [0.0, 0.0]     # x,y on floor
PLAYER_ROT = 90.0           # yaw degrees (0 = +X, 90 = +Y)
PLAYER_SPEED = 400
KEYS = {"w": False, "s": False, "a": False, "d": False}
CAM_MODE_FPS = 0
CAM_MODE_TPS = 1
camera_mode = CAM_MODE_FPS
TPS_BACK = 140.0
TPS_UP = 90.0
FPS_EYE_Z = 75.0
FPS_LOOK_DIST = 200.0
LAST_FRAME_TIME = 0.0
DT = 0.016  # fallback
PLAYER_HEALTH = 5
GAME_OVER = False
GAME_WIN = False
GAME_MESSAGE = ""

def init_game_state():
    global GAME_OVER, GAME_WIN, GAME_MESSAGE, PLAYER_HEALTH, LAST_FRAME_TIME, DT, PLAYER_ROT, camera_mode, SLOW_T, FREEZE_T, HURT_CD, GAME_ITEMS, ALTARS, INVENTORY, FINAL_PHASE_ACTIVE, FINAL_PHASE_TIMER, FINAL_WARDEN_BANISHED, WARDEN, WARDEN_VISIBLE, FINAL_START_TIME, KEYS, CHEAT_FREEZE_GHOSTS
    CHEAT_FREEZE_GHOSTS = False
    GAME_OVER = False
    GAME_WIN = False
    GAME_MESSAGE = ""
    PLAYER_HEALTH = 5
    PLAYER_ROT = 90.0
    KEYS["w"] = False; KEYS["s"] = False; KEYS["a"] = False; KEYS["d"] = False
    camera_mode = CAM_MODE_FPS
    SLOW_T, FREEZE_T, HURT_CD = 0.0, 0.0, 0.0   
    GAME_ITEMS = []
    ALTARS = {}
    INVENTORY = set()
    FINAL_PHASE_ACTIVE = False
    FINAL_PHASE_TIMER = 0.0
    FINAL_WARDEN_BANISHED = False
    WARDEN = None
    WARDEN_VISIBLE = False
    FINAL_START_TIME = now_seconds()

    globals()["SHADOW_ROOM_ID"] = None
    globals()["SHADOW_ROOM_ACTIVE"] = False
    globals()["SHADOW_ROOM_DONE"] = False
    globals()["SHADOW_ROOM_TIMER"] = 0.0
    if "SHADOW_REQUIRED_T" not in globals():
        globals()["SHADOW_REQUIRED_T"] = 2.5

    # Reset frame timing so DT doesn't jump on first frame after restart
    LAST_FRAME_TIME = 0.0
    DT = 0.016
    if "EXIT_SIDE" not in globals():
        globals()["EXIT_SIDE"] = "L"
    build_mansion_layout()
    world_spawns_define_points()

    ROOM_STATE.clear()
    for rid in ROOMS.keys():
        ROOM_STATE[rid] = "HAUNTED"

    if "stem" in HALL:
        x0, x1, y0, y1 = HALL["stem"]
        PLAYER_POS[0] = 0.5 * (x0 + x1)
        PLAYER_POS[1] = y0 + 160.0
    else:
        PLAYER_POS[0] = 0.0
        PLAYER_POS[1] = 0.0
    LAST_VALID_POS[0] = PLAYER_POS[0]
    LAST_VALID_POS[1] = PLAYER_POS[1]
    define_room_triggers()
    globals()["PLAYER_ZONE"] = get_player_zone(PLAYER_POS[0], PLAYER_POS[1])
    globals()["PLAYER_LAST_MOVE_T"] = now_seconds()
    spawn_ghosts_initial()
    spawn_items_and_mechanisms()

def reset_run():
    init_game_state()
    glutPostRedisplay()

# ============= (3) Member 1 - MAP / COLLISION =============
Z_FLOOR = 0.00; Z_STRIPES = 0.03; Z_OVERLAY = 0.06; Z_SKIRT = 0.09
EXIT_SIDE = "R"   # "L" or "R"

def point_in_rect(px, py, rect, eps=0.0):
    x0, x1, y0, y1 = rect
    return (px >= (x0 + eps) and px <= (x1 - eps) and py >= (y0 + eps) and py <= (y1 - eps))

def get_player_zone(px, py):
    if "stem" in HALL and point_in_rect(px, py, HALL["stem"], eps=0.0):
        return ("hall", "stem")
    if "cap" in HALL and point_in_rect(px, py, HALL["cap"], eps=0.0):
        return ("hall", "cap")
    room_eps = 0.25
    for rid, r in ROOMS.items():
        if point_in_rect(px, py, r, eps=room_eps):
            return ("room", rid)
    return ("none", None)

def build_mansion_layout():
    global HALL, ROOMS, WALLS, EXIT_DOOR, BOUNDS, DOORS
    margin = 90.0
    # Hall thickness
    hall_half = 110.0
    cap_h = 2.0 * hall_half
    # Door opening size (gap along y)
    door_half = 45.0
    # Mansion square inside the outer boundary
    mx0 = -g_length + margin
    mx1 = +g_length - margin
    my0 = -g_length + margin
    my1 = +g_length - margin
    BOUNDS = (mx0, mx1, my0, my1)
    # Cap hallway (top band full width)
    cap_y0 = my1 - cap_h
    cap_y1 = my1
    cap_rect = (mx0, mx1, cap_y0, cap_y1)
    # Stem hallway (center vertical)
    stem_x0 = -hall_half
    stem_x1 = +hall_half
    stem_y0 = my0
    stem_y1 = cap_y0
    stem_rect = (stem_x0, stem_x1, stem_y0, stem_y1)
    HALL = {"cap": cap_rect, "stem": stem_rect}
    # Rooms occupy left and right blocks below the cap
    left_x0, left_x1 = mx0, stem_x0
    right_x0, right_x1 = stem_x1, mx1
    mid_y = 0.5 * (my0 + cap_y0)
    ROOMS = {
        "1": (left_x0,  left_x1,  mid_y, cap_y0),  # left top
        "2": (left_x0,  left_x1,  my0,   mid_y),   # left bottom
        "3": (right_x0, right_x1, mid_y, cap_y0),  # right top
        "4": (right_x0, right_x1, my0,   mid_y),   # right bottom
    }
    # ------------------- Inner wall segments -------------------
    WALLS = []
    def add_h(y, x0, x1):
        if x1 > x0:
            WALLS.append(("H", y, x0, x1))

    def add_v(x, y0, y1):
        if y1 > y0:
            WALLS.append(("V", x, y0, y1))

    # T-junction line between cap and below (leave stem opening)
    add_h(cap_y0, mx0, stem_x0)
    add_h(cap_y0, stem_x1, mx1)
    # Stem side walls
    add_v(stem_x0, my0, cap_y0)
    add_v(stem_x1, my0, cap_y0)
    # Room divider lines (between top & bottom) for both sides
    add_h(mid_y, left_x0, left_x1)
    add_h(mid_y, right_x0, right_x1)
    # Room inner walls with DOOR GAP (we leave a gap in wall segments)
    for rid, (rx0, rx1, ry0, ry1) in ROOMS.items():
        midr = 0.5 * (ry0 + ry1)
        if rid in ("1", "2"):
            x_inner = left_x1  # = stem_x0
            add_v(x_inner, ry0, midr - door_half)
            add_v(x_inner, midr + door_half, ry1)
        else:
            x_inner = right_x0  # = stem_x1
            add_v(x_inner, ry0, midr - door_half)
            add_v(x_inner, midr + door_half, ry1)

    DOORS = {}
    door_z0 = 0.0
    door_z1 = 220.0
    for rid, (rx0, rx1, ry0, ry1) in ROOMS.items():
        midr = 0.5 * (ry0 + ry1)
        y0 = midr - door_half
        y1 = midr + door_half
        if rid in ("1", "2"):
            x_wall = left_x1
            x_draw = x_wall + 18.0
            DOORS[rid] = {
                "side": "L",
                "x_wall": x_wall,
                "x_draw": x_draw,
                "y0": y0, "y1": y1,
                "z0": door_z0, "z1": door_z1,
                "open": False,
                "locked": False
            }
        else:
            x_wall = right_x0
            x_draw = x_wall - 18.0
            DOORS[rid] = {
                "side": "R",
                "x_wall": x_wall,
                "x_draw": x_draw,
                "y0": y0, "y1": y1,
                "z0": door_z0, "z1": door_z1,
                "open": False,
                "locked": False
            }

    exit_midy = 0.5 * (cap_y0 + cap_y1)
    exit_gap_half = 55.0
    side = "L"
    ex = (mx1 if side == "R" else mx0)
    EXIT_DOOR = {
        "x": ex,
        "y0": exit_midy - exit_gap_half,
        "y1": exit_midy + exit_gap_half,
        "z0": 0.0,
        "z1": 220.0,
        "locked": True,
        "side": side
    }

def define_room_triggers():
    global CURRENT_ZONE
    zt, zid = get_player_zone(PLAYER_POS[0], PLAYER_POS[1])
    if zt == "none":
        return
    CURRENT_ZONE = (zt, zid)

def collision_resolve_player_world():
    global LAST_VALID_POS, CURRENT_ZONE
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    prevx, prevy = LAST_VALID_POS[0], LAST_VALID_POS[1]
    # 0) Hard mansion bounds (outer square)
    if BOUNDS:
        mx0, mx1, my0, my1 = BOUNDS
        margin = 15.0
        if px < (mx0 + margin) or px > (mx1 - margin) or py < (my0 + margin) or py > (my1 - margin):
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = get_player_zone(prevx, prevy)
            return
    prev_zone = get_player_zone(prevx, prevy)
    curr_zone = get_player_zone(px, py)
    # 1) If outside all valid areas -> rollback
    if curr_zone[0] == "none":
        PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
        CURRENT_ZONE = prev_zone
        return
    # Helpers
    def door_open(rid):
        d = DOORS.get(rid)
        if not d:
            return True
        return d.get("open", False)

    def crossed_door_portal(prevx, prevy, px, py, rid):
        d = DOORS.get(rid)
        if not d:
            return True
        x_wall = d["x_wall"]
        y0 = d["y0"]
        y1 = d["y1"]
        side = d["side"]  # "L" or "R"
        dx = (px - prevx)
        if abs(dx) < 1e-6:
            # Didn't move in x -> cannot cross the door wall plane
            return False
        # Must cross the wall plane between prev and curr:
        t = (x_wall - prevx) / dx
        if t < 0.0 or t > 1.0:
            return False
        y_cross = prevy + t * (py - prevy)
        # Must cross within the vertical door opening range
        if y_cross < y0 or y_cross > y1:
            return False
        if side == "L":
            # hall->room : prevx should be >= x_wall and px <= x_wall (crossing into left side)
            # room->hall : prevx <= x_wall and px >= x_wall (crossing into right side)
            if not ((prevx >= x_wall and px <= x_wall) or (prevx <= x_wall and px >= x_wall)):
                return False
        else:
            # side == "R"
            if not ((prevx <= x_wall and px >= x_wall) or (prevx >= x_wall and px <= x_wall)):
                return False
        return True
    # 2) Prevent room -> different room directly
    if prev_zone[0] == "room" and curr_zone[0] == "room":
        if prev_zone[1] != curr_zone[1]:
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = prev_zone
            return

    # 3) Enforce hall <-> room transitions through door portal only
    if prev_zone[0] == "hall" and curr_zone[0] == "room":
        rid = curr_zone[1]
        # Only allow entering rooms from stem hall
        if prev_zone[1] != "stem":
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = prev_zone
            return
        # Door must be open
        if not door_open(rid):
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = prev_zone
            return
        # Must cross via the door opening (portal)
        if not crossed_door_portal(prevx, prevy, px, py, rid):
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = prev_zone
            return
    if prev_zone[0] == "room" and curr_zone[0] == "hall":
        rid = prev_zone[1]
        # Only allow exiting rooms into stem hall
        if curr_zone[1] != "stem":
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = prev_zone
            return
        # Door must be open
        if not door_open(rid):
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = prev_zone
            return
        # Must cross via the door opening (portal)
        if not crossed_door_portal(prevx, prevy, px, py, rid):
            PLAYER_POS[0], PLAYER_POS[1] = prevx, prevy
            CURRENT_ZONE = prev_zone
            return
    # 4) Commit valid move
    LAST_VALID_POS[0], LAST_VALID_POS[1] = px, py
    CURRENT_ZONE = curr_zone

def door_lock_unlock_system():
    inv = globals().get("INVENTORY", set())
    if "4" in DOORS:
        DOORS["4"]["locked"] = ("Charm Item" not in inv)
        if DOORS["4"]["locked"]:
            DOORS["4"]["open"] = False
    # Exit door lock hook
    final_done = globals().get("FINAL_WARDEN_BANISHED", False)
    if EXIT_DOOR:
        EXIT_DOOR["locked"] = (not final_done)

def world_spawns_define_points():
    global SPAWNS
    SPAWNS = {
        "rooms": {},
        "hall": {},
        "doors": {},
        "exit": None
    }
    # Room centers + corners-ish
    for rid, (x0, x1, y0, y1) in ROOMS.items():
        cx = 0.5 * (x0 + x1)
        cy = 0.5 * (y0 + y1)
        SPAWNS["rooms"][rid] = {
            "center": (cx, cy),
            "near_inner": (cx + (x1 - x0) * 0.25 if rid in ("1", "2") else cx - (x1 - x0) * 0.25, cy),
            "corner_a": (x0 + 60.0, y0 + 60.0),
            "corner_b": (x1 - 60.0, y1 - 60.0),
        }
        # Door point (on the wall line)
        d = DOORS.get(rid)
        if d:
            xw = d["x_wall"]
            ym = 0.5 * (d["y0"] + d["y1"])
            SPAWNS["doors"][rid] = (xw, ym)
    # Hall spawn points
    if "stem" in HALL:
        x0, x1, y0, y1 = HALL["stem"]
        SPAWNS["hall"]["stem_mid"] = (0.5 * (x0 + x1), 0.5 * (y0 + y1))
        SPAWNS["hall"]["stem_low"] = (0.0, y0 + 120.0)
        SPAWNS["hall"]["stem_high"] = (0.0, y1 - 120.0)
    if "cap" in HALL:
        x0, x1, y0, y1 = HALL["cap"]
        SPAWNS["hall"]["cap_mid"] = (0.5 * (x0 + x1), 0.5 * (y0 + y1))
        SPAWNS["hall"]["cap_left"] = (x0 + 140.0, 0.5 * (y0 + y1))
        SPAWNS["hall"]["cap_right"] = (x1 - 140.0, 0.5 * (y0 + y1))
    # Exit point (interaction spot slightly inside boundary)
    if EXIT_DOOR:
        # interaction spot slightly INSIDE the boundary (depends on side)
        sign = 1.0 if EXIT_DOOR.get("side", "R") == "R" else -1.0
        ex = EXIT_DOOR["x"] - (35.0 * sign)
        ey = 0.5 * (EXIT_DOOR["y0"] + EXIT_DOOR["y1"])
        SPAWNS["exit"] = (ex, ey)

# ---- Floorplan drawing helpers ----
def draw_floor_checkered():
    # Base floor slab
    glColor3f(0.22, 0.22, 0.22)
    glBegin(GL_QUADS)
    glVertex3f(-g_length, -g_length, Z_FLOOR)
    glVertex3f( g_length, -g_length, Z_FLOOR)
    glVertex3f( g_length,  g_length, Z_FLOOR)
    glVertex3f(-g_length,  g_length, Z_FLOOR)
    glEnd()
    # Faint plank stripes
    glColor3f(0.20, 0.20, 0.20)
    spacing = 80
    for x in range(int(-g_length), int(g_length), spacing):
        glBegin(GL_QUADS)
        glVertex3f(x,     -g_length, Z_STRIPES)
        glVertex3f(x + 6, -g_length, Z_STRIPES)
        glVertex3f(x + 6,  g_length, Z_STRIPES)
        glVertex3f(x,      g_length, Z_STRIPES)
        glEnd()

def draw_boundaries():
    wall_h = 260.0
    base_r, base_g, base_b = 0.30, 0.30, 0.36
    stripe_r, stripe_g, stripe_b = 0.26, 0.26, 0.32
    skirt_thick = 14.0
    skirt_col = 0.10
    glColor3f(skirt_col, skirt_col, skirt_col)
    # Bottom inside strip
    glBegin(GL_QUADS)
    glVertex3f(-g_length, -g_length, Z_SKIRT)
    glVertex3f( g_length, -g_length, Z_SKIRT)
    glVertex3f( g_length, -g_length + skirt_thick, Z_SKIRT)
    glVertex3f(-g_length, -g_length + skirt_thick, Z_SKIRT)
    glEnd()
    # Top inside strip
    glBegin(GL_QUADS)
    glVertex3f(-g_length,  g_length - skirt_thick, Z_SKIRT)
    glVertex3f( g_length,  g_length - skirt_thick, Z_SKIRT)
    glVertex3f( g_length,  g_length, Z_SKIRT)
    glVertex3f(-g_length,  g_length, Z_SKIRT)
    glEnd()
    # Left inside strip
    glBegin(GL_QUADS)
    glVertex3f(-g_length, -g_length, Z_SKIRT)
    glVertex3f(-g_length + skirt_thick, -g_length, Z_SKIRT)
    glVertex3f(-g_length + skirt_thick,  g_length, Z_SKIRT)
    glVertex3f(-g_length,  g_length, Z_SKIRT)
    glEnd()
    # Right inside strip
    glBegin(GL_QUADS)
    glVertex3f( g_length - skirt_thick, -g_length, Z_SKIRT)
    glVertex3f( g_length, -g_length, Z_SKIRT)
    glVertex3f( g_length,  g_length, Z_SKIRT)
    glVertex3f( g_length - skirt_thick,  g_length, Z_SKIRT)
    glEnd()
    # 2) Main walls (quads)
    glColor3f(base_r, base_g, base_b)
    # Bottom wall (y = -g_length)
    glBegin(GL_QUADS)
    glVertex3f(-g_length, -g_length, 0)
    glVertex3f( g_length, -g_length, 0)
    glVertex3f( g_length, -g_length, wall_h)
    glVertex3f(-g_length, -g_length, wall_h)
    glEnd()
    # Top wall (y = +g_length)
    glBegin(GL_QUADS)
    glVertex3f(-g_length,  g_length, 0)
    glVertex3f( g_length,  g_length, 0)
    glVertex3f( g_length,  g_length, wall_h)
    glVertex3f(-g_length,  g_length, wall_h)
    glEnd()
    # Left wall (x = -g_length)
    glBegin(GL_QUADS)
    glVertex3f(-g_length, -g_length, 0)
    glVertex3f(-g_length,  g_length, 0)
    glVertex3f(-g_length,  g_length, wall_h)
    glVertex3f(-g_length, -g_length, wall_h)
    glEnd()
    # Right wall (x = +g_length)
    glBegin(GL_QUADS)
    glVertex3f( g_length, -g_length, 0)
    glVertex3f( g_length,  g_length, 0)
    glVertex3f( g_length,  g_length, wall_h)
    glVertex3f( g_length, -g_length, wall_h)
    glEnd()
    # 3) Haunted wall panels
    glColor3f(stripe_r, stripe_g, stripe_b)
    panel_w = 80.0; panel_gap = 20.0; z0 = 12.0; z1 = wall_h - 18.0
    # Bottom wall panels (vary x)
    x = -g_length + panel_gap
    while x < g_length - panel_w:
        glBegin(GL_QUADS)
        glVertex3f(x, -g_length + 0.5, z0)
        glVertex3f(x + panel_w, -g_length + 0.5, z0)
        glVertex3f(x + panel_w, -g_length + 0.5, z1)
        glVertex3f(x, -g_length + 0.5, z1)
        glEnd()
        x += (panel_w + panel_gap)
    # Top wall panels
    x = -g_length + panel_gap
    while x < g_length - panel_w:
        glBegin(GL_QUADS)
        glVertex3f(x, g_length - 0.5, z0)
        glVertex3f(x + panel_w, g_length - 0.5, z0)
        glVertex3f(x + panel_w, g_length - 0.5, z1)
        glVertex3f(x, g_length - 0.5, z1)
        glEnd()
        x += (panel_w + panel_gap)
    # Left wall panels (vary y)
    y = -g_length + panel_gap
    while y < g_length - panel_w:
        glBegin(GL_QUADS)
        glVertex3f(-g_length + 0.5, y, z0)
        glVertex3f(-g_length + 0.5, y + panel_w, z0)
        glVertex3f(-g_length + 0.5, y + panel_w, z1)
        glVertex3f(-g_length + 0.5, y, z1)
        glEnd()
        y += (panel_w + panel_gap)
    # Right wall panels
    y = -g_length + panel_gap
    while y < g_length - panel_w:
        glBegin(GL_QUADS)
        glVertex3f(g_length - 0.5, y, z0)
        glVertex3f(g_length - 0.5, y + panel_w, z0)
        glVertex3f(g_length - 0.5, y + panel_w, z1)
        glVertex3f(g_length - 0.5, y, z1)
        glEnd()
        y += (panel_w + panel_gap)

def draw_mansion_fill_strips():
    if not BOUNDS:
        return
    mx0, mx1, my0, my1 = BOUNDS
    z_top = 40.0
    glColor3f(0.16, 0.16, 0.18)
    def fill_rect(x0, x1, y0, y1):
        glBegin(GL_QUADS)
        glVertex3f(x0, y0, Z_OVERLAY)
        glVertex3f(x1, y0, Z_OVERLAY)
        glVertex3f(x1, y1, Z_OVERLAY)
        glVertex3f(x0, y1, Z_OVERLAY)
        glEnd()
        glBegin(GL_QUADS)
        glVertex3f(x0, y0, z_top)
        glVertex3f(x1, y0, z_top)
        glVertex3f(x1, y1, z_top)
        glVertex3f(x0, y1, z_top)
        glEnd()
    # Left strip (between outer wall and mx0)
    fill_rect(-g_length, mx0, -g_length, g_length)
    # Right strip
    fill_rect(mx1, g_length, -g_length, g_length)
    # Bottom strip
    fill_rect(mx0, mx1, -g_length, my0)
    # Top strip
    fill_rect(mx0, mx1, my1, g_length)

def draw_room_doors():
    if not DOORS:
        return
    frame_col = (0.12, 0.10, 0.08); door_col = (0.48, 0.30, 0.18); inset_col = (0.38, 0.24, 0.14); handle_col = (0.75, 0.70, 0.55)
    eps0 = 0.25; eps1 = 0.45; eps2 = 0.70; eps3 = 0.95
    for rid, d in DOORS.items():
        # Door plane
        base_x = d["x_draw"]
        sgn = 1.0 if d.get("side") == "L" else -1.0
        y0, y1 = d["y0"], d["y1"]
        z0, z1 = d["z0"], d["z1"]
        if d.get("open", False):
            x = base_x + sgn * eps1
            glColor3f(0.05, 0.05, 0.05) 
            glBegin(GL_QUADS)
            glVertex3f(x, y0, z0)
            glVertex3f(x, y1, z0)
            glVertex3f(x, y1, z1)
            glVertex3f(x, y0, z1)
            glEnd()
            continue
        # Frame slightly larger
        fy0 = y0 - 6.0
        fy1 = y1 + 6.0
        fz0 = z0
        fz1 = z1 + 10.0
        # 1) Frame 
        x = base_x + sgn * eps0
        glColor3f(frame_col[0], frame_col[1], frame_col[2])
        glBegin(GL_QUADS)
        glVertex3f(x, fy0, fz0)
        glVertex3f(x, fy1, fz0)
        glVertex3f(x, fy1, fz1)
        glVertex3f(x, fy0, fz1)
        glEnd()
        # 2) Main door panel
        x = base_x + sgn * eps1
        glColor3f(door_col[0], door_col[1], door_col[2])
        glBegin(GL_QUADS)
        glVertex3f(x, y0, z0)
        glVertex3f(x, y1, z0)
        glVertex3f(x, y1, z1)
        glVertex3f(x, y0, z1)
        glEnd()
        # 3) Inset rectangle
        inset_pad_y = 10.0
        inset_pad_z = 28.0
        iy0 = y0 + inset_pad_y
        iy1 = y1 - inset_pad_y
        iz0 = z0 + inset_pad_z
        iz1 = z1 - inset_pad_z
        x = base_x + sgn * eps2
        glColor3f(inset_col[0], inset_col[1], inset_col[2])
        glBegin(GL_QUADS)
        glVertex3f(x, iy0, iz0)
        glVertex3f(x, iy1, iz0)
        glVertex3f(x, iy1, iz1)
        glVertex3f(x, iy0, iz1)
        glEnd()
        # 4) Handle
        hy = 0.5 * (y0 + y1)
        hz = z0 + 95.0
        handle_y0 = hy - 6.0
        handle_y1 = hy + 6.0
        handle_z0 = hz - 6.0
        handle_z1 = hz + 6.0
        x = base_x + sgn * eps3
        glColor3f(handle_col[0], handle_col[1], handle_col[2])
        glBegin(GL_QUADS)
        glVertex3f(x, handle_y0, handle_z0)
        glVertex3f(x, handle_y1, handle_z0)
        glVertex3f(x, handle_y1, handle_z1)
        glVertex3f(x, handle_y0, handle_z1)
        glEnd()

def draw_room_doors_single(rid):
    if not DOORS or rid not in DOORS:
        return
    saved = dict(DOORS)
    try:
        globals()["DOORS"] = {rid: saved[rid]}
        draw_room_doors()
    finally:
        globals()["DOORS"] = saved

def try_toggle_nearby_door(px, py, reach=90.0):
    global GAME_MESSAGE
    if not DOORS:
        return False
    best_id = None
    best_d2 = 1e18
    r2 = reach * reach
    for rid, d in DOORS.items():
        xw = d["x_wall"]
        ym = 0.5 * (d["y0"] + d["y1"])
        d2 = distance2_xy(px, py, xw, ym)
        if d2 < best_d2:
            best_d2 = d2
            best_id = rid
    if best_id is None or best_d2 > r2:
        return False
    # Locked door: refuse toggle
    if DOORS[best_id].get("locked", False):
        GAME_MESSAGE = f"Door {best_id} is locked."
        return True
    DOORS[best_id]["open"] = not DOORS[best_id]["open"]
    return True

def draw_inner_walls():
    wall_h = 260.0
    thick = 10.0
    # Main wall color (less flat)
    base = (0.42, 0.42, 0.48)
    # Bottom trim (darker)
    trim = (0.18, 0.18, 0.22)
    # Top trim (slightly darker than base)
    toptrim = (0.30, 0.30, 0.36)
    trim_h = 22.0
    top_h0 = wall_h - 18.0

    def draw_wall_face(x0, y0, x1, y1):
        # main body
        glColor3f(base[0], base[1], base[2])
        glBegin(GL_QUADS)
        glVertex3f(x0, y0, 0.0)
        glVertex3f(x1, y1, 0.0)
        glVertex3f(x1, y1, wall_h)
        glVertex3f(x0, y0, wall_h)
        glEnd()
        # bottom trim
        glColor3f(trim[0], trim[1], trim[2])
        glBegin(GL_QUADS)
        glVertex3f(x0, y0, 0.0)
        glVertex3f(x1, y1, 0.0)
        glVertex3f(x1, y1, trim_h)
        glVertex3f(x0, y0, trim_h)
        glEnd()
        # top trim
        glColor3f(toptrim[0], toptrim[1], toptrim[2])
        glBegin(GL_QUADS)
        glVertex3f(x0, y0, top_h0)
        glVertex3f(x1, y1, top_h0)
        glVertex3f(x1, y1, wall_h)
        glVertex3f(x0, y0, wall_h)
        glEnd()

    for seg in WALLS:
        typ, c, a0, a1 = seg
        if typ == "H":
            y = c
            x0 = a0
            x1 = a1
            y0 = y - thick * 0.5
            y1 = y + thick * 0.5
            # two faces
            draw_wall_face(x0, y0, x1, y0)
            draw_wall_face(x0, y1, x1, y1)
        else:
            x = c
            y0 = a0
            y1 = a1
            x0 = x - thick * 0.5
            x1 = x + thick * 0.5
            draw_wall_face(x0, y0, x0, y1)
            draw_wall_face(x1, y0, x1, y1)

def draw_ceiling_rect(rect):
    x0, x1, y0, y1 = rect
    z = CEIL_H
    glColor3f(0.18, 0.18, 0.22)
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, z)
    glVertex3f(x1, y0, z)
    glVertex3f(x1, y1, z)
    glVertex3f(x0, y1, z)
    glEnd()
    t = 10.0
    glColor3f(0.12, 0.12, 0.15)
    # bottom edge
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, z - 2.0)
    glVertex3f(x1, y0, z - 2.0)
    glVertex3f(x1, y0 + t, z - 2.0)
    glVertex3f(x0, y0 + t, z - 2.0)
    glEnd()
    # top edge
    glBegin(GL_QUADS)
    glVertex3f(x0, y1 - t, z - 2.0)
    glVertex3f(x1, y1 - t, z - 2.0)
    glVertex3f(x1, y1, z - 2.0)
    glVertex3f(x0, y1, z - 2.0)
    glEnd()
    # left edge
    glBegin(GL_QUADS)
    glVertex3f(x0, y0, z - 2.0)
    glVertex3f(x0 + t, y0, z - 2.0)
    glVertex3f(x0 + t, y1, z - 2.0)
    glVertex3f(x0, y1, z - 2.0)
    glEnd()
    # right edge
    glBegin(GL_QUADS)
    glVertex3f(x1 - t, y0, z - 2.0)
    glVertex3f(x1, y0, z - 2.0)
    glVertex3f(x1, y1, z - 2.0)
    glVertex3f(x1 - t, y1, z - 2.0)
    glEnd()

def draw_endcap_walls_for_rect(rect, draw_left=True, draw_right=True, draw_bottom=True, draw_top=True):
    x0, x1, y0, y1 = rect
    h = CEIL_H
    eps = 2.0
    glColor3f(0.42, 0.42, 0.48)
    # bottom cap (y = y0)
    if draw_bottom:
        yy = y0 - eps
        glBegin(GL_QUADS)
        glVertex3f(x0, yy, 0.0)
        glVertex3f(x1, yy, 0.0)
        glVertex3f(x1, yy, h)
        glVertex3f(x0, yy, h)
        glEnd()
    # top cap (y = y1)
    if draw_top:
        yy = y1 + eps
        glBegin(GL_QUADS)
        glVertex3f(x0, yy, 0.0)
        glVertex3f(x1, yy, 0.0)
        glVertex3f(x1, yy, h)
        glVertex3f(x0, yy, h)
        glEnd()
    # left cap (x = x0)
    if draw_left:
        xx = x0 - eps
        glBegin(GL_QUADS)
        glVertex3f(xx, y0, 0.0)
        glVertex3f(xx, y1, 0.0)
        glVertex3f(xx, y1, h)
        glVertex3f(xx, y0, h)
        glEnd()
    # right cap (x = x1)
    if draw_right:
        xx = x1 + eps
        glBegin(GL_QUADS)
        glVertex3f(xx, y0, 0.0)
        glVertex3f(xx, y1, 0.0)
        glVertex3f(xx, y1, h)
        glVertex3f(xx, y0, h)
        glEnd()

def draw_world_floor_and_walls():
    draw_floor_checkered()
    draw_mansion_fill_strips()
    draw_boundaries()
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    zt, zid = get_player_zone(px, py)
    # Helper: draw overlay rect
    def draw_overlay(rect, col):
        x0, x1, y0, y1 = rect
        glColor3f(col[0], col[1], col[2])
        glBegin(GL_QUADS)
        glVertex3f(x0, y0, Z_OVERLAY)
        glVertex3f(x1, y0, Z_OVERLAY)
        glVertex3f(x1, y1, Z_OVERLAY)
        glVertex3f(x0, y1, Z_OVERLAY)
        glEnd()
    # Helper: draw only a subset of wall segments
    def draw_wall_segments(segments):
        saved = WALLS
        try:
            globals()["WALLS"] = segments
            draw_inner_walls()
        finally:
            globals()["WALLS"] = saved
    # Build segments for a specific room rectangle
    def room_wall_segments(rect, door_obj, include_door_gap=True):
        rx0, rx1, ry0, ry1 = rect
        thick = 10.0
        door_half = 45.0
        segs = []
        def add_h(y, x0, x1):
            if x1 > x0:
                segs.append(("H", y, x0, x1))
        def add_v(x, y0, y1):
            if y1 > y0:
                segs.append(("V", x, y0, y1))
        add_h(ry0, rx0, rx1)
        add_h(ry1, rx0, rx1)
        if door_obj["side"] == "L":
            add_v(rx0, ry0, ry1)
            if include_door_gap:
                midy = 0.5 * (ry0 + ry1)
                add_v(rx1, ry0, midy - door_half)
                add_v(rx1, midy + door_half, ry1)
            else:
                add_v(rx1, ry0, ry1)
        else:
            add_v(rx1, ry0, ry1)
            if include_door_gap:
                midy = 0.5 * (ry0 + ry1)
                add_v(rx0, ry0, midy - door_half)
                add_v(rx0, midy + door_half, ry1)
            else:
                add_v(rx0, ry0, ry1)

        return segs

    # ======= ROOM VIEW =======
    if zt == "room" and zid in ROOMS:
        rect = ROOMS[zid]
        shadow_active = globals().get("SHADOW_ROOM_ACTIVE", False) and (not globals().get("SHADOW_ROOM_DONE", False))
        shadow_rid = globals().get("SHADOW_ROOM_ID", None)
        if shadow_active and (zid == shadow_rid):
            draw_overlay(rect, (0.10, 0.08, 0.14))
        else:
            draw_overlay(rect, (0.30, 0.30, 0.30))
        draw_ceiling_rect(rect)
        door = DOORS.get(zid)
        if door and door.get("side") == "L":
            draw_endcap_walls_for_rect(rect, draw_left=True, draw_right=False, draw_bottom=True, draw_top=True)
        elif door and door.get("side") == "R":
            draw_endcap_walls_for_rect(rect, draw_left=False, draw_right=True, draw_bottom=True, draw_top=True)
        else:
            draw_endcap_walls_for_rect(rect, True, True, True, True)
        door = DOORS.get(zid)
        segs = room_wall_segments(rect, door, include_door_gap=True)
        draw_wall_segments(segs)
        if door:
            draw_room_doors_single(zid)
        return

    # ======= HALL VIEW =======
    if zt == "hall":
        if zid in HALL:
            hrect = HALL[zid]
            draw_overlay(hrect, (0.30, 0.30, 0.30))
            draw_ceiling_rect(hrect)
            if zid == "stem":
                draw_endcap_walls_for_rect(hrect, draw_left=True, draw_right=True, draw_bottom=True, draw_top=False)
            elif zid == "cap":
                draw_endcap_walls_for_rect(hrect, draw_left=True, draw_right=True, draw_bottom=False, draw_top=True)
            else:
                draw_endcap_walls_for_rect(hrect, True, True, True, True)
        draw_inner_walls()
        draw_room_doors()
        draw_exit_door()
        return
    # ======= OUTSIDE =======
    if "cap" in HALL:
        draw_overlay(HALL["cap"], (0.30, 0.30, 0.30))
    if "stem" in HALL:
        draw_overlay(HALL["stem"], (0.30, 0.30, 0.30))
    draw_inner_walls()
    draw_room_doors()
    draw_exit_door()

def draw_exit_door():
    if not EXIT_DOOR:
        return
    x_wall = EXIT_DOOR["x"]
    y0 = EXIT_DOOR["y0"]
    y1 = EXIT_DOOR["y1"]
    z0 = EXIT_DOOR["z0"]
    z1 = EXIT_DOOR["z1"]
    side = EXIT_DOOR.get("side", "R")
    offset = 2.5
    door_x = (x_wall - offset) if side == "R" else (x_wall + offset)
    if EXIT_DOOR.get("locked", True):
        glColor3f(0.65, 0.12, 0.12)  
    else:
        glColor3f(0.10, 0.65, 0.18)  
    # Door panel
    glBegin(GL_QUADS)
    glVertex3f(door_x, y0, z0)
    glVertex3f(door_x, y1, z0)
    glVertex3f(door_x, y1, z1)
    glVertex3f(door_x, y0, z1)
    glEnd()
    # Simple bright "EXIT" label 
    glColor3f(1.0, 1.0, 1.0)
    # Place label in upper-middle
    cz = z0 + 160.0
    h = 32.0
    stroke = 6.0
    gap = 10.0
    # total width for "EXIT"
    E_w, X_w, I_w, T_w = 24.0, 24.0, 12.0, 24.0
    total_w = E_w + gap + X_w + gap + I_w + gap + T_w
    start_y = 0.5 * (y0 + y1) - 0.5 * total_w
    z_bot = cz - 0.5 * h
    z_top = cz + 0.5 * h
    def rect(yy0, yy1, zz0, zz1):
        glBegin(GL_QUADS)
        glVertex3f(door_x - (0.8 if side == "R" else -0.8), yy0, zz0)
        glVertex3f(door_x - (0.8 if side == "R" else -0.8), yy1, zz0)
        glVertex3f(door_x - (0.8 if side == "R" else -0.8), yy1, zz1)
        glVertex3f(door_x - (0.8 if side == "R" else -0.8), yy0, zz1)
        glEnd()

    def draw_E(y):
        rect(y, y+stroke, z_bot, z_top)
        rect(y, y+E_w, z_top-stroke, z_top)
        rect(y, y+E_w*0.8, (z_bot+z_top)*0.5-stroke*0.5, (z_bot+z_top)*0.5+stroke*0.5)
        rect(y, y+E_w, z_bot, z_bot+stroke)

    def draw_I(y):
        rect(y, y+I_w, z_top-stroke, z_top)
        mid = y + I_w*0.5
        rect(mid-stroke*0.5, mid+stroke*0.5, z_bot, z_top)
        rect(y, y+I_w, z_bot, z_bot+stroke)

    def draw_T(y):
        rect(y, y+T_w, z_top-stroke, z_top)
        mid = y + T_w*0.5
        rect(mid-stroke*0.5, mid+stroke*0.5, z_bot, z_top)

    def draw_X(y):
        steps = 6
        dz = (z_top - z_bot) / steps
        dy = X_w / steps
        for i in range(steps):
            zz0 = z_bot + i*dz
            zz1 = zz0 + stroke
            rect(y + i*dy, y + i*dy + stroke, zz0, zz1)                 
            rect(y + X_w - i*dy - stroke, y + X_w - i*dy, zz0, zz1)      
    y = start_y
    draw_E(y); y += E_w + gap
    draw_X(y); y += X_w + gap
    draw_I(y); y += I_w + gap
    draw_T(y)

def draw_room_state_feedback():
    zt, zid = CURRENT_ZONE
    if zt != "hall":
        return
    for rid, door_pt in SPAWNS.get("doors", {}).items():
        x, y = door_pt
        st = ROOM_STATE.get(rid, "HAUNTED")
        if st == "CLEARED":
            glColor3f(0.20, 0.70, 0.25)
        else:
            glColor3f(0.55, 0.30, 0.75)
        # Draw a small plate on the floor near the door
        s = 26.0
        glBegin(GL_QUADS)
        glVertex3f(x - s, y - s, Z_OVERLAY)
        glVertex3f(x + s, y - s, Z_OVERLAY)
        glVertex3f(x + s, y + s, Z_OVERLAY)
        glVertex3f(x - s, y + s, Z_OVERLAY)
        glEnd()

# ============= (4) Member 2 — PLAYER CONTROL / CAMERA / STATUS EFFECTS / CHEAT =============
PLAYER_LAST_MOVE_T = 0.0

def banish_try_interaction(reach=110.0):
    return banish_interaction_logic(reach=reach)

def do_interact_action():
    if try_exit_interaction():
        return True
    if banish_try_interaction():
        return True
    if try_pickup_nearby_item():
        return True
    return try_toggle_nearby_door(PLAYER_POS[0], PLAYER_POS[1])

def handle_keyboard_input(key, x, y):
    global camera_mode, CHEAT_FREEZE_GHOSTS, GAME_MESSAGE
    if key == b'w': KEYS["w"] = True
    if key == b's': KEYS["s"] = True
    if key == b'a': KEYS["a"] = True
    if key == b'd': KEYS["d"] = True
    if key == b'e' or key == b'E':
        do_interact_action()
        return
    if key == b'v' or key == b'V':
        CHEAT_FREEZE_GHOSTS = not CHEAT_FREEZE_GHOSTS
        if CHEAT_FREEZE_GHOSTS:
            GAME_MESSAGE = "CHEAT: Ghosts frozen"
        else:
            GAME_MESSAGE = "CHEAT: Ghosts unfrozen"
        return
    if key == b'c' or key == b'C':
        camera_mode = CAM_MODE_TPS if camera_mode == CAM_MODE_FPS else CAM_MODE_FPS

def handle_keyboard_up(key, x, y):
    if key == b'w': KEYS["w"] = False
    if key == b's': KEYS["s"] = False
    if key == b'a': KEYS["a"] = False
    if key == b'd': KEYS["d"] = False

def handle_special_keys(key, x, y):
    global PLAYER_ROT, TPS_BACK, TPS_UP
    if key == GLUT_KEY_LEFT:
        PLAYER_ROT += 4.0
    elif key == GLUT_KEY_RIGHT:
        PLAYER_ROT -= 4.0
    elif key == GLUT_KEY_UP:
        TPS_BACK = clamp_value(TPS_BACK - 10.0, 90.0, 220.0)
    elif key == GLUT_KEY_DOWN:
        TPS_BACK = clamp_value(TPS_BACK + 10.0, 90.0, 260.0)

def handle_mouse_input(button, state, x, y):
    global camera_mode
    if state != GLUT_DOWN:
        return
    # Right click toggles camera mode
    if button == GLUT_RIGHT_BUTTON:
        camera_mode = CAM_MODE_TPS if camera_mode == CAM_MODE_FPS else CAM_MODE_FPS
        return
    # Left click: quick interact (same priority as E)
    if button == GLUT_LEFT_BUTTON:
        do_interact_action()
        return

def update_player_movement():
    global PLAYER_POS
    if GAME_OVER or GAME_WIN:
        return
    if FREEZE_T > 0.0:
        return
    fx, fy = forward_xy(PLAYER_ROT)
    rx, ry = fy, -fx
    sp = PLAYER_SPEED
    if SLOW_T > 0.0:
        sp *= 0.45
    dx = 0.0
    dy = 0.0
    w = KEYS["w"]
    s = KEYS["s"]
    a = KEYS["a"]
    d = KEYS["d"]
    if w:
        dx += fx * sp
        dy += fy * sp
    if s:
        dx -= fx * sp
        dy -= fy * sp
    if a:
        dx -= rx * sp
        dy -= ry * sp
    if d:
        dx += rx * sp
        dy += ry * sp
    PLAYER_POS[0] += dx * DT
    PLAYER_POS[1] += dy * DT

def camera_setup():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspect = float(w_width) / float(w_height)
    far_plane = max(2000.0, 8.0 * g_length)
    gluPerspective(fovY, aspect, 0.1, far_plane)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    fx, fy = forward_xy(PLAYER_ROT)
    if camera_mode == CAM_MODE_FPS:
        eye = (px, py, FPS_EYE_Z)
        look = (px + fx * FPS_LOOK_DIST, py + fy * FPS_LOOK_DIST, FPS_EYE_Z - 10.0)
        gluLookAt(eye[0], eye[1], eye[2],
                  look[0], look[1], look[2],
                  0, 0, 1)
        return
    # TPS camera with simple bounds clamp (prevents "inside wall" look most of the time)
    desired_cx = px - fx * TPS_BACK
    desired_cy = py - fy * TPS_BACK
    desired_cz = TPS_UP
    # Clamp camera position to mansion bounds (if available)
    if BOUNDS:
        mx0, mx1, my0, my1 = BOUNDS
        pad = 40.0
        desired_cx = clamp_value(desired_cx, mx0 + pad, mx1 - pad)
        desired_cy = clamp_value(desired_cy, my0 + pad, my1 - pad)
    lookz = 55.0
    gluLookAt(desired_cx, desired_cy, desired_cz,
              px + fx * 40.0, py + fy * 40.0, lookz,
              0, 0, 1)

def camera_mode_rules():
    global TPS_BACK, TPS_UP
    TPS_BACK = clamp_value(TPS_BACK, 90.0, 260.0)
    TPS_UP   = clamp_value(TPS_UP, 60.0, 160.0)

def player_status_effect_system():
    global SLOW_T, FREEZE_T, HURT_CD, GAME_MESSAGE
    if SLOW_T > 0.0:
        SLOW_T = max(0.0, SLOW_T - DT)
    if FREEZE_T > 0.0:
        FREEZE_T = max(0.0, FREEZE_T - DT)
    if HURT_CD > 0.0:
        HURT_CD = max(0.0, HURT_CD - DT)
    if GAME_MESSAGE and random.random() < 0.02:
        GAME_MESSAGE = ""

def draw_player_model_tps():
    if camera_mode != CAM_MODE_TPS:
        return
    glPushMatrix()
    glTranslatef(PLAYER_POS[0], PLAYER_POS[1], 0.0)
    glRotatef(PLAYER_ROT, 0, 0, 1)
    # --- Reference body proportions ---
    leg_len = 30.0
    leg_top_z = leg_len
    leg_top_r = 9.0
    leg_bot_r = 4.0
    torso_w = 45.0
    torso_d = 25.0
    torso_h = 65.0
    torso_gap = 6.0
    torso_cz = leg_top_z + torso_gap + (torso_h * 0.5)
    head_r = 15.0
    head_cz = torso_cz + (torso_h * 0.5) + 18.0
    # Torso
    glColor3f(0.0, 0.5, 0.0)
    glPushMatrix()
    glTranslatef(0, 0, torso_cz)
    glScalef(torso_w, torso_d, torso_h)
    glutSolidCube(1)
    glPopMatrix()
    # Head
    glColor3f(0, 0, 0)
    glPushMatrix()
    glTranslatef(0, 0, head_cz)
    gluSphere(quad, head_r, 16, 16)
    glPopMatrix()
    glColor3f(1.0, 0.8, 0.6)
    shoulder_z = torso_cz + 12.0
    arm_x = 18.0
    arm_y = 6.0
    arm_len = 34.0
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * arm_x, arm_y, shoulder_z)
        glRotatef(180, 1, 0, 0)
        gluCylinder(quad, 5, 5, arm_len, 10, 10)
        glPopMatrix()
    # Legs
    glColor3f(0, 0, 1)
    leg_x = 14.0
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * leg_x, 0, leg_top_z)
        glRotatef(180, 1, 0, 0)
        gluCylinder(quad, leg_top_r, leg_bot_r, leg_len, 10, 10)
        glPopMatrix()
    glPopMatrix()

# ============= (5) Member 3 — GHOST AI / ITEMS / BANISH / PROGRESSION / FINAL =============
FINAL_START_TIME = 0.0
HALL_ALTAR = None  # (x,y) banish point for hall ghost (g3)
def update_warden_ai():
    if GAME_OVER or GAME_WIN:
        return
    # CHEAT: freeze warden movement
    if CHEAT_FREEZE_GHOSTS:
        return
    if (not WARDEN) or (not WARDEN_VISIBLE) or (not FINAL_PHASE_ACTIVE) or FINAL_WARDEN_BANISHED:
        return
    # Only active in cap when player is also there
    zt, zid = zone_of_player()
    if (zt, zid) != ("hall", "cap"):
        return
    wx, wy = WARDEN["x"], WARDEN["y"]
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    dx = px - wx
    dy = py - wy
    mag = math.sqrt(dx * dx + dy * dy) + 1e-6
    dx /= mag
    dy /= mag
    time_elapsed = now_seconds() - FINAL_START_TIME
    base_speed = 120.0  # Reduced from 175.0
    max_speed = 180.0
    if FINAL_PHASE_TIMER > 60.0:  # First 15 seconds
        sp = base_speed
    else:
        progress = (75.0 - FINAL_PHASE_TIMER) / 15.0  # 0 to 1 over 15s
        sp = base_speed + (max_speed - base_speed) * min(1.0, progress)
    WARDEN["x"] += dx * sp * DT
    WARDEN["y"] += dy * sp * DT

def draw_warden_head_face(head_x, head_y, head_z, anim_time):
    # Base head
    glPushMatrix()
    glTranslatef(head_x, head_y, head_z)
    glColor3f(0.40, 0.10, 0.60)
    gluSphere(quad, 22, 18, 18)
    glPopMatrix()
    # Snout
    glPushMatrix()
    glTranslatef(head_x, head_y + 18, head_z - 2)
    glColor3f(0.34, 0.08, 0.50)
    glScalef(1.25, 1.45, 0.95)
    gluSphere(quad, 14, 16, 16)
    glPopMatrix()
    # Cheeks
    glPushMatrix()
    glTranslatef(head_x - 14, head_y + 10, head_z)
    glColor3f(0.36, 0.09, 0.54)
    glScalef(1.05, 1.20, 1.00)
    gluSphere(quad, 10, 14, 14)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(head_x + 14, head_y + 10, head_z)
    glColor3f(0.36, 0.09, 0.54)
    glScalef(1.05, 1.20, 1.00)
    gluSphere(quad, 10, 14, 14)
    glPopMatrix()
    # Eye bumps
    glPushMatrix()
    glTranslatef(head_x - 10, head_y + 14, head_z + 6)
    glColor3f(0.45, 0.14, 0.70)
    gluSphere(quad, 6.5, 12, 12)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(head_x + 10, head_y + 14, head_z + 6)
    glColor3f(0.45, 0.14, 0.70)
    gluSphere(quad, 6.5, 12, 12)
    glPopMatrix()
    # Eyes
    glColor3f(1.0, 0.0, 0.25)
    glPushMatrix()
    glTranslatef(head_x - 10, head_y + 18, head_z + 8)
    gluSphere(quad, 4.2, 12, 12)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(head_x + 10, head_y + 18, head_z + 8)
    gluSphere(quad, 4.2, 12, 12)
    glPopMatrix()
    # Horn plates
    glColor3f(0.20, 0.03, 0.30)
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(head_x + side * 14, head_y - 6, head_z + 18)
        glRotatef(20 * side, 0, 1, 0)
        glScalef(0.35, 0.90, 0.20)
        glutSolidCube(30)
        glPopMatrix()
    # Nostrils (points)
    glColor3f(0.05, 0.0, 0.08)
    glPointSize(5)
    glBegin(GL_POINTS)
    glVertex3f(head_x - 4, head_y + 30, head_z - 3)
    glVertex3f(head_x + 4, head_y + 30, head_z - 3)
    glEnd()

def draw_ghost2_segmented(x, y, z, anim_time, state):
    glPushMatrix()
    glTranslatef(x, y, z)
    glScalef(1.25, 1.25, 1.25)
    if state == 'sleep':
        pulse = math.sin(anim_time * 0.8) * 0.08 + 0.92
        glScalef(pulse, pulse, pulse)
        glTranslatef(0, 0, 25)
        sep = 4
        colors = [(0.55, 0.35, 0.45), (0.6, 0.4, 0.5), (0.65, 0.45, 0.55)]
    else:
        shake = math.sin(anim_time * 15) * 3
        glTranslatef(shake, shake * 0.7, 0)
        bounce = abs(math.sin(anim_time * 5)) * 12
        glTranslatef(0, 0, bounce + 30)
        sep = 12 + abs(math.sin(anim_time * 3)) * 8
        colors = [(0.95, 0.25, 0.3), (1.0, 0.3, 0.35), (1.0, 0.35, 0.4)]
    segment_sizes = [36, 30, 24]
    segment_heights = [25, 55, 80]
    for i, (size, height) in enumerate(zip(segment_sizes, segment_heights)):
        rotation = (anim_time * (30 + i * 20)) % 360
        bob = math.sin(anim_time * 2 + i) * sep * 0.3
        glPushMatrix()
        glTranslatef(0, 0, height + bob)
        glRotatef(rotation, 0, 0, 1)
        glColor3f(*colors[i])
        glutSolidCube(size)
        glPopMatrix()
    head_bob = math.sin(anim_time * 2.5) * 6
    glPushMatrix()
    glTranslatef(0, 0, 105 + head_bob)
    glColor3f(colors[2][0] * 1.05, colors[2][1] * 1.05, colors[2][2] * 1.05)
    glutSolidCube(24)
    glPopMatrix()
    eye_dist = 10 if state == 'sleep' else 14
    glColor3f(0.6, 0.05, 0.05)
    glPushMatrix()
    glTranslatef(-eye_dist, 10, 108 + head_bob)
    glutSolidCube(8)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(eye_dist, 10, 108 + head_bob)
    glutSolidCube(8)
    glPopMatrix()
    glPopMatrix()

def draw_ghost3_wispy(x, y, z, anim_time):
    glPushMatrix()
    glTranslatef(x, y, z)
    glScalef(1.25, 1.25, 1.25)
    drift_x = math.sin(anim_time * 1.0) * 20
    drift_y = math.cos(anim_time * 0.7) * 15
    glTranslatef(drift_x, drift_y, 0)
    float_offset = math.cos(anim_time * 1.4) * 12
    glTranslatef(0, 0, float_offset + 45)
    phase = math.sin(anim_time * 2.0) * 0.12 + 0.92
    glScalef(phase, phase, phase)
    layer_count = 4
    for layer in range(layer_count):
        layer_rot = (anim_time * (20 + layer * 10) + layer * 60) % 360
        layer_off = layer * 10
        intensity = 1.0 - (layer * 0.15)
        glPushMatrix()
        glRotatef(layer_rot, 0, 0, 1)
        for i in range(3):
            height = i * 18
            radius = 16 - i * 2 - layer * 2
            wave = math.sin(anim_time * 2 + i + layer) * 3
            cv = (0.75 + (i * 0.05)) * intensity
            glPushMatrix()
            glTranslatef(wave, wave * 0.5, height + layer_off)
            glColor3f(cv, cv, min(1.0, cv + 0.08))
            gluSphere(quad, max(4.0, radius), 14, 14)
            glPopMatrix()
        glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 35)
    glColor3f(0.6, 0.6, 0.65)
    gluSphere(quad, 14, 14, 14)
    glPopMatrix()
    glColor3f(0.1, 0.1, 0.15)
    glPushMatrix()
    glTranslatef(-8, 12, 55)
    gluSphere(quad, 4, 10, 10)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(8, 12, 55)
    gluSphere(quad, 4, 10, 10)
    glPopMatrix()
    glPopMatrix()

def draw_warden_horror(x, y, z, anim_time):
    glPushMatrix()
    glTranslatef(x, y, z)
    H_SCALE = 0.75            # overall height scale
    BASE_LIFT = 38.0          
    float_offset = math.sin(anim_time * 0.9) * (12.0 * H_SCALE)
    glTranslatef(0, 0, float_offset + BASE_LIFT)
    pulse = math.sin(anim_time * 1.3) * 0.06 + 1.04
    glScalef(pulse, pulse, pulse)
    body_dark  = (0.22, 0.05, 0.30)
    body_mid   = (0.30, 0.08, 0.40)
    body_light = (0.38, 0.12, 0.55)
    # --- Body spheres ---
    glPushMatrix()
    glTranslatef(0, 0, 35 * H_SCALE)
    glColor3f(*body_dark)
    gluSphere(quad, 55, 20, 20)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 85 * H_SCALE)
    glColor3f(*body_mid)
    gluSphere(quad, 48, 20, 20)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 130 * H_SCALE)
    glColor3f(*body_light)
    gluSphere(quad, 40, 20, 20)
    glPopMatrix()
    # --- Thorns ring 1 ---
    thorn_count = 12
    glColor3f(0.12, 0.02, 0.20)
    for i in range(thorn_count):
        ang = i * (360.0 / thorn_count) + (anim_time * 20)
        rad = deg_to_rad(ang)
        px = math.cos(rad) * 58
        py = math.sin(rad) * 58
        pz = 85 * H_SCALE
        glPushMatrix()
        glTranslatef(px, py, pz)
        glRotatef(ang, 0, 0, 1)
        glScalef(0.3, 0.3, 1.4)
        glutSolidCube(20)
        glPopMatrix()
    # --- Thorns ring 2 ---
    thorn_count2 = 10
    glColor3f(0.15, 0.03, 0.25)
    for i in range(thorn_count2):
        ang = i * (360.0 / thorn_count2) - (anim_time * 25)
        rad = deg_to_rad(ang)
        px = math.cos(rad) * 45
        py = math.sin(rad) * 45
        pz = 130 * H_SCALE
        glPushMatrix()
        glTranslatef(px, py, pz)
        glRotatef(ang, 0, 0, 1)
        glScalef(0.25, 0.25, 1.2)
        glutSolidCube(18)
        glPopMatrix()
    # --- Heads + necks ---
    head_configs = [(0, 0, 'center'), (-70, -10, 'left'), (70, -10, 'right')]
    for hx, hy, ht in head_configs:
        if ht == 'center':
            head_sway = math.sin(anim_time * 1.5) * 8
            head_bob  = math.sin(anim_time * 2.0) * 5
        elif ht == 'left':
            head_sway = math.sin(anim_time * 1.3 + 1) * 10
            head_bob  = math.sin(anim_time * 1.8 + 1) * 6
        else:
            head_sway = math.sin(anim_time * 1.4 + 2) * 10
            head_bob  = math.sin(anim_time * 1.9 + 2) * 6
        neck_segments = 5
        for seg in range(neck_segments):
            seg_h = (150 + seg * 18) * H_SCALE
            seg_x = hx * (0.25 + seg * 0.12)
            seg_y = hy * (0.25 + seg * 0.12)
            wave = math.sin(anim_time * 2 + seg + hx) * 4
            cf = seg / neck_segments
            glColor3f(body_mid[0] + cf * 0.08,
                      body_mid[1] + cf * 0.06,
                      body_mid[2] + cf * 0.12)
            glPushMatrix()
            glTranslatef(seg_x + wave, seg_y + wave * 0.5, seg_h)
            gluSphere(quad, 14 - seg * 1.2, 14, 14)
            glPopMatrix()
        head_x = hx + head_sway
        head_y = hy
        head_z = (235 * H_SCALE) + head_bob
        draw_warden_head_face(head_x, head_y, head_z, anim_time)
        glColor3f(0.12, 0.02, 0.20)
        for k in range(6):
            ang = k * 60 + anim_time * 30
            rad = deg_to_rad(ang)
            tx = head_x + math.cos(rad) * 18
            ty = head_y + math.sin(rad) * 18
            tz = head_z + (18 * H_SCALE)
            glPushMatrix()
            glTranslatef(tx, ty, tz)
            glRotatef(ang, 0, 0, 1)
            glScalef(0.2, 0.2, 1.0)
            glutSolidCube(14)
            glPopMatrix()
    glPopMatrix()

def zone_of_player():
    return globals().get("PLAYER_ZONE", get_player_zone(PLAYER_POS[0], PLAYER_POS[1]))

def dist2_to_player(x, y):
    return distance2_xy(x, y, PLAYER_POS[0], PLAYER_POS[1])

def try_pickup_nearby_item(reach=90.0):
    global GAME_MESSAGE, PLAYER_HEALTH, FINAL_PHASE_TIMER
    if GAME_OVER or GAME_WIN:
        return False
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    zt, zid = get_player_zone(px, py)
    r2 = reach * reach
    best = None
    best_d2 = 1e18
    for it in GAME_ITEMS:
        if it.get("picked"):
            continue
        if it.get("zone") != (zt, zid):
            continue
        d2 = distance2_xy(px, py, it["x"], it["y"])
        if d2 < best_d2:
            best_d2 = d2
            best = it
    if not best or best_d2 > r2:
        return False
    best["picked"] = True
    t = best["type"]
    # Special items
    if t == "Health Orb":
        PLAYER_HEALTH = clamp_value(PLAYER_HEALTH + 1, 0, 5)
        GAME_MESSAGE = f"Picked: Health Orb (+HP). HP now {PLAYER_HEALTH}"
        return True
    if t == "Time Shard":
        if globals().get("FINAL_PHASE_ACTIVE", False) and (not globals().get("FINAL_WARDEN_BANISHED", False)):
            FINAL_PHASE_TIMER = min(120.0, FINAL_PHASE_TIMER + 15.0)
            GAME_MESSAGE = f"Picked: Time Shard (+15s). Timer: {int(FINAL_PHASE_TIMER)}"
        else:
            GAME_MESSAGE = "Picked: Time Shard (saved for final)"
        INVENTORY.add("Time Shard")
        return True
    # Default: add to inventory
    INVENTORY.add(t)
    GAME_MESSAGE = f"Picked: {t}"
    return True

def try_exit_interaction(reach=120.0):
    global GAME_WIN, GAME_MESSAGE
    if not EXIT_DOOR:
        return False
    if EXIT_DOOR.get("locked", True):
        return False
    if GAME_OVER or GAME_WIN:
        return False
    exy = SPAWNS.get("exit", None)
    if not exy:
        return False
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    d2 = distance2_xy(px, py, exy[0], exy[1])
    if d2 <= reach * reach:
        GAME_WIN = True
        GAME_MESSAGE = "Escaped."
        return True
    return False

def spawn_ghosts_initial():
    global GHOSTS, WARDEN, FINAL_START_TIME, WARDEN_VISIBLE
    FINAL_START_TIME = now_seconds()
    GHOSTS = []
    WARDEN = None
    WARDEN_VISIBLE = False
    sp = globals().get("SPAWNS", None)
    def fallback_room_center(rid, dx, dy):
        r = ROOMS.get(rid)
        if not r:
            return (dx, dy)
        x0, x1, y0, y1 = r
        return (0.5 * (x0 + x1), 0.5 * (y0 + y1))
    # Ghost 2 (segmented)
    x2, y2 = fallback_room_center("2", 250.0, 250.0)
    if sp and "rooms" in sp and "2" in sp["rooms"]:
        x2, y2 = sp["rooms"]["2"]["center"]
    GHOSTS.append({
        "id": "g2",
        "type": "segmented",
        "x": x2, "y": y2, "z": 0.0,
        "state": "sleep",
        "zone": ("room", "2")
    })
    # Ghost 3 (wispy)
    x3, y3 = (0.0, -200.0)
    if sp and "hall" in sp and "stem_mid" in sp["hall"]:
        x3, y3 = sp["hall"]["stem_mid"]
    GHOSTS.append({
        "id": "g3",
        "type": "wispy",
        "x": x3, "y": y3, "z": 0.0,
        "state": "roam",
        "zone": ("hall", "stem")
    })
    # Warden - spawn at FAR END of cap hallway (away from player)
    wx, wy = (0.0, 500.0)
    if sp and "hall" in sp and "cap_mid" in sp["hall"]:
        cx, cy = sp["hall"]["cap_mid"]
        if "cap" in HALL:
            cap_x0, cap_x1, cap_y0, cap_y1 = HALL["cap"]
            exit_side = EXIT_DOOR.get("side", "R") if EXIT_DOOR else "R"
            if exit_side == "R":
                wx = cap_x1 - 180.0  # Near right wall
            else:
                wx = cap_x0 + 180.0  # Near left wall
            wy = cy
    WARDEN = {
        "id": "warden",
        "type": "warden",
        "x": wx, "y": wy, "z": 0.0,
        "state": "active",
        "zone": ("hall", "cap")
    }

def spawn_final_warden_if_ready():
    global FINAL_PHASE_ACTIVE, FINAL_PHASE_TIMER, WARDEN_VISIBLE
    if GAME_OVER or GAME_WIN:
        return
    if FINAL_PHASE_ACTIVE:
        return
    if "seal" in INVENTORY and WARDEN and (not FINAL_WARDEN_BANISHED):
        FINAL_PHASE_ACTIVE = True
        FINAL_PHASE_TIMER = 75.0
        WARDEN_VISIBLE = True

def ghost_state_machine_update():
    global GHOSTS
    if CHEAT_FREEZE_GHOSTS:
        return
    if GAME_OVER or GAME_WIN:
        return
    zt, zid = zone_of_player()
    chase_r = 260.0
    chase_r2 = chase_r * chase_r
    for g in GHOSTS:
        if g.get("zone") != (zt, zid):
            continue
        gx, gy = g["x"], g["y"]
        d2 = dist2_to_player(gx, gy)
        if d2 < chase_r2:
            g["state"] = "chase"
        else:
            if g["state"] == "chase":
                g["state"] = "roam"
        if g["state"] == "chase":
            # Move toward player
            px, py = PLAYER_POS[0], PLAYER_POS[1]
            dx = px - gx
            dy = py - gy
            mag = math.sqrt(dx * dx + dy * dy) + 1e-6
            dx /= mag
            dy /= mag
            if g["type"] == "segmented":
                sp = 135.0
                g["state"] = "awake"
            else:
                sp = 165.0
            g["x"] += dx * sp * DT
            g["y"] += dy * sp * DT
        else:
            t = now_seconds() - FINAL_START_TIME
            if g["type"] == "twisted":
                g["x"] += math.cos(t * 0.8 + 1.2) * 30.0 * DT
                g["y"] += math.sin(t * 0.7 + 0.4) * 30.0 * DT
            elif g["type"] == "segmented":
                g["x"] += math.cos(t * 0.6 + 2.0) * 22.0 * DT
                g["y"] += math.sin(t * 0.6 + 0.2) * 22.0 * DT
            else:
                g["x"] += math.cos(t * 1.1 + 0.5) * 40.0 * DT
                g["y"] += math.sin(t * 1.0 + 1.0) * 40.0 * DT

def apply_ghost_effects_on_contact():
    global PLAYER_HEALTH, GAME_OVER, GAME_MESSAGE, SLOW_T, FREEZE_T, HURT_CD
    if CHEAT_FREEZE_GHOSTS and CHEAT_GHOST_NO_DAMAGE:
        return
    if GAME_OVER or GAME_WIN:
        return
    zt, zid = zone_of_player()
    hit_r = 75.0
    hit_r2 = hit_r * hit_r
    if HURT_CD > 0.0:
        return
    for g in GHOSTS:
        if g.get("zone") != (zt, zid):
            continue
        d2 = dist2_to_player(g["x"], g["y"])
        if d2 <= hit_r2:
            PLAYER_HEALTH -= 1
            HURT_CD = 1.0

            if g["type"] == "segmented":
                FREEZE_T = max(FREEZE_T, 1.0)
                GAME_MESSAGE = "Segmented hit: freeze"
            else:
                SLOW_T = max(SLOW_T, 3.0)
                GAME_MESSAGE = "Wispy hit: slow"
            if PLAYER_HEALTH <= 0:
                GAME_OVER = True
                GAME_MESSAGE = "You were overwhelmed."
            return
    if WARDEN_VISIBLE and WARDEN and FINAL_PHASE_ACTIVE and (not FINAL_WARDEN_BANISHED):
        if WARDEN.get("zone") == (zt, zid):
            wx, wy = WARDEN["x"], WARDEN["y"]
            d2 = distance2_xy(wx, wy, PLAYER_POS[0], PLAYER_POS[1])
            if d2 <= (95.0 * 95.0):
                PLAYER_HEALTH -= 2
                HURT_CD = 1.2
                SLOW_T = max(SLOW_T, 2.0)
                GAME_MESSAGE = "Warden hit: heavy damage + slow"
                if PLAYER_HEALTH <= 0:
                    GAME_OVER = True
                    GAME_MESSAGE = "The Warden ended your run."
                return

def spawn_items_and_mechanisms():
    global GAME_ITEMS, ALTARS, HALL_ALTAR
    GAME_ITEMS = []
    ALTARS = {}
    HALL_ALTAR = None
    if "3" in ROOMS:
        x0, x1, y0, y1 = ROOMS["3"]
        cx = 0.5 * (x0 + x1)
        cy = 0.5 * (y0 + y1)
        HALL_ALTAR = (cx, cy)
    for rid, rect in ROOMS.items():
        if rid == "1":
            continue
        x0, x1, y0, y1 = rect
        ax = (x0 + 100.0) if rid in ("1", "2") else (x1 - 100.0)
        ay = y1 - 120.0
        ALTARS[rid] = (ax, ay)
    if "2" in SPAWNS.get("rooms", {}):
        cx, cy = SPAWNS["rooms"]["2"]["center"]
        GAME_ITEMS.append({"id": "it_sg", "type": "Charm Item", "x": cx, "y": cy, "z": 0.0, "zone": ("room", "2"), "picked": False})
    if "3" in SPAWNS.get("rooms", {}):
        cx, cy = SPAWNS["rooms"]["3"]["corner_a"]
        GAME_ITEMS.append({"id": "it_hp", "type": "Health Orb", "x": cx, "y": cy, "z": 0.0, "zone": ("room", "3"), "picked": False})
    if "4" in SPAWNS.get("rooms", {}):
        cx, cy = SPAWNS["rooms"]["4"]["corner_b"]
        GAME_ITEMS.append({"id": "it_tm", "type": "Time Shard", "x": cx, "y": cy, "z": 0.0, "zone": ("room", "4"), "picked": False})

def banish_interaction_logic(reach=110.0):
    global GAME_MESSAGE, WARDEN_VISIBLE, FINAL_WARDEN_BANISHED
    if GAME_OVER or GAME_WIN:
        return False
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    zt, zid = get_player_zone(px, py)
    # ===== Magic circle banish for g3 (wispy) in Room 3 =====
    if zt == "room" and zid == "3":
        hall_altar = globals().get("HALL_ALTAR", None)
        if hall_altar:
            ax, ay = hall_altar
            magic_reach = 80.0
            dist_sq = distance2_xy(px, py, ax, ay)
            if dist_sq <= (magic_reach * magic_reach):
                found = False
                for i in range(len(GHOSTS)):
                    if GHOSTS[i]["id"] == "g3":
                        GHOSTS.pop(i)
                        GAME_MESSAGE = "Wispy ghost banished by the magic circle!"
                        found = True
                        break
                if found:
                    return True
                else:
                    GAME_MESSAGE = "The wispy ghost has already been banished."
                    return True
    # ===== Room banish (g2) =====
    if zt == "room" and zid in ALTARS:
        ax, ay = ALTARS[zid]
        if distance2_xy(px, py, ax, ay) > reach * reach:
            return False
        needed = None
        target_id = None
        if zid == "2":
            needed = "Charm Item"
            target_id = "g2"
        else:
            return False
        if needed not in INVENTORY:
            GAME_MESSAGE = f"Need {needed} to banish here."
            return True
        for i in range(len(GHOSTS)):
            if GHOSTS[i]["id"] == target_id:
                GHOSTS.pop(i)
                GAME_MESSAGE = f"Banish successful in room {zid}."
                ROOM_STATE[zid] = "CLEARED"
                if zid in DOORS:
                    DOORS[zid]["open"] = True
                break
        return True

    # ===== Final warden banish =====
    if globals().get("FINAL_PHASE_ACTIVE", False) and globals().get("WARDEN_VISIBLE", False):
        if zt == "hall" and zid == "cap":
            if "seal" not in INVENTORY:
                if WARDEN:
                    wx, wy = WARDEN["x"], WARDEN["y"]
                    dist_sq = distance2_xy(px, py, wx, wy)
                    if dist_sq <= (200.0 * 200.0):  # Within visual range
                        GAME_MESSAGE = "Need SEAL to banish the Warden. Defeat all ghosts first!"
                        return True
                return False
            # If we have the seal, allow banishing from MUCH FARTHER away
            if WARDEN:
                wx, wy = WARDEN["x"], WARDEN["y"]
                banish_range = 220.0  # Increased from 140.0
                dist_sq = distance2_xy(px, py, wx, wy)
                # Show distance feedback
                dist = math.sqrt(dist_sq)
                if dist <= banish_range:
                    # Success!
                    FINAL_WARDEN_BANISHED = True
                    WARDEN_VISIBLE = False
                    GAME_MESSAGE = "Warden banished! Exit unlocked!"
                    return True
                elif dist <= (banish_range + 100.0):
                    # Close but not quite
                    GAME_MESSAGE = f"Get closer to banish! Distance: {int(dist)}"
                    return True
    return False

def shadow_room_activate():
    global SHADOW_ROOM_ID, SHADOW_ROOM_ACTIVE, SHADOW_ROOM_DONE, SHADOW_ROOM_TIMER
    if SHADOW_ROOM_ACTIVE or SHADOW_ROOM_DONE or (SHADOW_ROOM_ID is not None):
        return
    candidates = []
    for rid in ["1", "4", "2", "3"]:
        if rid in ROOMS:
            candidates.append(rid)
    if not candidates:
        return
    SHADOW_ROOM_ID = random.choice(candidates)
    SHADOW_ROOM_ACTIVE = True
    SHADOW_ROOM_DONE = False
    SHADOW_ROOM_TIMER = 0.0

def shadow_room_update():
    global SHADOW_ROOM_ACTIVE, SHADOW_ROOM_DONE, SHADOW_ROOM_TIMER, GAME_MESSAGE
    if GAME_OVER or GAME_WIN:
        return
    if not SHADOW_ROOM_ACTIVE:
        return
    if SHADOW_ROOM_DONE:
        return
    if SHADOW_ROOM_ID is None:
        return
    px, py = PLAYER_POS[0], PLAYER_POS[1]
    zt, zid = get_player_zone(px, py)
    if (zt == "room") and (zid == SHADOW_ROOM_ID):
        SHADOW_ROOM_TIMER += DT
        if SHADOW_ROOM_TIMER >= SHADOW_REQUIRED_T:
            SHADOW_ROOM_DONE = True
            SHADOW_ROOM_ACTIVE = False
            GAME_MESSAGE = "Shadow room cleared. You can now banish the Warden!"
    else:
        SHADOW_ROOM_TIMER = 0.0

def room_clear_progression_update():
    global GAME_MESSAGE
    alive_ids = set([g["id"] for g in GHOSTS])
    g2_alive = "g2" in alive_ids
    g3_alive = "g3" in alive_ids
    if (not g2_alive) and (not g3_alive):
        if "seal" not in INVENTORY:
            INVENTORY.add("seal")
            GAME_MESSAGE = "You obtained the SEAL. The Warden awakens..."
            shadow_room_activate()
            spawn_final_warden_if_ready()

def final_phase_timer_update():
    global FINAL_PHASE_TIMER, GAME_OVER, GAME_MESSAGE
    if not FINAL_PHASE_ACTIVE:
        return
    if GAME_OVER or GAME_WIN:
        return
    if FINAL_WARDEN_BANISHED:
        return
    FINAL_PHASE_TIMER = max(0.0, FINAL_PHASE_TIMER - DT)
    if FINAL_PHASE_TIMER <= 0.0:
        GAME_OVER = True
        GAME_MESSAGE = "Time ran out. The Warden consumed the mansion."

def draw_ghosts():
    zt, zid = globals().get("CURRENT_ZONE", ("hall", "stem"))
    anim_time = now_seconds() - FINAL_START_TIME
    for g in GHOSTS:
        if g.get("zone") != (zt, zid):
            continue
        gx, gy, gz = g["x"], g["y"], g["z"]
        gtype = g["type"]

        if gtype == "segmented":
            draw_ghost2_segmented(gx, gy, gz, anim_time, g.get("state", "sleep"))
        elif gtype == "wispy":
            draw_ghost3_wispy(gx, gy, gz, anim_time)
    # Warden only if enabled AND same zone
    if WARDEN_VISIBLE and WARDEN:
        if WARDEN.get("zone") == (zt, zid):
            draw_warden_horror(WARDEN["x"], WARDEN["y"], WARDEN["z"], anim_time)

def draw_items_and_mechanisms():
    zt, zid = zone_of_player()
    # Draw items in current zone
    for it in GAME_ITEMS:
        if it.get("picked"):
            continue
        if it.get("zone") != (zt, zid):
            continue
        glPushMatrix()
        glTranslatef(it["x"], it["y"], 12.0)
        t = it.get("type", "")
        if t == "Health Orb":
            glColor3f(0.25, 0.85, 0.35)
            glutSolidCube(18)
        elif t == "Time Shard":
            glColor3f(0.55, 0.75, 0.95)
            glutSolidCube(18)
        else:
            glColor3f(0.85, 0.85, 0.25)
            glutSolidCube(18)
        glPopMatrix()
    # Room altar marker (room zones only)
    if zt == "room" and zid in ALTARS:
        ax, ay = ALTARS[zid]
        glColor3f(0.15, 0.75, 0.75)
        s = 48.0
        glBegin(GL_QUADS)
        glVertex3f(ax - s, ay - s, 0.05)
        glVertex3f(ax + s, ay - s, 0.05)
        glVertex3f(ax + s, ay + s, 0.05)
        glVertex3f(ax - s, ay + s, 0.05)
        glEnd()
    # Magic circle marker (Room 3 only)
    if zt == "room" and zid == "3" and globals().get("HALL_ALTAR", None):
        ax, ay = HALL_ALTAR
        # Draw circle using triangle fan
        glColor3f(0.65, 0.25, 0.85)  # Purple magic circle
        radius = 60.0
        segments = 32
        glBegin(GL_TRIANGLES)
        for i in range(segments):
            a0 = 2.0 * math.pi * i / segments
            a1 = 2.0 * math.pi * (i + 1) / segments

            x0 = ax + radius * math.cos(a0)
            y0 = ay + radius * math.sin(a0)
            x1 = ax + radius * math.cos(a1)
            y1 = ay + radius * math.sin(a1)

            # Triangle: center -> p0 -> p1
            glVertex3f(ax, ay, 0.08)
            glVertex3f(x0, y0, 0.08)
            glVertex3f(x1, y1, 0.08)
        glEnd()
        # Draw outer ring
        glColor3f(0.85, 0.45, 0.95)  # Lighter purple
        # Outer ring using GL_LINES
        r2 = radius + 8.0
        glBegin(GL_LINES)
        for i in range(segments):
            a0 = 2.0 * math.pi * i / segments
            a1 = 2.0 * math.pi * (i + 1) / segments

            x0 = ax + r2 * math.cos(a0)
            y0 = ay + r2 * math.sin(a0)
            x1 = ax + r2 * math.cos(a1)
            y1 = ay + r2 * math.sin(a1)

            glVertex3f(x0, y0, 0.09)
            glVertex3f(x1, y1, 0.09)
        glEnd()

# ============= HUD and TEXT =============
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, w_width, 0, w_height)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in str(text):
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_hud_overlay():
    draw_text(10, w_height - 20, f"HP: {PLAYER_HEALTH}")
    zt, zid = get_player_zone(PLAYER_POS[0], PLAYER_POS[1])
    if zt == "hall":
        zone_str = "Hallway"
    elif zt == "room":
        zone_str = f"Room {zid}"
    else:
        zone_str = zt
    draw_text(10, w_height - 40, f"Zone: {zone_str}")
    if CHEAT_FREEZE_GHOSTS:
        draw_text(10, w_height - 80, "CHEAT: FREEZE (V)")
    # Status effects (show remaining seconds)
    y = w_height - 60
    if SLOW_T > 0.0:
        draw_text(10, y, f"SLOW: {SLOW_T:.1f}s"); y -= 20
    if FREEZE_T > 0.0:
        draw_text(10, y, f"FREEZE: {FREEZE_T:.1f}s"); y -= 20
    if FINAL_PHASE_ACTIVE:
        draw_text(10, y, f"FINAL TIMER: {max(0, int(FINAL_PHASE_TIMER))}"); y -= 20
    if GAME_OVER:
        draw_text(w_width * 0.40, w_height * 0.55, "GAME OVER")
    if GAME_WIN:
        draw_text(w_width * 0.42, w_height * 0.55, "YOU WIN")
    if GAME_MESSAGE:
        draw_text(10, 20, GAME_MESSAGE)

# ============= (7) UPDATE LOOP (Idle) =============
def update_game():
    global LAST_FRAME_TIME, DT
    t = now_seconds()
    if LAST_FRAME_TIME <= 0.0:
        LAST_FRAME_TIME = t
    DT = t - LAST_FRAME_TIME
    LAST_FRAME_TIME = t
    DT = clamp_value(DT, 0.001, 0.05)
    player_status_effect_system()
    update_player_movement()
    collision_resolve_player_world()
    define_room_triggers()
    globals()["PLAYER_ZONE"] = get_player_zone(PLAYER_POS[0], PLAYER_POS[1])
    door_lock_unlock_system()
    ghost_state_machine_update()
    update_warden_ai()
    apply_ghost_effects_on_contact()
    room_clear_progression_update()
    shadow_room_update()
    spawn_final_warden_if_ready()
    final_phase_timer_update()
    camera_mode_rules()

def idle():
    update_game()
    glutPostRedisplay()

# ============= (8) DRAW LOOP (showScreen) — Draw in consistent order =============
def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, w_width, w_height)
    setupCamera()
    draw_world_floor_and_walls()
    draw_room_state_feedback()
    draw_items_and_mechanisms()
    draw_ghosts()
    draw_player_model_tps()
    draw_hud_overlay()
    glutSwapBuffers()

# ============= LISTENERS =============

def keyboardListener(key, x, y):
    if key == b'r' or key == b'R':
        reset_run()
        return
    handle_keyboard_input(key, x, y)
    glutPostRedisplay()

def specialKeyListener(key, x, y):
    handle_special_keys(key, x, y)
    glutPostRedisplay()

def mouseListener(button, state, x, y):
    handle_mouse_input(button, state, x, y)
    glutPostRedisplay()

# ============= CAMERA =============
def setupCamera():
    camera_setup()
# ============= MAIN =============
def main():
    global quad
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(w_width, w_height)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"Spectral Lockdown 3D")
    quad = gluNewQuadric()
    glEnable(GL_DEPTH_TEST)
    init_game_state()
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutKeyboardUpFunc(handle_keyboard_up)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)
    glutMainLoop()

if __name__ == "__main__":
    main()