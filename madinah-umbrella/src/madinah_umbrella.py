"""Madinah Piazza convertible umbrella (Prophet's Mosque, SL Rasch "U-26 Piazza"), open state.

Units: millimetres, +Z up, origin at the centre of the column on the paving.

Published dimensions (SL Rasch / press): 25.5 m x 25.5 m canopy, open height
14.4 m or 15.3 m (two types so neighbours overlap), folded height 21.7 m,
4 diagonal + 4 middle + 16 passive arms, PTFE membrane with blue ornament,
GRP cladding with glass mosaic, gold-plated brass trim, 4 lanterns per column.
Everything else (section sizes, column proportions, ornament layout) is an
estimate; see README.md.
"""

from __future__ import annotations

import math

from cadgen import build123d as bd
from cadgen import glb, step

# ---- published dimensions ---------------------------------------------------
SPAN = 25_500.0            # canopy side
OPEN_HEIGHT = 15_300.0     # corner height, tall type (short type: 14_400)
FOLDED_HEIGHT = 21_700.0   # reference only: PIVOT_Z + middle arm length

# ---- estimated dimensions ---------------------------------------------------
HALF = SPAN / 2
CORNER_R = HALF * math.sqrt(2)
MID_TIP_Z = OPEN_HEIGHT - 1_400.0   # edge mid-point sits lower than the corners
FUNNEL_R = 800.0                    # membrane collar radius at the mast
FUNNEL_Z = OPEN_HEIGHT - 5_850.0    # low point of the funnel
PIVOT_Z = FUNNEL_Z - 250.0
ARM_DROP = 60.0                     # arm top below membrane

PLINTH1_AF, PLINTH1_H = 2_100.0, 350.0
PLINTH2_AF, PLINTH2_H = 1_800.0, 650.0
SHAFT_W, SHAFT_CH = 1_300.0, 300.0
SHAFT_Z0 = PLINTH1_H + PLINTH2_H
SHAFT_Z1 = 7_000.0
CAPITAL_Z1 = 8_050.0
LANTERN_Z = 5_000.0
MAST_R = 400.0

# ---- colours ----------------------------------------------------------------
WHITE = bd.Color(0.96, 0.96, 0.94)
MEMBRANE = bd.Color(0.98, 0.97, 0.93)
BLUE = bd.Color(0.10, 0.32, 0.62)
GOLD = bd.Color(0.83, 0.66, 0.22)
BEIGE = bd.Color(0.86, 0.80, 0.68)
GRANITE = bd.Color(0.36, 0.35, 0.34)
GLASS = bd.Color(1.0, 0.93, 0.70)
DARK = bd.Color(0.15, 0.15, 0.16)


def paint(shape, color, label):
    shape.color = color
    shape.label = label
    return shape


def group(label, parts):
    return bd.Compound(label=label, children=list(parts))


def polar(r, az_deg, z):
    a = math.radians(az_deg)
    return bd.Vector(r * math.cos(a), r * math.sin(a), z)


def lerp(a, b, t):
    return a + (b - a) * t


