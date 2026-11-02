"""Vintage DETTOL antiseptic bottle, modelled after the supplied illustration.

Units: millimetres. Z up, bottle base on Z=0, front (label) face toward -Y.
All lettering and the sword/oval artwork are ENGRAVED (cut) into the glass;
"DETTOL" is engraved into the top of the cap and around the neck collar.
"""
from __future__ import annotations

import math
from functools import reduce
from operator import add

from cadgen import build123d as bd
from cadgen import glb, srgb, step, stl

FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"   # bold grotesque, like the logo

# ---- bottle body -----------------------------------------------------------
BODY_W = 76.0          # width (X)
BODY_D = 40.0          # depth (Y)
CORNER_R = 16.0        # plan-view corner radius (rounded, fluted sides)
BODY_H = 85.0          # straight wall height
SHOULDER_H = 15.0      # shoulder rise, body top -> neck
NECK_R = 13.0
NECK_H = 3.0
BASE_FILLET = 5.0
BASE_PUSHUP = 1.0

# ---- fluting on the narrow sides -------------------------------------------
FLUTE_R = 1.3
FLUTE_DEPTH = 0.9
FLUTE_Z0, FLUTE_Z1 = 8.0, 80.0
FLUTE_ANGLES = (14.0, 28.0, 42.0)   # on each plan corner arc, deg from the side

# ---- front label panel (the dark oval on the illustration) ------------------
PANEL_W, PANEL_H, PANEL_R = 62.0, 76.0, 26.0
PANEL_ZC = 44.0
PANEL_DEPTH = 0.8        # oval recessed into the glass
ART_DEPTH = 1.4          # artwork engraved deeper, below the panel floor
BORDER_OFFSET, BORDER_W = 2.5, 0.8

# ---- cap and collar --------------------------------------------------------
COLLAR_R, COLLAR_H = 13.5, 7.0
CAP_R, CAP_H = 14.5, 24.0
CAP_TOP_FILLET = 1.5
KNURL_N, KNURL_R, KNURL_DEPTH = 40, 0.6, 0.6
CAP_TEXT_DEPTH = 0.6
COLLAR_TEXT_DEPTH = 0.5

GLASS = "#D7E3D2"
BAKELITE = "#141414"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def front_plane(y: float) -> bd.Plane:
    """Plane at the given Y whose local X = +X, local Y = +Z, normal toward -Y
    (text drawn on it reads correctly when the bottle is viewed from the front)."""
    return bd.Plane(origin=(0, y, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))


def font_size_for_cap_height(cap_height: float) -> float:
    return cap_height / 0.729      # FreeSans Bold cap-height ratio


def glyph(ch: str, size: float) -> bd.Sketch:
    return bd.Text(ch, size, font_path=FONT,
                   text_align=(bd.TextAlign.CENTER, bd.TextAlign.BOTTOM))


def glyph_run(word: str, size: float, spacing: float):
    """Glyph sketches with their widths and arc-length centre positions
    (measured along the baseline from the word centre)."""
    glyphs = [glyph(ch, size) for ch in word]
    widths = []
    for g in glyphs:
        bb = g.bounding_box()
        widths.append(bb.max.X - bb.min.X)
    total = sum(widths) + spacing * (len(word) - 1)
    pos, centres = -total / 2, []
    for w in widths:
        centres.append(pos + w / 2)
        pos += w + spacing
    return glyphs, centres


def arc_text(word: str, cap_height: float, radius: float, centre_deg: float,
             tops_inward: bool, spacing: float = 0.45) -> bd.Sketch:
    """Word set on a circle of `radius` about the origin, centred at `centre_deg`.
    tops_inward=False: baseline inside, letters point outward (text over the top).
    tops_inward=True : baseline outside, letters point to the centre (seal-style
    text along the bottom); both read left to right."""
    size = font_size_for_cap_height(cap_height)
    glyphs, centres = glyph_run(word, size, spacing)
    pieces = []
    for g, s in zip(glyphs, centres):
        da = math.degrees(s / radius)
        ang = centre_deg + da if tops_inward else centre_deg - da
        rot = ang + 90 if tops_inward else ang - 90
        a = math.radians(ang)
        pieces.append(bd.Pos(radius * math.cos(a), radius * math.sin(a)) * bd.Rot(0, 0, rot) * g)
    return reduce(add, pieces)


def capsule(r: float, length: float) -> bd.Solid:
    body = bd.Cylinder(r, length)
    return body + bd.Pos(0, 0, length / 2) * bd.Sphere(r) + bd.Pos(0, 0, -length / 2) * bd.Sphere(r)


# ---------------------------------------------------------------------------
# bottle body
# ---------------------------------------------------------------------------
def plan_outline() -> bd.Sketch:
    return bd.RectangleRounded(BODY_W, BODY_D, CORNER_R)


