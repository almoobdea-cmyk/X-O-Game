#!/usr/bin/env python3
"""
Parametric 3D model of the Madinah Piazza convertible umbrella (SL Rasch "U26 Piazza").

Units: metres, Y up, origin on the piazza floor at the column axis.
Dimensions are taken from the designer's published technical data and from
measurements of the published section drawing (see REFERENCE.md).

Usage:  python3 build_umbrella.py            -> writes both variants + viewer.html
Needs:  numpy, Pillow
"""
import base64, io, json, math, os, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SQ2 = math.sqrt(2.0)

# --------------------------------------------------------------------------
# Dimensions (m).  [D] = from designer data/drawing label, [M] = measured off
# the section drawing (scale fixed by 21.7 m folded height), [P] = estimated
# from photographs.
# --------------------------------------------------------------------------
HALF = 12.75            # [D] membrane 25.5 x 25.5 m
TIP_STEP = HALF / 3.0   # [P] 6 scallops per side -> 24 edge points (8 active + 16 passive arms [D])
VARIANTS = {            # [D] two deployed heights so neighbouring canopies overlap
    "low":  dict(tip=14.5, elbow=15.35),
    "high": dict(tip=15.3, elbow=14.90),
}
R_FUNNEL, H_FUNNEL = 0.55, 10.30     # [M] membrane collar above the lantern
H_ARM_PIVOT = 14.15                  # [M] arm root hinge on the mast
H_UPPER_PIVOT = 16.20                # [M] upper strut hinge
H_LOWER_PIVOT = 10.86                # [M] lower strut hinge
R_ELBOW = 6.60                       # [M] inner/outer arm hinge radius (middle arm)
H_FAN = 3.96                         # [M] evaporative cooling fan axis
H_SHAFT0, H_SHAFT1 = 1.40, 5.50      # [M]
H_FRIEZE0, H_FRIEZE1 = 6.75, 7.55    # [M]
H_LANT0, H_LANT1 = 7.90, 9.35        # [M] lantern (piazza + facade lighting)


# --------------------------------------------------------------------------
# Mesh container
# --------------------------------------------------------------------------
class Mesh:
    def __init__(self):
        self.P, self.N, self.UV, self.I = [], [], [], []

    def _n(self, a, b, c):
        n = np.cross(np.subtract(b, a), np.subtract(c, a))
        l = np.linalg.norm(n)
        return n / l if l > 1e-12 else np.array([0.0, 1.0, 0.0])

    def tri(self, a, b, c, uva=(0, 0), uvb=(1, 0), uvc=(0, 1)):
        n = self._n(a, b, c)
        k = len(self.P)
        self.P += [a, b, c]; self.N += [n, n, n]; self.UV += [uva, uvb, uvc]
        self.I += [k, k + 1, k + 2]

    def quad(self, a, b, c, d, uv=((0, 0), (1, 0), (1, 1), (0, 1)), hint=None):
        """Flat quad a-b-c-d.  If hint (outward direction) is given, fix winding."""
        n = self._n(a, b, c)
        if np.linalg.norm(np.cross(np.subtract(b, a), np.subtract(c, a))) < 1e-12:
            n = self._n(a, c, d)
        if hint is not None and np.dot(n, hint) < 0:
            a, b, c, d = a, d, c, b
            uv = (uv[0], uv[3], uv[2], uv[1])
            n = -n
        k = len(self.P)
        self.P += [a, b, c, d]; self.N += [n] * 4; self.UV += list(uv)
        self.I += [k, k + 1, k + 2, k, k + 2, k + 3]

    def smooth(self, verts, tris, uvs=None, up_hint=None):
        verts = np.asarray(verts, float); tris = np.asarray(tris, int)
        nrm = np.zeros_like(verts)
        fn = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
        for j in range(3):
            np.add.at(nrm, tris[:, j], fn)
        if up_hint is not None and np.dot(nrm.sum(0), up_hint) < 0:
            tris = tris[:, ::-1]; nrm = -nrm
        l = np.linalg.norm(nrm, axis=1, keepdims=True); l[l < 1e-12] = 1
        nrm /= l
        k = len(self.P)
        self.P += list(verts); self.N += list(nrm)
        self.UV += list(uvs) if uvs is not None else [(0, 0)] * len(verts)
        self.I += list((tris + k).ravel())

    def arrays(self):
        return (np.asarray(self.P, np.float32), np.asarray(self.N, np.float32),
                np.asarray(self.UV, np.float32), np.asarray(self.I, np.uint32))


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def octa(a, d=None):
    """Octagon in XZ: main faces (+-X, +-Z) at apothem a, diagonal faces at apothem d."""
    d = a if d is None else d
    w = max(d * SQ2 - a, 0.0)
    w = min(w, a)
    pts = [(a, -w), (a, w), (w, a), (-w, a), (-a, w), (-a, -w), (-w, -a), (w, -a)]
    return pts  # CCW by angle (x=cos, z=sin)


def loft(m, stations, uv_mode="wrap", vscale=1.0, cap_top=False, cap_bot=False, faces=None):
    """Loft octagonal stations [(y, a, d)] upward.  uv_mode: 'wrap' or 'face'."""
    secs = [(y, octa(a, d)) for (y, a, d) in stations]
    for k in range(len(secs) - 1):
        y0, s0 = secs[k]; y1, s1 = secs[k + 1]
        for i in range(8):
            if faces is not None and i not in faces:
                continue
            j = (i + 1) % 8
            b0 = (s0[i][0], y0, s0[i][1]); b1 = (s0[j][0], y0, s0[j][1])
            t0 = (s1[i][0], y1, s1[i][1]); t1 = (s1[j][0], y1, s1[j][1])
            if uv_mode == "face":
                T = stations[-1][0] - stations[0][0]
                v0 = 1 - (y0 - stations[0][0]) / T; v1 = 1 - (y1 - stations[0][0]) / T
                uv = ((1, v0), (1, v1), (0, v1), (0, v0))
            else:
                uv = ((i / 8 * 4, -y0 * vscale), (i / 8 * 4, -y1 * vscale),
                      ((i + 1) / 8 * 4, -y1 * vscale), ((i + 1) / 8 * 4, -y0 * vscale))
            m.quad(b0, t0, t1, b1, uv)
    if cap_top:
        y, s = secs[-1]
        for i in range(8):
            j = (i + 1) % 8
            m.tri((0, y, 0), (s[j][0], y, s[j][1]), (s[i][0], y, s[i][1]))
    if cap_bot:
        y, s = secs[0]
        for i in range(8):
            j = (i + 1) % 8
            m.tri((0, y, 0), (s[i][0], y, s[i][1]), (s[j][0], y, s[j][1]))


