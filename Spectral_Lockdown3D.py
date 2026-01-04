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

# ============= NaziaNissa - MAP / COLLISION =============
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