def shoulder_sections() -> list:
    """Rounded-rectangle sections (always 8 edges, so the loft never twists)
    following an elliptical shoulder profile from the body top to the neck."""
    sections = []
    for z in (0.0, 2.5, 5.0, 7.5, 10.0, 12.0, 13.5, 14.5, 15.0):
        t = z / SHOULDER_H
        k = math.sqrt(max(0.0, 1.0 - t * t))
        x_half = NECK_R + (BODY_W / 2 - NECK_R) * k
        y_half = NECK_R + (BODY_D / 2 - NECK_R) * k
        r = min(CORNER_R, y_half - 0.4)
        sections.append(bd.Plane.XY.offset(BODY_H + z) * bd.RectangleRounded(2 * x_half, 2 * y_half, r))
    return sections


def blank_body() -> bd.Solid:
    prism = bd.extrude(plan_outline(), BODY_H)
    # base: round the bottom perimeter and add a shallow push-up
    bottom = bd.ShapeList(e for e in prism.edges() if e.bounding_box().max.Z < 1e-3)
    prism = bd.fillet(bottom, BASE_FILLET)
    prism = prism - bd.Cylinder(BODY_D / 2 - 6, BASE_PUSHUP * 2)
    shoulder = bd.loft(shoulder_sections(), ruled=False)
    top = shoulder.faces().sort_by(bd.Axis.Z)[-1]
    neck = bd.extrude(top, NECK_H)
    return prism + shoulder + neck


def flute_tools() -> bd.Compound:
    length = FLUTE_Z1 - FLUTE_Z0 - 2 * FLUTE_R
    cap = capsule(FLUTE_R, length)
    zc = (FLUTE_Z0 + FLUTE_Z1) / 2
    cx, cy = BODY_W / 2 - CORNER_R, BODY_D / 2 - CORNER_R
    stand = CORNER_R + FLUTE_R - FLUTE_DEPTH
    pts = [(BODY_W / 2 + FLUTE_R - FLUTE_DEPTH, 0.0), (cx + stand, cy), (cx + stand, -cy)]
    for a in FLUTE_ANGLES:
        r = math.radians(a)
        pts += [(cx + stand * math.cos(r), cy + stand * math.sin(r)),
                (cx + stand * math.cos(r), -cy - stand * math.sin(r))]
    pts += [(-x, y) for x, y in pts]
    return bd.Compound(children=[bd.Pos(x, y, zc) * cap for x, y in pts])


def shell(depth: float) -> bd.Solid:
    """The outer `depth` mm of the straight body walls, following the rounded plan."""
    h = BODY_H + SHOULDER_H + NECK_H + 1
    return bd.extrude(plan_outline(), h) - bd.extrude(bd.offset(plan_outline(), -depth), h)


def panel_outline() -> bd.Sketch:
    return bd.RectangleRounded(PANEL_W, PANEL_H, PANEL_R)


def dettol_band_letters() -> bd.Sketch:
    t = bd.Text("DETTOL", 9.4, font_path=FONT,
                text_align=(bd.TextAlign.CENTER, bd.TextAlign.BOTTOM))
    t = bd.scale(t, by=(1.15, 1.0, 1.0))          # extended face, like the logo
    bb = t.bounding_box()
    return bd.Pos(0, 12.0 - (bb.max.Y + bb.min.Y) / 2) * t


def sword() -> bd.Sketch:
    pommel = bd.Pos(0, 25.5) * bd.Circle(2.2)
    grip = bd.Pos(0, 21.9) * bd.Rectangle(2.6, 3.6)
    guard = bd.Pos(0, 19.1) * bd.Rectangle(14.0, 2.2) + bd.Pos(7, 19.1) * bd.Circle(1.1) + bd.Pos(-7, 19.1) * bd.Circle(1.1)
    blade = bd.Polygon((-1.8, 18.4), (1.8, 18.4), (0.0, -30.4), align=None)
    return pommel + grip + guard + blade


def artwork_level2() -> bd.Sketch:
    """Everything engraved below the panel floor, in panel coordinates (0,0 = panel centre)."""
    border = bd.offset(panel_outline(), -BORDER_OFFSET) - bd.offset(panel_outline(), -BORDER_OFFSET - BORDER_W)
    antiseptic = bd.Pos(0, 10.0) * arc_text("ANTISEPTIC", 3.6, 20.3, 90.0, tops_inward=False)
    non_poisonous = bd.Pos(0, -10.0) * arc_text("NON-POISONOUS", 3.0, 23.0, 221.0, tops_inward=True)
    germicidal = bd.Pos(0, -10.0) * arc_text("GERMICIDAL", 3.0, 23.0, 311.0, tops_inward=True)
    band = bd.Pos(0, 12.0) * bd.Rectangle(50.0, 9.5)
    art = border + antiseptic + non_poisonous + germicidal + band + sword()
    return art - dettol_band_letters()       # the band letters stay at the panel floor