def lathe(m, profile, n=32, flutes=0, flute_depth=0.0):
    """Smooth surface of revolution about Y.  profile = [(r, y)] bottom->top."""
    V, UVs, T = [], [], []
    for k, (r, y) in enumerate(profile):
        for i in range(n + 1):
            th = 2 * math.pi * i / n
            rr = r * (1 - flute_depth * (0.5 - 0.5 * math.cos(flutes * th))) if flutes else r
            V.append((rr * math.cos(th), y, rr * math.sin(th)))
            UVs.append((i / n * 4, k / max(len(profile) - 1, 1)))
    for k in range(len(profile) - 1):
        for i in range(n):
            a = k * (n + 1) + i; b = a + 1; c = a + n + 1; d = c + 1
            T += [(a, c, d), (a, d, b)]
    m.smooth(V, T, UVs)


def _frame(p0, p1, up=(0, 1, 0)):
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    d = p1 - p0; L = np.linalg.norm(d); d = d / L
    s = np.cross(d, up)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(d, (1, 0, 0))
    s /= np.linalg.norm(s)
    u = np.cross(s, d)
    return p0, p1, d, s, u


def beam(m, p0, p1, w0, h0, w1=None, h1=None, up=(0, 1, 0), uvlen=1.0):
    """Tapered rectangular box along p0->p1 (w across, h along 'up')."""
    w1 = w0 if w1 is None else w1; h1 = h0 if h1 is None else h1
    p0, p1, d, s, u = _frame(p0, p1, up)
    A = [p0 + s * sx * w0 / 2 + u * sy * h0 / 2 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    B = [p1 + s * sx * w1 / 2 + u * sy * h1 / 2 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    c = (p0 + p1) / 2
    L = np.linalg.norm(p1 - p0) / uvlen
    for i in range(4):
        j = (i + 1) % 4
        q = [A[i], A[j], B[j], B[i]]
        m.quad(*q, uv=((0, 0), (1, 0), (1, L), (0, L)), hint=np.mean(q, 0) - c)
    m.quad(A[0], A[1], A[2], A[3], hint=-d)
    m.quad(B[0], B[1], B[2], B[3], hint=d)


def cyl(m, p0, p1, r0, r1=None, n=14, caps=True):
    r1 = r0 if r1 is None else r1
    p0, p1, d, s, u = _frame(p0, p1)
    V, T = [], []
    for i in range(n + 1):
        th = 2 * math.pi * i / n
        e = s * math.cos(th) + u * math.sin(th)
        V += [p0 + e * r0, p1 + e * r1]
    for i in range(n):
        a = 2 * i; b = a + 1; c = a + 2; e = a + 3
        T += [(a, c, e), (a, e, b)]
    k0 = len(m.P)
    m.smooth(V, T)
    # make sure the side faces outward
    nn = np.asarray(m.N[k0]); vv = np.asarray(m.P[k0]) - p0
    if np.dot(nn, vv) < 0:
        for q in range(k0, len(m.N)):
            m.N[q] = -np.asarray(m.N[q])
        idx = m.I[-len(T) * 3:]
        m.I[-len(T) * 3:] = [x for t in zip(idx[0::3], idx[2::3], idx[1::3]) for x in t]
    if caps:
        for (p, r, dd) in ((p0, r0, -d), (p1, r1, d)):
            ring = [p + (s * math.cos(2 * math.pi * i / n) + u * math.sin(2 * math.pi * i / n)) * r for i in range(n)]
            for i in range(n):
                a, b = ring[i], ring[(i + 1) % n]
                if np.dot(np.cross(a - p, b - p), dd) < 0:
                    a, b = b, a
                m.tri(p, a, b)


def sphere(m, c, r, n=16, sy=1.0):
    prof = [(r * math.sin(math.pi * k / n), c[1] - r * sy * math.cos(math.pi * k / n)) for k in range(n + 1)]
    sub = Mesh(); lathe(sub, prof, n)
    k = len(m.P)
    m.P += [(p[0] + c[0], p[1], p[2] + c[2]) for p in sub.P]; m.N += sub.N; m.UV += sub.UV
    m.I += [i + k for i in sub.I]


def torus(m, c, R, r, axis="y", n=40, k=10):
    V, T = [], []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        for j in range(k + 1):
            b = 2 * math.pi * j / k
            x = (R + r * math.cos(b)) * math.cos(a); z = (R + r * math.cos(b)) * math.sin(a); y = r * math.sin(b)
            V.append((x, y, z) if axis == "y" else (x, z, y) if axis == "z" else (y, x, z))
    for i in range(n):
        for j in range(k):
            a = i * (k + 1) + j; b = a + 1; c2 = a + k + 1; d = c2 + 1
            T += [(a, b, d), (a, d, c2)]
    V = np.asarray(V) + np.asarray(c)
    k0 = len(m.P)
    m.smooth(V, T)
    # orient outward from tube centre line (check one vertex)
    p = np.asarray(m.P[k0 + 0]); cc = np.asarray(c, float)
    radial = p - cc
    if np.dot(np.asarray(m.N[k0]), radial) < 0:
        for q in range(k0, len(m.N)):
            m.N[q] = -np.asarray(m.N[q])
        idx = m.I[-len(T) * 3:]
        m.I[-len(T) * 3:] = [x for t in zip(idx[0::3], idx[2::3], idx[1::3]) for x in t]


def pchip(xs, ys):
    """Monotone cubic interpolant (Fritsch-Carlson)."""
    xs = np.asarray(xs, float); ys = np.asarray(ys, float)
    h = np.diff(xs); dl = np.diff(ys) / h
    mm = np.zeros_like(xs); mm[0] = dl[0]; mm[-1] = dl[-1]
    for i in range(1, len(xs) - 1):
        mm[i] = 0 if dl[i - 1] * dl[i] <= 0 else 2 * dl[i - 1] * dl[i] / (dl[i - 1] + dl[i])

    def f(x):
        x = np.clip(x, xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        t = (x - xs[i]) / h[i]
        return (ys[i] * (2 * t ** 3 - 3 * t ** 2 + 1) + h[i] * mm[i] * (t ** 3 - 2 * t ** 2 + t)
                + ys[i + 1] * (-2 * t ** 3 + 3 * t ** 2) + h[i] * mm[i + 1] * (t ** 3 - t ** 2))
    return f


# --------------------------------------------------------------------------
# Membrane surface definition (shared by mesh and texture)
# --------------------------------------------------------------------------
# Funnel profile measured off the section drawing: fraction of rise vs r/R.
FUNNEL = pchip([0.0, 0.04, 0.10, 0.20, 0.35, 0.50, 0.70, 1.0],
               [0.0, 0.00, 0.12, 0.31, 0.62, 0.855, 0.96, 1.0])
SCALLOP_IN = 0.055      # [P] edge-cable inset between arm tips (fraction of radius)
SCALLOP_SAG = 0.38      # [P] edge sag between tips (m)


def edge_base(q):
    """q in [0,24): edge parameter, integer q = arm tip.  Returns XZ point on the 25.5 m square."""
    q = q % 24.0
    sd = int(q // 6) % 4; j = q - 6 * sd
    t = -HALF + TIP_STEP * j
    x, z = HALF, t
    for _ in range(sd):
        x, z = -z, x
    return x, z


def edge_point(q):
    u = q - math.floor(q)
    x, z = edge_base(q)
    k = 1 - SCALLOP_IN * 4 * u * (1 - u)
    return x * k, z * k, u


def membrane_point(q, sig, tip_h):
    ex, ez, u = edge_point(q)
    Re = math.hypot(ex, ez)
    bx, bz = edge_base(q); Rb = math.hypot(bx, bz)
    r = R_FUNNEL + (Re - R_FUNNEL) * sig
    Rblend = (Rb ** sig) * (14.0 ** (1 - sig))
    he = tip_h - 0.15 - SCALLOP_SAG * 4 * u * (1 - u)
    y = H_FUNNEL + (he - H_FUNNEL) * float(FUNNEL(min(r / Rblend, 1.0) if sig < 1 else 1.0))
    # blend direction: uniform pleats at the collar, straight to the tips outside
    th_tip = math.atan2(ez, ex); th_uni = math.radians(-45 + 15 * q)
    dth = (th_tip - th_uni + math.pi) % (2 * math.pi) - math.pi
    b = min(max((r - 1.0) / 6.0, 0), 1); b = b * b * (3 - 2 * b)
    th = th_uni + dth * b
    return r * math.cos(th), y, r * math.sin(th)


def build_membrane(tip_h):
    m = Mesh()
    NQ, NS = 24 * 10, 44
    sigs = np.linspace(0, 1, NS + 1) ** 1.6
    V, UVs, T = [], [], []
    for a in range(NQ + 1):
        q = 24.0 * a / NQ
        for s in sigs:
            x, y, z = membrane_point(q if a < NQ else 0.0, float(s), tip_h)
            V.append((x, y, z)); UVs.append((x / 27.0 + 0.5, z / 27.0 + 0.5))
    for a in range(NQ):
        for k in range(NS):
            i0 = a * (NS + 1) + k; i1 = i0 + 1; j0 = i0 + NS + 1; j1 = j0 + 1
            T += [(i0, j0, j1), (i0, j1, i1)]
    m.smooth(V, T, UVs, up_hint=(0, 1, 0))
    return m


# --------------------------------------------------------------------------
# Textures
# --------------------------------------------------------------------------
BLUE = (46, 68, 122)


def tex_membrane(size=2048, ss=2):
    S = size * ss
    im = Image.new("RGB", (S, S), (244, 240, 230))
    d = ImageDraw.Draw(im)
    px = lambda x, z: ((x / 27.0 + 0.5) * S, (z / 27.0 + 0.5) * S)

    def pol(q, r):
        """plan point for edge-parameter q at plan radius r (same blend as the mesh)."""
        ex, ez, _ = edge_point(q)
        th_tip = math.atan2(ez, ex); th_uni = math.radians(-45 + 15 * q)
        dth = (th_tip - th_uni + math.pi) % (2 * math.pi) - math.pi
        b = min(max((r - 1.0) / 6.0, 0), 1); b = b * b * (3 - 2 * b)
        th = th_uni + dth * b
        return px(r * math.cos(th), r * math.sin(th))

    def redge(q):
        ex, ez, _ = edge_point(q); return math.hypot(ex, ez)

    # seams: 24 to the arm tips (heavy), 24 to scallop centres, 48 light pleat seams
    for i in range(96):
        q = i / 4.0
        wt = 7 if i % 4 == 0 else 4 if i % 2 == 0 else 2
        r1 = redge(q) if i % 2 == 0 else redge(q) * 0.62
        pts = [pol(q, R_FUNNEL + (r1 - R_FUNNEL) * k / 60) for k in range(61)]
        d.line(pts, fill=BLUE if i % 2 == 0 else (120, 135, 170), width=wt * ss // 2 + 1)

    def petal(qc, r0, r1, W, width=5, fill=None):
        L, R = [], []
        for k in range(41):
            t = k / 40.0
            hw = W * (math.sin(math.pi * t ** 0.75) ** 0.85) * (1 - 0.25 * t)
            r = r0 + (r1 - r0) * t
            L.append(pol(qc - hw, r)); R.append(pol(qc + hw, r))
        poly = L + R[::-1]
        if fill:
            d.polygon(poly, fill=fill)
        d.line(poly + [poly[0]], fill=BLUE, width=width * ss // 2 + 1, joint="curve")

    def diamond(qc, r0, r1, W, rim=0.22):
        rm = r0 + (r1 - r0) * 0.42
        outer = [pol(qc, r0), pol(qc + W, rm), pol(qc, r1), pol(qc - W, rm)]
        d.polygon(outer, fill=(250, 247, 240)); d.line(outer + [outer[0]], fill=BLUE, width=3 * ss // 2 + 1)
        g = rim
        inner = [pol(qc, r0 + (r1 - r0) * g * 0.8), pol(qc + W * (1 - g * 1.5), rm),
                 pol(qc, r1 - (r1 - r0) * g * 0.8), pol(qc - W * (1 - g * 1.5), rm)]
        d.polygon(inner, fill=(84, 106, 152))

    for i in range(24):                       # outer tier of tall lotus arches (on scallop centres)
        petal(i + 0.5, 4.0, 8.6, 0.50, width=4)
    for i in range(24):                       # arches enclosing the diamonds (on tip seams)
        petal(i, 2.5, 7.2, 0.50, width=5)
    for i in range(24):
        diamond(i, 3.5, 5.9, 0.36)            # large diamond ring
    for i in range(24):
        diamond(i + 0.5, 5.6, 7.2, 0.20)      # small diamond ring
    for i in range(24):                       # inner lotus tiers around the collar
        petal(i + 0.5, 1.3, 4.3, 0.47, width=4)
        petal(i, 0.7, 3.1, 0.42, width=3)

    # scalloped edge trim + tip motifs
    edge = [px(*edge_point(24.0 * k / 960)[:2]) for k in range(961)]
    d.line(edge, fill=BLUE, width=9 * ss, joint="curve")
    edge2 = [px(*(np.array(edge_point(24.0 * k / 960)[:2]) * 0.972)) for k in range(961)]
    d.line(edge2, fill=BLUE, width=2 * ss)
    for i in range(24):
        ex, ez, _ = edge_point(i); R = math.hypot(ex, ez)
        tip = [pol(i, R * 0.995), pol(i + 0.10, R * 0.945), pol(i, R * 0.89), pol(i - 0.10, R * 0.945)]
        d.polygon(tip, fill=(70, 96, 150)); d.line(tip + [tip[0]], fill=BLUE, width=2 * ss)
    # fabric weave shading
    rng = np.random.default_rng(3)
    a = np.asarray(im.resize((size, size), Image.LANCZOS), np.float32)
    a += rng.normal(0, 1.0, (size, size, 1))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _noise(size, seed, scale):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size), np.float32)
    for o, amp in ((4, 0.5), (16, 0.3), (64, 0.2)):
        n = rng.random((size // o + 1, size // o + 1)).astype(np.float32)
        im = Image.fromarray((n * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        out += amp * np.asarray(im, np.float32) / 255
    return (out - out.mean()) * scale


def tex_stone(size=512):
    """Beige granite-like cladding with one horizontal joint per V repeat."""
    rng = np.random.default_rng(1)
    base = np.array([203, 182, 150], np.float32)
    a = np.ones((size, size, 3), np.float32) * base
    a += _noise(size, 5, 26)[..., None]
    a += rng.normal(0, 7, (size, size, 1))
    spk = rng.random((size, size)) > 0.985
    a[spk] *= 0.78
    a[:5, :, :] *= 0.72; a[5:8, :, :] *= 1.06            # joint + highlight
    for x in (0, size // 2):
        a[:, x:x + 3, :] *= 0.86                          # vertical joints
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def tex_carved(size=512):
    """Capital face: arabesque shield medallion in low relief (painted shading)."""
    im = Image.fromarray(np.asarray(tex_stone(size))[8:, 8:].copy()).resize((size, size))
    hi = Image.new("L", (size, size), 0); lo = Image.new("L", (size, size), 0)
    dh, dl = ImageDraw.Draw(hi), ImageDraw.Draw(lo)
    c = size / 2

    def shape(scale, off=0):
        pts = []
        for k in range(200):
            t = k / 200 * 2 * math.pi
            # pointed shield / palmette outline
            r = scale * (0.62 + 0.10 * math.cos(8 * t)) * (1 + 0.28 * math.cos(t) ** 3)
            pts.append((c + r * math.sin(t) * 0.78, c * 0.98 - r * math.cos(t) * 1.0 + off))
        return pts
    for sc, wd in ((0.40 * size, 7), (0.30 * size, 5), (0.19 * size, 5)):
        p = shape(sc)
        dl.line(p + [p[0]], fill=255, width=wd)
        dh.line([(x - 3, y - 3) for x, y in p + [p[0]]], fill=255, width=3)
    for k in range(8):                                   # rosette
        t = k * math.pi / 4
        x, y = c + 0.085 * size * math.sin(t), c * 0.98 - 0.085 * size * math.cos(t)
        dl.ellipse((x - 20, y - 20, x + 20, y + 20), outline=255, width=4)
    dl.ellipse((c - 16, c * 0.98 - 16, c + 16, c * 0.98 + 16), fill=255)
    for sx in (-1, 1):                                   # scroll tendrils in the corners
        for k in range(60):
            t = k / 60 * 3.2 * math.pi; r = 6 + t * 7
            x = c + sx * (0.36 * size + r * math.cos(t) * 0.6); y = 0.14 * size + r * math.sin(t) * 0.6
            dl.ellipse((x - 3, y - 3, x + 3, y + 3), fill=255)
            y2 = 0.88 * size - r * math.sin(t) * 0.5
            dl.ellipse((x - 3, y2 - 3, x + 3, y2 + 3), fill=255)
    dl.rectangle((6, 6, size - 6, size - 6), outline=255, width=5)
    a = np.asarray(im, np.float32)
    a *= (1 - 0.42 * np.asarray(lo.filter(ImageFilter.GaussianBlur(1.2)), np.float32)[..., None] / 255)
    a *= (1 + 0.16 * np.asarray(hi.filter(ImageFilter.GaussianBlur(1.5)), np.float32)[..., None] / 255)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def tex_frieze(size=512):
    """Dark grey-green frieze panel.  The real plaques carry inscriptions; an abstract
    geometric band is used here instead of imitating sacred calligraphy."""
    a = np.ones((size, size, 3), np.float32) * np.array([92, 96, 84], np.float32)
    a += _noise(size, 9, 18)[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im)
    d.rectangle((26, 60, size - 26, size - 60), outline=(60, 62, 52), width=8)
    d.rectangle((34, 68, size - 34, size - 68), fill=(70, 78, 66), outline=(150, 140, 100), width=3)
    gold = (176, 160, 110)
    y0, y1 = size * 0.36, size * 0.64; n = 9; w = (size - 110) / n
    for i in range(n):                                   # interlaced meander
        x = 55 + i * w
        d.line([(x, y1), (x, y0), (x + w * 0.6, y0), (x + w * 0.6, (y0 + y1) / 2), (x + w * 0.3, (y0 + y1) / 2)], fill=gold, width=5)
        d.line([(x + w * 0.3, y1), (x + w, y1)], fill=gold, width=5)
    d.line([(55, y0 - 22), (size - 55, y0 - 22)], fill=gold, width=2)
    d.line([(55, y1 + 22), (size - 55, y1 + 22)], fill=gold, width=2)
    return im


def tex_mosaic(size=256):
    """Glass-mosaic strip of the arm cladding panels (GRP + glass tiles [D])."""
    n = 32; t = size // n
    rng = np.random.default_rng(11)
    im = Image.new("RGB", (size, size)); d = ImageDraw.Draw(im)
    for j in range(n):
        for i in range(n):
            u, v = (i + .5) / n - .5, ((j + .5) / n * 2) % 1 - .5
            k = abs(u) + abs(v)
            if abs(u) > 0.40:
                col = (196, 170, 96)                      # gold border
            elif k < 0.16:
                col = (190, 164, 90)
            elif k < 0.30:
                col = (58, 110, 128)                      # turquoise diamond
            elif abs(k - 0.42) < 0.05:
                col = (40, 66, 118)
            else:
                col = (232, 226, 210)
            j2 = rng.integers(-9, 9)
            col = tuple(int(np.clip(c + j2, 0, 255)) for c in col)
            d.rectangle((i * t, j * t, i * t + t - 2, j * t + t - 2), fill=col)
            d.rectangle((i * t + t - 1, j * t, i * t + t, j * t + t), fill=(150, 146, 136))
            d.rectangle((i * t, j * t + t - 1, i * t + t, j * t + t), fill=(150, 146, 136))
    return im


def tex_floor(size=512):
    a = np.ones((size, size, 3), np.float32) * np.array([226, 222, 214], np.float32)
    a += _noise(size, 21, 30)[..., None]
    v = _noise(size, 22, 1.0)
    a[np.abs(v) < 0.012] -= 26                            # veins
    for k in (0, size // 2):
        a[k:k + 3, :, :] = 150; a[:, k:k + 3, :] = 150
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def tex_glass(size=256):
    """Lantern diffuser: warm prismatic glass with horizontal louvre shading."""
    a = np.ones((size, size, 3), np.float32) * np.array([255, 238, 200], np.float32)
    y = np.arange(size)[:, None]
    a *= (0.80 + 0.20 * np.abs(np.sin(y / size * math.pi * 9)))[..., None]
    x = np.arange(size)[None, :]
    a *= (0.93 + 0.07 * np.cos(x / size * math.pi * 40))[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
MATERIALS = {
    "membrane":  dict(tex="membrane", rough=0.85, metal=0.0, double=True),
    "stone":     dict(tex="stone", rough=0.55, metal=0.0),
    "base":      dict(color=(0.80, 0.74, 0.64), tex="stone", rough=0.35, metal=0.0),
    "carved":    dict(tex="carved", rough=0.7, metal=0.0),
    "frieze":    dict(tex="frieze", rough=0.5, metal=0.1),
    "gold":      dict(color=(1.0, 0.76, 0.33), rough=0.22, metal=1.0),
    "gold_dark": dict(color=(0.72, 0.52, 0.20), rough=0.4, metal=1.0),
    "glass":     dict(tex="glass", rough=0.25, metal=0.0, emissive=(1.0, 0.86, 0.62), estr=1.0),
    "steel":     dict(color=(0.93, 0.92, 0.89), rough=0.45, metal=0.15),
    "mosaic":    dict(tex="mosaic", rough=0.3, metal=0.0),
    "fan":       dict(color=(0.90, 0.86, 0.78), rough=0.6, metal=0.0),
    "fan_dark":  dict(color=(0.35, 0.33, 0.30), rough=0.6, metal=0.3),
    "floor":     dict(tex="floor", rough=0.18, metal=0.0),
}


# --------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------
def build_parts(variant):
    V = VARIANTS[variant]
    tip_h, elbow_h = V["tip"], V["elbow"]
    parts = []

    def add(name, group, mesh, mat, rot=None):
        parts.append(dict(name=name, group=group, mesh=mesh, mat=mat, rot=rot))

    R4 = [0, 90, 180, 270]

    # ---------------- column -------------------------------------------------
    m = Mesh()                                            # plinth + torus mouldings [M]
    loft(m, [(0, .94, None), (.10, .94, None), (.10, .87, None), (.62, .87, None), (.70, .80, None),
             (.78, .80, None), (.84, .76, None), (.92, .80, None), (1.00, .80, None), (1.07, .75, None),
             (1.13, .67, None), (1.21, .67, None), (1.31, .59, None), (H_SHAFT0, .55, None)], vscale=1.2, cap_bot=True)
    add("Base_Plinth", "Column", m, "base")
    m = Mesh()                                            # shaft, 1.10 m across flats
    loft(m, [(H_SHAFT0, .55, None), (H_SHAFT1, .55, None)], vscale=1 / 1.025)
    add("Shaft", "Column", m, "stone")
    m = Mesh()                                            # astragal rings under the capital
    loft(m, [(H_SHAFT1, .55, None), (5.53, .60, None), (5.58, .60, None), (5.60, .57, None),
             (5.63, .61, None), (5.68, .61, None), (5.70, .56, None)], vscale=1.0)
    add("Astragal", "Column", m, "base")
    m = Mesh()                                            # capital: octagon -> chamfered square [P]
    loft(m, [(5.70, .56, .56), (5.95, .58, .60), (6.35, .66, .76), (H_FRIEZE0 - .08, .71, .86)], uv_mode="face")
    add("Capital_Carved", "Column", m, "carved")
    m = Mesh()
    loft(m, [(H_FRIEZE0 - .08, .71, .86), (H_FRIEZE0 - .06, .74, .89), (H_FRIEZE0, .74, .89), (H_FRIEZE0, .71, .86)])
    loft(m, [(H_FRIEZE1, .71, .86), (H_FRIEZE1, .75, .90), (H_FRIEZE1 + .07, .75, .90),
             (H_FRIEZE1 + .12, .72, .87), (H_LANT0, .80, .95)])
    add("Frieze_Cornices", "Column", m, "base")
    m = Mesh()
    loft(m, [(H_FRIEZE0, .71, .86), (H_FRIEZE1, .71, .86)], uv_mode="face")
    add("Frieze_Panels", "Column", m, "frieze")

    # ---------------- lantern ------------------------------------------------
    m = Mesh()
    loft(m, [(H_LANT0, .80, .95), (H_LANT1, .92, 1.08)], vscale=1.0)
    add("Lantern_Body", "Lantern", m, "stone")
    m = Mesh()                                            # gold crown / membrane collar
    loft(m, [(H_LANT1, .92, 1.08), (H_LANT1, 1.00, 1.16), (H_LANT1 + .10, 1.02, 1.18), (H_LANT1 + .16, .96, 1.10),
             (H_LANT1 + .30, .80, .90), (9.95, .62, .66), (H_FUNNEL, .56, .56), (H_FUNNEL + .25, .50, .50)])
    add("Lantern_Crown", "Lantern", m, "gold")
    m = Mesh()                                            # cresting leaves on the cornice
    for s in (-0.42, -0.14, 0.14, 0.42):
        y = H_LANT1 + .10
        m.tri((1.02, y, s - .12), (1.02, y, s + .12), (1.00, y + .22, s))
        m.tri((1.02, y, s + .12), (1.02, y, s - .12), (0.98, y + .22, s))
    add("Lantern_Cresting", "Lantern", m, "gold", R4)

    # one bay lantern on the +X face (instanced x4): gold frame, glass, louvres, gable
    x0 = 0.84; x1 = 1.20; hw = 0.40; yb, yt = H_LANT0 + 0.12, H_LANT1 - 0.12
    g = Mesh(); gl = Mesh()
    fr = 0.07
    for z in (-hw + fr / 2, hw - fr / 2):                 # corner posts
        beam(g, (x1 - fr / 2, yb, z), (x1 - fr / 2, yt, z), fr, fr, up=(1, 0, 0))
        beam(g, (x0, yb, z), (x0, yt, z), fr, fr, up=(1, 0, 0))
    for y in (yb + fr / 2, yt - fr / 2):                  # rails front + sides
        beam(g, (x1 - fr / 2, y, -hw), (x1 - fr / 2, y, hw), fr, fr)
        for z in (-hw + fr / 2, hw - fr / 2):
            beam(g, (x0, y, z), (x1, y, z), fr, fr)
    beam(g, ((x0 + x1) / 2, yb - .03, 0), ((x0 + x1) / 2, yb + .01, 0), 2 * hw + .08, x1 - x0 + .1, up=(1, 0, 0))  # sill
    beam(g, ((x0 + x1) / 2 - .05, yb - .16, 0), ((x0 + x1) / 2 - .05, yb - .03, 0), 2 * hw - .2, .2, 2 * hw + .04, x1 - x0, up=(1, 0, 0))
    for sgn in (-1, 1):                                   # arch spandrels
        zc = sgn * (hw - fr)
        g.quad((x1 - .02, yt - fr, zc), (x1 - .02, yt - fr - .26, zc), (x1 - .02, yt - fr - .10, zc - sgn * .10),
               (x1 - .02, yt - fr, zc - sgn * .26), hint=(1, 0, 0))
    n_l = 7
    for k in range(n_l):                                  # louvre blades
        y = yb + fr + (yt - yb - 2 * fr) * (k + .5) / n_l
        beam(g, (x1 - .05, y, -hw + fr), (x1 - .05, y, hw - fr), .012, .05, up=(1, 0.6, 0))
    beam(g, (x1 - .03, yb, 0), (x1 - .03, yt, 0), .025, .025, up=(1, 0, 0))     # mullion
    # gable roof
    yr = yt + .02; ridge = yt + .34
    A = (x0 - .02, yr, -hw - .06); B = (x1 + .07, yr, -hw - .06); C = (x1 + .07, yr, hw + .06); D = (x0 - .02, yr, hw + .06)
    E = (x0 - .02, ridge, 0); F = (x1 + .02, ridge - .04, 0)
    g.quad(A, B, F, E, hint=(0, 1, -1)); g.quad(D, C, F, E, hint=(0, 1, 1)); g.tri(B, C, F)
    g.quad(A, B, C, D, hint=(0, -1, 0))
    sphere(g, (x1 + .02, ridge + .05, 0), .05, 8)
    # glass (front + sides), set just inside the frame
    gl.quad((x1 - .09, yb, -hw + fr), (x1 - .09, yb, hw - fr), (x1 - .09, yt, hw - fr), (x1 - .09, yt, -hw + fr), hint=(1, 0, 0))
    for sgn in (-1, 1):
        z = sgn * (hw - fr * .8)
        gl.quad((x0, yb, z), (x1 - .09, yb, z), (x1 - .09, yt, z), (x0, yt, z), hint=(0, 0, sgn))
    add("Lantern_Bay_Frame", "Lantern", g, "gold", R4)
    add("Lantern_Bay_Glass", "Lantern", gl, "glass", R4)

    # ---------------- mast, hubs, finial ------------------------------------
    m = Mesh()
    cyl(m, (0, H_FUNNEL, 0), (0, 16.45, 0), .30, .27, n=20)                    # upper steel column / telescopic shaft
    for y, r, hgt in ((H_LOWER_PIVOT, .44, .40), (H_ARM_PIVOT, .46, .55), (H_UPPER_PIVOT, .42, .40)):
        mm = Mesh(); loft(mm, [(y - hgt / 2, r, None), (y + hgt / 2, r, None)], cap_top=True, cap_bot=True)
        m.P += mm.P; k = len(m.N); m.N += mm.N; m.UV += mm.UV; m.I += [i + k for i in mm.I]
    lathe(m, [(.30, 16.40), (.52, 16.45), (.50, 16.60), (.34, 16.78)], 24)
    add("Mast_and_Hubs", "Structure", m, "steel")
    m = Mesh()                                            # gilded crown and lance [D: gold-plated]
    lathe(m, [(.86, 16.55), (.90, 16.60), (.80, 16.68), (.52, 16.95), (.34, 17.25), (.22, 17.50), (.16, 17.62)], 48, flutes=16, flute_depth=0.16)
    lathe(m, [(.16, 17.62), (.24, 17.66), (.24, 17.70), (.12, 17.74), (.10, 17.80)], 24)
    sphere(m, (0, 17.98, 0), .20, 16, sy=1.05)
    lathe(m, [(.07, 18.16), (.13, 18.20), (.07, 18.26), (.055, 18.40), (.085, 18.52), (.05, 18.66), (.03, 19.00), (.004, 19.45)], 16)
    add("Finial_Crown_and_Lance", "Finial", m, "gold")

    # ---------------- arms ---------------------------------------------------
    def arm_height(k, r):
        """height of the arm centre line at radius r for reach factor k"""
        re = R_ELBOW * k; rt = HALF * k
        if r <= re:
            return H_ARM_PIVOT + (elbow_h - H_ARM_PIVOT) * (r - .45) / (re - .45)
        return elbow_h + (tip_h - elbow_h) * (r - re) / (rt - re)

    def arm_assembly(k, direction):
        dx, dz = direction
        P = lambda r, y, off=0.0: (dx * r - dz * off, y, dz * r + dx * off)
        st, cl, hg = Mesh(), Mesh(), Mesh()
        re, rt = R_ELBOW * k, HALF * k
        side = (-dz, 0, dx)
        beam(st, P(.45, H_ARM_PIVOT), P(re, elbow_h), .34, .44, .30, .36)                  # inner arm section
        beam(st, P(re, elbow_h), P(rt - .15, tip_h + .02), .28, .34, .14, .16)             # outer arm section
        ru = 2.83 * k
        beam(st, P(.34, H_UPPER_PIVOT), P(ru, arm_height(k, ru) + .22), .20, .22)          # upper strut
        rl = 6.30 * k; pl0 = np.array(P(.46, H_LOWER_PIVOT)); pl1 = np.array(P(rl, arm_height(k, rl) - .20))
        mid = pl0 + (pl1 - pl0) * .55
        beam(st, pl0, mid, .30, .32)                                                       # lower strut (telescopic)
        beam(st, mid, pl1, .22, .24)
        beam(st, mid - (pl1 - pl0) * .01, mid + (pl1 - pl0) * .012, .36, .38)
        for (r, y, rad, ln) in ((.45, H_ARM_PIVOT, .16, .62), (re, elbow_h, .20, .56), (ru, arm_height(k, ru) + .22, .10, .40),
                                (rl, arm_height(k, rl) - .20, .12, .44), (.34, H_UPPER_PIVOT, .11, .44), (.46, H_LOWER_PIVOT, .13, .52)):
            c = np.array(P(r, y)); s = np.array(side)
            cyl(hg, c - s * ln / 2, c + s * ln / 2, rad, n=14)                              # hinge pins (6 per arm [D])
        for sg in (-1, 1):                                                                 # elbow cheek plates
            c = np.array(P(re, elbow_h)) + np.array(side) * sg * .19
            beam(st, c - np.array(P(.55, 0)) + 0, c + np.array(P(.55, 0)), .03, .50)
        # cladding flaps with glass mosaic (form the prismatic casing when folded)
        for (ra, rb, wa, wb) in ((1.4 * k, re - .45, .46, .62), (re + .45, rt - .9, .62, .30)):
            a = np.array(P(ra, arm_height(k, ra) + .30)); b = np.array(P(rb, arm_height(k, rb) + .27 if rb < re else arm_height(k, rb) + .22))
            beam(cl, a, b, wa, .05, wb, .05, uvlen=wa)
            for t in (.15, .5, .85):
                c = a + (b - a) * t
                beam(st, c - (0, .24, 0), c, .06, .06, up=(dx, 0, dz))
        tipm = Mesh()                                                                      # gilded tip shoe
        cyl(tipm, P(rt - .22, tip_h + .02), P(rt + .10, tip_h - .02), .09, .035, n=10)
        sphere(tipm, P(rt + .12, tip_h - .02), .055, 8)
        # suspension ties from arm to membrane
        q = {(1, 0): 3.0, (SQ2 / 2, SQ2 / 2): 6.0}[(round(dx, 6) if abs(dx - 1) < 1e-6 else SQ2 / 2, round(dz, 6) if abs(dz) < 1e-6 else SQ2 / 2)]
        for sig in (.42, .62, .82):
            mx, my, mz = membrane_point(q, sig, tip_h)
            r = math.hypot(mx, mz)
            cyl(st, (mx, my, mz), P(r, arm_height(k, r) - .15), .018, n=6, caps=False)
        return st, cl, hg, tipm

    st, cl, hg, tp = arm_assembly(1.0, (1, 0))
    add("Middle_Arm_Steel", "Arms", st, "steel", R4); add("Middle_Arm_Mosaic_Cladding", "Arms", cl, "mosaic", R4)
    add("Middle_Arm_Hinges", "Arms", hg, "gold_dark", R4); add("Middle_Arm_Tip", "Arms", tp, "gold", R4)
    st, cl, hg, tp = arm_assembly(SQ2, (SQ2 / 2, SQ2 / 2))
    # 4 passive arms hinged off each diagonal arm (16 in total [D])
    for (rh, tips) in ((11.0, ((HALF, TIP_STEP), (TIP_STEP, HALF))), (14.5, ((HALF, 2 * TIP_STEP), (2 * TIP_STEP, HALF)))):
        hpt = np.array((rh * SQ2 / 2, arm_height(SQ2, rh) - .05, rh * SQ2 / 2))
        for (tx, tz) in tips:
            tpt = np.array((tx, tip_h - .06, tz))
            cyl(st, hpt, tpt, .075, .04, n=10)
            sphere(tp, tuple(tpt), .05, 8)
        sphere(hg, tuple(hpt), .13, 10)
    add("Diagonal_Arm_Steel_and_Passive_Arms", "Arms", st, "steel", R4); add("Diagonal_Arm_Mosaic_Cladding", "Arms", cl, "mosaic", R4)
    add("Diagonal_Arm_Hinges", "Arms", hg, "gold_dark", R4); add("Diagonal_Arm_Tips", "Arms", tp, "gold", R4)

    # ---------------- membrane ----------------------------------------------
    add("PTFE_Membrane_25.5m", "Membrane", build_membrane(tip_h), "membrane")
    m = Mesh(); torus(m, (0, H_FUNNEL + .02, 0), R_FUNNEL + .02, .045, n=32, k=8)
    add("Membrane_Collar_Ring", "Membrane", m, "gold")

    # ---------------- evaporative cooling fans ------------------------------
    f, fd = Mesh(), Mesh()
    cx = 0.55 + 0.12 + 0.56; R = 0.56; dep = 0.50
    prof = [(R - .05, -dep / 2), (R, -dep / 2 + .04), (R, dep / 2 - .06), (R + .04, dep / 2), (R - .03, dep / 2 + .02), (R - .07, dep / 2 - .04), (R - .07, -dep / 2)]
    sub = Mesh(); lathe(sub, prof, 32)
    for p, n in zip(sub.P, sub.N):                        # rotate lathe axis Y -> Z, move to fan centre
        f.P.append((p[0] + cx, p[2] + H_FAN, p[1])); f.N.append((n[0], n[2], n[1]))
    f.UV += sub.UV; f.I += [i for t in zip(sub.I[0::3], sub.I[2::3], sub.I[1::3]) for i in t]
    cyl(fd, (cx, H_FAN, -.16), (cx, H_FAN, .14), .15, .11, n=14)                           # hub / motor
    for b in range(7):                                    # swept blades
        a0 = 2 * math.pi * b / 7
        pts = []
        for (rr, da, zz) in ((.14, 0, -.06), (.48, .55, -.10), (.48, .95, .06), (.14, .35, .08)):
            pts.append((cx + rr * math.cos(a0 + da), H_FAN + rr * math.sin(a0 + da), zz))
        f.quad(*pts); f.quad(*pts[::-1])
    for rr in (.30, .44):                                 # guard rings + mist ring
        torus(fd, (cx, H_FAN, dep / 2 - .02), rr, .012, axis="z", n=28, k=6)
    torus(fd, (cx, H_FAN, dep / 2 + .03), R - .02, .018, axis="z", n=28, k=6)
    for i in range(16):                                   # 16 mist nozzles per fan [D]
        a = 2 * math.pi * i / 16
        c = (cx + (R - .02) * math.cos(a), H_FAN + (R - .02) * math.sin(a), dep / 2 + .03)
        cyl(fd, c, (c[0], c[1], c[2] + .05), .016, .008, n=6)
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        cyl(fd, (cx + .12 * math.cos(a), H_FAN + .12 * math.sin(a), dep / 2 - .02), (cx + .5 * math.cos(a), H_FAN + .5 * math.sin(a), dep / 2 - .02), .012, n=6, caps=False)
    beam(f, (0.50, H_FAN + R + .19, 0), (cx + .30, H_FAN + R + .19, 0), .50, .26)           # bracket housing
    beam(f, (cx, H_FAN + R - .02, 0), (cx, H_FAN + R + .08, 0), .20, .20, up=(1, 0, 0))
    add("Cooling_Fan_Housing", "Cooling", f, "fan", [0, 180]); add("Cooling_Fan_Guard_and_Mist_Ring", "Cooling", fd, "fan_dark", [0, 180])

    # ---------------- piazza floor ------------------------------------------
    m = Mesh(); S = 13.5
    m.quad((-S, 0, -S), (S, 0, -S), (S, 0, S), (-S, 0, S), uv=((0, 0), (9, 0), (9, 9), (0, 9)), hint=(0, 1, 0))
    add("Piazza_Floor_27m", "Site", m, "floor")
    return parts


# --------------------------------------------------------------------------
# GLB writer
# --------------------------------------------------------------------------
def quat_y(deg):
    a = math.radians(deg) / 2
    return [0.0, math.sin(a), 0.0, math.cos(a)]


def quat_from_to(a, b):
    a = np.asarray(a, float) / np.linalg.norm(a); b = np.asarray(b, float) / np.linalg.norm(b)
    c = np.cross(a, b); w = 1 + float(np.dot(a, b))
    if w < 1e-8:
        return [1.0, 0.0, 0.0, 0.0]
    q = np.array([c[0], c[1], c[2], w]); q /= np.linalg.norm(q)
    return [float(x) for x in q]


def write_glb(path, parts, textures, variant):
    bin_ = bytearray(); views = []; accs = []

    def view(data, target=None):
        while len(bin_) % 4:
            bin_.append(0)
        v = dict(buffer=0, byteOffset=len(bin_), byteLength=len(data))
        if target:
            v["target"] = target
        bin_.extend(data); views.append(v); return len(views) - 1

    def acc(arr, typ, ctype, target, minmax=False):
        a = dict(bufferView=view(arr.tobytes(), target), componentType=ctype, count=int(arr.shape[0]), type=typ)
        if minmax:
            a["min"] = [float(x) for x in arr.min(0)]; a["max"] = [float(x) for x in arr.max(0)]
        accs.append(a); return len(accs) - 1

    tex_names = list(textures)
    images = []
    for n in tex_names:
        b = io.BytesIO(); textures[n].save(b, "JPEG", quality=86, optimize=True)
        images.append(dict(bufferView=view(b.getvalue()), mimeType="image/jpeg", name=n))
    mat_names = list(MATERIALS); mats = []
    for n in mat_names:
        d = MATERIALS[n]
        pbr = dict(baseColorFactor=list(d.get("color", (1, 1, 1))) + [1.0], metallicFactor=d["metal"], roughnessFactor=d["rough"])
        if "tex" in d:
            pbr["baseColorTexture"] = dict(index=tex_names.index(d["tex"]))
        mt = dict(name=n, pbrMetallicRoughness=pbr, doubleSided=bool(d.get("double", False)))
        if "emissive" in d:
            mt["emissiveFactor"] = list(d["emissive"]); mt["emissiveTexture"] = dict(index=tex_names.index(d["tex"]))
            mt["extensions"] = {"KHR_materials_emissive_strength": {"emissiveStrength": d["estr"]}}
        mats.append(mt)

    nodes = [dict(name="Madinah_Piazza_Umbrella_U26_" + variant, children=[])]
    groups = {}; meshes = []; ntri = 0
    for p in parts:
        P, N, UV, I = p["mesh"].arrays()
        ntri += len(I) // 3 * (len(p["rot"]) if p["rot"] else 1)
        prim = dict(attributes=dict(POSITION=acc(P, "VEC3", 5126, 34962, True), NORMAL=acc(N, "VEC3", 5126, 34962),
                                    TEXCOORD_0=acc(UV, "VEC2", 5126, 34962)),
                    indices=acc(I, "SCALAR", 5125, 34963), material=mat_names.index(p["mat"]))
        meshes.append(dict(name=p["name"], primitives=[prim])); mi = len(meshes) - 1
        if p["group"] not in groups:
            nodes.append(dict(name=p["group"], children=[])); groups[p["group"]] = len(nodes) - 1
            nodes[0]["children"].append(groups[p["group"]])
        gi = groups[p["group"]]
        for r in (p["rot"] or [None]):
            nd = dict(name=p["name"] + ("" if r is None else "_%03d" % r), mesh=mi)
            if r:
                nd["rotation"] = quat_y(r)
            nodes.append(nd); nodes[gi]["children"].append(len(nodes) - 1)

    # lighting design: facade uplights wash the membrane, bay lanterns light the piazza
    lights = [dict(name="Membrane_Uplight", type="spot", color=[1.0, 0.90, 0.74], intensity=4000.0,
                   spot=dict(innerConeAngle=0.5, outerConeAngle=1.15), range=30.0),
              dict(name="Piazza_Downlight", type="spot", color=[1.0, 0.84, 0.60], intensity=6000.0,
                   spot=dict(innerConeAngle=0.6, outerConeAngle=1.2), range=40.0)]
    nodes.append(dict(name="Lighting", children=[])); li = len(nodes) - 1; nodes[0]["children"].append(li)
    for k in range(8):                                    # facade lighting: 8 uplights on the lantern crown
        a = math.radians(45 * k); r = 1.25 if k % 2 == 0 else 1.4
        d = (math.cos(a) * 0.95, 0.62, math.sin(a) * 0.95)
        nodes.append(dict(name="Membrane_Uplight_%d" % k, translation=[r * math.cos(a), H_LANT1 + .25, r * math.sin(a)],
                          rotation=quat_from_to((0, 0, -1), d), extensions={"KHR_lights_punctual": {"light": 0}}))
        nodes[li]["children"].append(len(nodes) - 1)
    for k in range(4):                                    # piazza lighting: one downlight per bay lantern
        a = math.radians(90 * k)
        d = (math.cos(a) * 0.75, -0.66, math.sin(a) * 0.75)
        nodes.append(dict(name="Piazza_Downlight_%d" % k, translation=[1.30 * math.cos(a), H_LANT0 + .05, 1.30 * math.sin(a)],
                          rotation=quat_from_to((0, 0, -1), d), extensions={"KHR_lights_punctual": {"light": 1}}))
        nodes[li]["children"].append(len(nodes) - 1)

    while len(bin_) % 4:
        bin_.append(0)
    gltf = dict(asset=dict(version="2.0", generator="build_umbrella.py (parametric, metres, Y-up)"),
                extensionsUsed=["KHR_lights_punctual", "KHR_materials_emissive_strength"],
                extensions={"KHR_lights_punctual": {"lights": lights}},
                scene=0, scenes=[dict(name="Scene", nodes=[0])], nodes=nodes, meshes=meshes, materials=mats,
                textures=[dict(source=i, sampler=0) for i in range(len(images))], images=images,
                samplers=[dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)],
                accessors=accs, bufferViews=views, buffers=[dict(byteLength=len(bin_))])
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(bin_), b"BIN\0")); f.write(bin_)
    return ntri, os.path.getsize(path)


def main():
    textures = dict(membrane=tex_membrane(), stone=tex_stone(), carved=tex_carved(), frieze=tex_frieze(),
                    mosaic=tex_mosaic(), floor=tex_floor(), glass=tex_glass())
    os.makedirs(os.path.join(HERE, "textures"), exist_ok=True)
    for n, im in textures.items():
        im.save(os.path.join(HERE, "textures", n + ".jpg"), quality=86, optimize=True)
    out = {}
    for v in VARIANTS:
        path = os.path.join(HERE, "madinah_umbrella_%s.glb" % v)
        ntri, size = write_glb(path, build_parts(v), textures, v)
        out[v] = path
        print("%s: %d triangles, %.2f MB" % (os.path.basename(path), ntri, size / 1e6))
    tpl = os.path.join(HERE, "viewer.template.html")
    if os.path.exists(tpl):
        html = open(tpl, encoding="utf-8").read()
        for v in VARIANTS:
            html = html.replace("__GLB_%s__" % v.upper(), base64.b64encode(open(out[v], "rb").read()).decode())
        open(os.path.join(HERE, "viewer.html"), "w", encoding="utf-8").write(html)
        print("viewer.html: %.2f MB" % (os.path.getsize(os.path.join(HERE, "viewer.html")) / 1e6))


if __name__ == "__main__":
    main()