def tube(p0, p1, radius):
    d = p1 - p0
    cyl = bd.Cylinder(radius, d.length, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    return bd.Plane(origin=p0, z_dir=d.normalized()).location * cyl


def chamfered_square(w, c):
    h = w / 2
    return bd.Polygon(
        (h - c, h), (-(h - c), h), (-h, h - c), (-h, -(h - c)),
        (-(h - c), -h), (h - c, -h), (h, -(h - c)), (h, h - c),
        align=None,
    )


def prism(sketch, z0, h):
    return bd.extrude(bd.Pos(0, 0, z0) * sketch, amount=h)


def tapered(sk0, z0, sk1, z1):
    return bd.loft([bd.Pos(0, 0, z0) * sk0, bd.Pos(0, 0, z1) * sk1])


# ---- membrane geometry ------------------------------------------------------
def arm_line(az):
    """Membrane support line (inner collar point, tip) for the arm at azimuth az."""
    diagonal = round(az) % 90 == 45
    tip = polar(CORNER_R if diagonal else HALF, az, OPEN_HEIGHT if diagonal else MID_TIP_Z)
    return polar(FUNNEL_R, az, FUNNEL_Z), tip


def patch(az_a, az_b, s1, s2, t1, t2, dz=0.0):
    """Ruled patch of the sector between two arm lines, in (s along arm, t across)."""
    a0, a1 = arm_line(az_a)
    b0, b1 = arm_line(az_b)
    off = bd.Vector(0, 0, dz)

    def pt(s, t):
        return lerp(lerp(a0, a1, s), lerp(b0, b1, s), t) + off

    e1 = bd.Edge.make_line(pt(s1, t1), pt(s2, t1))
    e2 = bd.Edge.make_line(pt(s1, t2), pt(s2, t2))
    return bd.Face.make_surface_from_curves(e1, e2)


def membrane():
    sheets, blue = [], []
    for k in range(8):
        az_m = 90 * ((k + 1) // 2 % 4)           # middle arm bounding this sector
        az_d = 45 + 90 * (k // 2)                # diagonal arm bounding this sector
        sheets.append(patch(az_d, az_m, 0, 1, 0, 1))

        def b(s1, s2, t1, t2):
            blue.append(patch(az_d, az_m, s1, s2, t1, t2, dz=-20))

        b(0.100, 0.125, 0, 1)                    # inner ring
        b(0.330, 0.345, 0, 1)                    # outer ring
        for i in range(7):                       # rays between the rings
            c = i / 6
            b(0.140, 0.315, max(0, c - 0.035), min(1, c + 0.035))
        for i in (0, 2, 4):                      # stepped crenellation
            b(0.360, 0.400, i / 6 + 0.02, (i + 1) / 6 - 0.02)
        for i in (1, 3, 5):
            b(0.400, 0.440, i / 6 + 0.02, (i + 1) / 6 - 0.02)
        b(0.470, 0.960, 0.030, 0.045)            # stripes beside the arms
        b(0.470, 0.960, 0.955, 0.970)
        b(0.975, 0.990, 0, 1)                    # edge border
    return [
        paint(bd.Compound(sheets), MEMBRANE, "ptfe_membrane"),
        paint(bd.Compound(blue), BLUE, "blue_ornament"),
    ]


# ---- arms -------------------------------------------------------------------
def box_arm(p0, p1, w0, d0, w1, d1):
    """Tapered box section whose top face runs from p0 to p1."""
    d = p1 - p0
    length = d.length
    az = math.degrees(math.atan2(d.Y, d.X))
    pitch = math.degrees(math.atan2(d.Z, math.hypot(d.X, d.Y)))
    loc = bd.Pos(p0.X, p0.Y, p0.Z) * bd.Rot(0, 0, az) * bd.Rot(0, -pitch, 0)

    def section(x, w, dep):
        return bd.Plane.YZ.offset(x) * bd.Pos(0, -dep / 2) * bd.Rectangle(w, dep)

    body = bd.loft([section(0, w0, d0), section(length, w1, d1)])
    inlay = bd.loft([
        bd.Plane.YZ.offset(0.12 * length) * bd.Pos(0, -lerp(d0, d1, 0.12) - 4) * bd.Rectangle(w0 * 0.45, 8),
        bd.Plane.YZ.offset(0.92 * length) * bd.Pos(0, -lerp(d0, d1, 0.92) - 4) * bd.Rectangle(w1 * 0.45, 8),
    ])
    tip = bd.Plane.YZ.offset(length) * bd.Pos(0, -d1 / 2) * bd.Cone(
        d1 * 0.62, 12, 520, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    collar = bd.Plane.YZ.offset(length - 90) * bd.Pos(0, -d1 / 2) * bd.Rectangle(w1 + 50, d1 + 50)
    collar = bd.extrude(collar, amount=90)
    return loc, body, inlay, tip + collar


def arms():
    white, blue, gold = [], [], []
    drop = bd.Vector(0, 0, -ARM_DROP)
    carriage = PIVOT_Z - 900
    for i in range(8):
        az = 45 * i
        diagonal = i % 2 == 1
        m0, m1 = arm_line(az)
        p0, p1 = m0 + drop, m1 + drop
        size = (460, 640, 200, 220) if diagonal else (400, 540, 180, 200)
        loc, body, inlay, tip = box_arm(p0, p1, *size)
        white.append(loc * body)
        blue.append(loc * inlay)
        gold.append(loc * tip)

        length = (p1 - p0).length
        axis = (p1 - p0).normalized()
        side = bd.Vector(-math.sin(math.radians(az)), math.cos(math.radians(az)), 0)

        # drive strut from the sliding carriage on the mast up to the arm
        hit = p0 + axis * 2_600 + bd.Vector(0, 0, -size[1] * 0.9)
        white.append(tube(polar(MAST_R + 120, az, carriage), hit, 70))

        if diagonal:
            # fold hinge of the outer arm section (the arm is longer than the folded stack)
            fold = FOLDED_HEIGHT - PIVOT_Z
            hp = p0 + axis * fold + bd.Vector(0, 0, -lerp(size[1], size[3], fold / length) / 2)
            gold.append(tube(hp - side * 300, hp + side * 300, 110))
            branch = hp
        else:
            branch = p0 + axis * (0.60 * length) + bd.Vector(0, 0, -lerp(size[1], size[3], 0.6) / 2)

        # passive arms out to the quarter points of the canopy edge (2 per main arm = 16)
        for sign in (-1, 1):
            az_n = az + sign * 45
            _, n1 = arm_line(az_n)
            edge_pt = lerp(m1, n1, 0.5) + bd.Vector(0, 0, -70)
            white.append(tube(branch, edge_pt, 55))
    return [
        paint(bd.Compound(white), WHITE, "arms_grp_cladding"),
        paint(bd.Compound(blue), BLUE, "arm_mosaic_inlay"),
        paint(bd.Compound(gold), GOLD, "arm_gold_tips_and_hinges"),
    ]


# ---- column -----------------------------------------------------------------
def lantern():
    """One wall lantern; local origin on the column face, +X pointing outwards."""
    gold, glass = [], []
    reach, top = 520.0, 420.0
    gold.append(bd.Pos(reach / 2, 0, top) * bd.Box(reach, 60, 60))
    gold.append(tube(bd.Vector(0, 0, top - 380), bd.Vector(reach - 90, 0, top - 30), 22))
    gold.append(bd.Pos(12, 0, top - 190) * bd.Box(24, 180, 520))
    gold.append(tube(bd.Vector(reach, 0, top), bd.Vector(reach, 0, top - 150), 14))
    z_cap = top - 150
    body_h, body_r = 620.0, 190.0
    cap = bd.Pos(reach, 0, z_cap - 150) * bd.Cone(
        body_r + 50, 40, 150, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    gold.append(cap)
    hexagon = bd.RegularPolygon(body_r, 6)
    glass.append(bd.Pos(reach, 0, z_cap - 150 - body_h) * bd.extrude(hexagon, amount=body_h))
    for j in range(6):
        v = polar(body_r, 60 * j, 0)
        gold.append(tube(bd.Vector(reach + v.X, v.Y, z_cap - 150 - body_h),
                         bd.Vector(reach + v.X, v.Y, z_cap - 150), 13))
    for z in (z_cap - 150 - body_h, z_cap - 150 - body_h / 2, z_cap - 165):
        ring = bd.extrude(bd.RegularPolygon(body_r + 16, 6), amount=22)
        ring -= bd.extrude(bd.RegularPolygon(body_r - 6, 6), amount=22)
        gold.append(bd.Pos(reach, 0, z) * ring)
    z_bot = z_cap - 150 - body_h
    gold.append(bd.Pos(reach, 0, z_bot) * bd.Rot(180, 0, 0) * bd.Cone(
        body_r + 16, 30, 140, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)))
    gold.append(bd.Pos(reach, 0, z_bot - 175) * bd.Sphere(42))
    return gold, glass


def mist_fan():
    """Misting fan; local origin on the column chamfer, +X pointing outwards."""
    dark, white = [], []
    white.append(bd.Pos(170, 0, 0) * bd.Box(340, 90, 90))
    axis = bd.Plane.YZ.offset(340)
    shroud = bd.extrude(axis * (bd.Circle(390) - bd.Circle(360)), amount=240)
    white.append(shroud)
    dark.append(bd.extrude(axis * bd.Circle(85), amount=200))
    for j in range(5):
        blade = bd.Pos(0, 0, 215) * bd.Box(22, 150, 270)
        dark.append(bd.Pos(440, 0, 0) * bd.Rot(72 * j, 0, 0) * bd.Rot(0, 0, 18) * blade)
    nozzle = bd.Plane.YZ.offset(600) * bd.Torus(375, 14)
    dark.append(nozzle)
    for j in range(16):  # 16 spray outlets per fan (press figure)
        a = math.radians(22.5 * j)
        dark.append(bd.Pos(612, 375 * math.cos(a), 375 * math.sin(a)) * bd.Sphere(20))
    return dark, white


def column():
    parts = []
    parts.append(paint(prism(bd.RegularPolygon(PLINTH1_AF / 2, 8, major_radius=False), 0, PLINTH1_H),
                       GRANITE, "plinth_granite"))

    oct2 = bd.RegularPolygon(PLINTH2_AF / 2, 8, major_radius=False)
    stone = [prism(oct2, PLINTH1_H, PLINTH2_H - 150),
             tapered(oct2, SHAFT_Z0 - 150, chamfered_square(SHAFT_W + 120, SHAFT_CH), SHAFT_Z0)]
    shaft_sk = chamfered_square(SHAFT_W, SHAFT_CH)
    stone.append(prism(shaft_sk, SHAFT_Z0, SHAFT_Z1 - SHAFT_Z0))
    # capital: two flaring tiers under a top slab
    tier1 = chamfered_square(1_750, 420)
    tier2 = chamfered_square(2_250, 560)
    stone.append(tapered(shaft_sk, SHAFT_Z1, tier1, SHAFT_Z1 + 450))
    stone.append(prism(tier1, SHAFT_Z1 + 450, 80))
    stone.append(tapered(tier1, SHAFT_Z1 + 530, tier2, CAPITAL_Z1 - 110))
    parts.append(paint(bd.Compound(stone), BEIGE, "column_cladding_grp"))

    gold, blue, glass, dark, white = [], [], [], [], []
    for z, grow, h in ((SHAFT_Z0, 70, 110), (4_500, 50, 90), (5_650, 50, 90), (SHAFT_Z1 - 90, 70, 110)):
        gold.append(prism(chamfered_square(SHAFT_W + grow, SHAFT_CH + grow * 0.3), z, h)
                    - prism(shaft_sk, z, h))
    gold.append(prism(chamfered_square(1_800, 435), SHAFT_Z1 + 450, 80)
                - prism(tier1, SHAFT_Z1 + 450, 80))
    gold.append(prism(tier2, CAPITAL_Z1 - 110, 110))

    flat = SHAFT_W - 2 * SHAFT_CH                 # width of a main face
    for q in range(4):
        face = bd.Rot(0, 0, 90 * q) * bd.Pos(SHAFT_W / 2, 0, 0)
        for z0, z1 in ((1_350, 4_350), (5_900, 6_800)):
            h = z1 - z0
            blue.append(face * bd.Pos(4, 0, (z0 + z1) / 2) * bd.Box(8, flat - 160, h - 160))
            frame = bd.Box(14, flat - 60, h - 60) - bd.Box(14, flat - 160, h - 160)
            gold.append(face * bd.Pos(7, 0, (z0 + z1) / 2) * frame)
            # eight-pointed star medallion in the middle of the mosaic panel
            star = bd.Rectangle(260, 260) + bd.Rot(0, 0, 45) * bd.Rectangle(260, 260)
            medal = bd.extrude(bd.Plane.YZ * star, amount=14)
            for zc in ([z0 + h * 0.25, z0 + h * 0.5, z0 + h * 0.75] if h > 2_000 else [z0 + h / 2]):
                gold.append(face * bd.Pos(8, 0, zc) * medal)
        g, gl = lantern()
        lamp = face * bd.Pos(0, 0, LANTERN_Z)
        gold += [lamp * s for s in g]
        glass += [lamp * s for s in gl]

    # uplights on the capital that wash the underside of the membrane
    for j in range(8):
        az = 22.5 + 45 * j
        base = polar(900, az, CAPITAL_Z1)
        aim = (polar(2_400, az, CAPITAL_Z1 + 1_500) - base).normalized()
        dark.append(tube(base, base + aim * 260, 95))
        glass.append(tube(base + aim * 260, base + aim * 272, 85))

    for q in (0, 2):  # misting fans on two opposite corner chamfers
        loc = bd.Rot(0, 0, 45 + 90 * q) * bd.Pos(SHAFT_W / 2 * math.sqrt(2) - SHAFT_CH / math.sqrt(2), 0, 3_600)
        d, w = mist_fan()
        dark += [loc * s for s in d]
        white += [loc * s for s in w]

    # mast, sliding carriage, arm head and funnel collar
    white.append(bd.Pos(0, 0, CAPITAL_Z1) * bd.Cylinder(
        MAST_R, FUNNEL_Z - CAPITAL_Z1, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)))
    white.append(bd.Pos(0, 0, PIVOT_Z - 900) * bd.Cylinder(MAST_R + 170, 320))
    white.append(bd.Pos(0, 0, PIVOT_Z - 60) * bd.Cylinder(FUNNEL_R + 120, 300))
    for i in range(8):
        white.append(bd.Rot(0, 0, 45 * i) * bd.Pos(FUNNEL_R + 60, 0, PIVOT_Z + 20) * bd.Box(260, 90, 380))
    funnel = bd.Pos(0, 0, FUNNEL_Z - 40) * (
        bd.Cone(FUNNEL_R - 60, FUNNEL_R + 90, 260, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        - bd.Cone(FUNNEL_R - 110, FUNNEL_R + 40, 260, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)))
    gold.append(funnel)

    parts += [
        paint(bd.Compound(gold), GOLD, "gold_plated_brass_trim"),
        paint(bd.Compound(blue), BLUE, "glass_mosaic_panels"),
        paint(bd.Compound(glass), GLASS, "lantern_glass_and_uplight_lenses"),
        paint(bd.Compound(dark), DARK, "uplights_and_fan_parts"),
        paint(bd.Compound(white), WHITE, "mast_head_and_fan_shrouds"),
    ]
    return parts


@step(out="../STEP/madinah_umbrella.step")
@glb(out="../GLB/madinah_umbrella.glb")
def madinah_umbrella():
    return group("madinah_piazza_umbrella", [
        group("column", column()),
        group("arms", arms()),
        group("canopy", membrane()),
    ])


if __name__ == "__main__":
    madinah_umbrella()