def engrave_front(body: bd.Solid) -> bd.Solid:
    plane = front_plane(-BODY_D / 2 - 5)
    slab = BODY_D / 2 + 5
    panel_tool = bd.extrude(plane * (bd.Pos(0, PANEL_ZC) * panel_outline()), slab, dir=(0, 1, 0)) & shell(PANEL_DEPTH)
    art_tool = bd.extrude(plane * (bd.Pos(0, PANEL_ZC) * artwork_level2()), slab, dir=(0, 1, 0)) & shell(ART_DEPTH)
    return body - panel_tool - art_tool


def bottle_body() -> bd.Solid:
    body = blank_body()
    body = body - flute_tools()
    body = engrave_front(body)
    body.label = "glass_bottle"
    body.color = srgb(GLASS)
    return body


# ---------------------------------------------------------------------------
# cap with neck collar
# ---------------------------------------------------------------------------
def collar_text_tool(z0: float) -> bd.Solid:
    size = font_size_for_cap_height(3.2)
    glyphs, centres = glyph_run("DETTOL", size, 0.5)
    zb = z0 + COLLAR_H / 2 - 1.6
    plane = front_plane(-(COLLAR_R + 2.0))
    prisms = []
    for g, s in zip(glyphs, centres):
        prism = bd.extrude(plane * (bd.Pos(0, zb) * g), 4.0, dir=(0, 1, 0))
        prisms.append(prism.rotate(bd.Axis.Z, math.degrees(s / COLLAR_R)))
    annulus = (bd.Cylinder(COLLAR_R + 1, COLLAR_H, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
               - bd.Cylinder(COLLAR_R - COLLAR_TEXT_DEPTH, COLLAR_H, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)))
    return bd.Compound(children=prisms) & bd.Pos(0, 0, z0) * annulus


def cap_with_collar() -> bd.Solid:
    z_collar = BODY_H + SHOULDER_H + NECK_H
    z_cap = z_collar + COLLAR_H
    z_top = z_cap + CAP_H
    collar = bd.Pos(0, 0, z_collar) * bd.Cylinder(COLLAR_R, COLLAR_H, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    cap = bd.Pos(0, 0, z_cap) * bd.Cylinder(CAP_R, CAP_H, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    top_edge = bd.ShapeList(e for e in cap.edges() if e.bounding_box().min.Z > z_top - 1e-3)
    cap = bd.fillet(top_edge, CAP_TOP_FILLET)
    # vertical knurling around the cap
    k_len = CAP_H - CAP_TOP_FILLET - 3.0 - 2 * KNURL_R
    k = capsule(KNURL_R, k_len)
    knurls = []
    for i in range(KNURL_N):
        a = math.radians(360.0 * i / KNURL_N)
        r = CAP_R + KNURL_R - KNURL_DEPTH
        knurls.append(bd.Pos(r * math.cos(a), r * math.sin(a), z_cap + 1.5 + KNURL_R + k_len / 2) * k)
    cap = cap - bd.Compound(children=knurls)
    # "DETTOL" engraved into the top of the cap
    top_text = bd.Text("DETTOL", 5.0, font_path=FONT, text_align=(bd.TextAlign.CENTER, bd.TextAlign.CENTER))
    bb = top_text.bounding_box()
    top_text = bd.Pos(0, -(bb.max.Y + bb.min.Y) / 2, z_top) * top_text
    cap = cap - bd.extrude(top_text, CAP_TEXT_DEPTH, dir=(0, 0, -1))
    # "DETTOL" engraved around the front of the collar
    part = (cap + collar) - collar_text_tool(z_collar)
    part.label = "cap"
    part.color = srgb(BAKELITE)
    return part


# ---------------------------------------------------------------------------
@step(out="../STEP/dettol_bottle.step", materials={
    "definitions": {
        "glass": {"name": "Moulded glass", "roughness": 0.12, "metalness": 0.0, "clearcoat": 0.8, "clearcoatRoughness": 0.1},
        "bakelite": {"name": "Bakelite cap", "roughness": 0.45, "metalness": 0.0},
    },
    "assignments": [
        {"targets": ["#glass_bottle"], "material": "glass"},
        {"targets": ["#cap"], "material": "bakelite"},
    ],
})
@stl(out="../STL/dettol_bottle.stl", mesh_tolerance=0.01)
@glb(out="../GLB/dettol_bottle.glb", mesh_tolerance=0.01)
def dettol_bottle():
    body = bottle_body()
    cap = cap_with_collar()
    return bd.Compound(children=[body, cap], label="dettol_bottle")


if __name__ == "__main__":
    dettol_bottle()
