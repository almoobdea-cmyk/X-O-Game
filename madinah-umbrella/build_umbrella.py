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
R_FUNNEL, H_FUNNEL = 0.52, 10.00     # [P] membrane pleats leave the faceted crown
H_ARM_PIVOT = 14.15                  # [M] arm root hinge on the mast
H_UPPER_PIVOT = 16.20                # [M] upper strut hinge
H_LOWER_PIVOT = 10.86                # [M] lower strut hinge
R_ELBOW = 6.60                       # [M] inner/outer arm hinge radius (middle arm)
H_FAN = 3.96                         # [M] evaporative cooling fan axis
H_SHAFT0, H_SHAFT1 = 1.27, 5.50      # [M/P]
H_FRIEZE0, H_FRIEZE1 = 6.78, 7.48    # [P] slate frieze band
H_LANT0, H_LANT1 = 7.78, 9.30        # [M/P] lamp frames (piazza + facade lighting)
A_SHAFT = 0.45                       # [M/P] shaft apothem: 0.90 m across flats
H_CAP0, H_CAP1 = 5.69, 6.67          # [P] carved capital
H_BODY0 = 7.635                      # [P] underside of the lantern block


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
# Relief carving helpers: everything is modelled as real geometry on a face frame
# --------------------------------------------------------------------------
def _unit(v):
    v = np.asarray(v, float); return v / np.linalg.norm(v)


class Frame:
    """Local 2D frame on a planar face: p(a, b, h) = origin + a*U + b*V + h*N (N points outward)."""
    def __init__(self, o, u, v):
        self.o = np.asarray(o, float); self.u = _unit(u); self.v = _unit(v)
        n = _unit(np.cross(self.u, self.v))
        if np.dot(n, (self.o[0], 0, self.o[2])) < 0:
            n = -n
        self.n = n

    def p(self, a, b, h=0.0):
        return self.o + self.u * a + self.v * b + self.n * h


def tri_h(m, a, b, c, hint):
    if np.dot(np.cross(np.subtract(b, a), np.subtract(c, a)), hint) < 0:
        b, c = c, b
    m.tri(a, b, c)


def curve(pts, sub=6, closed=False):
    """Catmull-Rom smoothing of a 2D polyline."""
    P = [np.asarray(p, float) for p in pts]; n = len(P); out = []
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = P[(i - 1) % n] if (closed or i > 0) else P[0]
        p1 = P[i]; p2 = P[(i + 1) % n]
        p3 = P[(i + 2) % n] if (closed or i + 2 < n) else P[-1]
        for k in range(sub):
            t = k / sub
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    if not closed:
        out.append(P[-1])
    return out


def ribbon(m, F, pts, hw, h, closed=False, top=0.42):
    """Raised moulding along a 2D path: flat crest of half-width hw*top, chamfered flanks."""
    P = [np.asarray(p, float) for p in pts]; n = len(P)
    if n < 2:
        return
    nr = []
    for i in range(n):
        a = P[(i - 1) % n] if (closed or i > 0) else P[i]
        b = P[(i + 1) % n] if (closed or i < n - 1) else P[i]
        t = b - a; L = np.linalg.norm(t)
        t = t / L if L > 1e-9 else np.array([1.0, 0.0])
        nr.append(np.array([-t[1], t[0]]))
    segs = range(n) if closed else range(n - 1)
    for i in segs:
        j = (i + 1) % n
        row = []
        for k in (i, j):
            p, q = P[k], nr[k]
            row.append([F.p(*(p + q * hw)), F.p(*(p + q * hw * top), h), F.p(*(p - q * hw * top), h), F.p(*(p - q * hw))])
        A, B = row
        for c in range(3):
            m.quad(A[c], A[c + 1], B[c + 1], B[c], hint=F.n)


def pyramid(m, F, base, h):
    c = np.mean(np.asarray(base, float), 0); apex = F.p(c[0], c[1], h)
    for i in range(len(base)):
        a = base[i]; b = base[(i + 1) % len(base)]
        tri_h(m, F.p(*a), F.p(*b), apex, F.n)


def plate(m, F, poly, h, inset=0.012):
    """Raised polygon (star-shaped about its centroid) with chamfered rim."""
    poly = [np.asarray(p, float) for p in poly]; c = np.mean(poly, 0)
    top = []
    for p in poly:
        d = c - p; L = np.linalg.norm(d)
        top.append(p + d / L * min(inset, L * 0.4))
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        m.quad(F.p(*poly[i]), F.p(*poly[j]), F.p(*top[j], h), F.p(*top[i], h), hint=F.n)
        tri_h(m, F.p(*c, h), F.p(*top[i], h), F.p(*top[j], h), F.n)


def dome(m, F, c, ru, rv, h, n=16, k=5):
    V, T = [], []
    for j in range(k + 1):
        ph = j / k * math.pi / 2
        for i in range(n):
            th = 2 * math.pi * i / n
            V.append(F.p(c[0] + ru * math.cos(ph) * math.cos(th), c[1] + rv * math.cos(ph) * math.sin(th), h * math.sin(ph)))
    for j in range(k):
        for i in range(n):
            a = j * n + i; b = j * n + (i + 1) % n; c2 = a + n; d = b + n
            T += [(a, b, d), (a, d, c2)]
    m.smooth(V, T, up_hint=F.n)


def in_poly(p, poly):
    x, y = p; inside = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def spiral(c, r0, r1, a0, turns, sgn=1, n=28):
    out = []
    for k in range(n + 1):
        t = k / n; r = r0 + (r1 - r0) * t; a = a0 + sgn * turns * 2 * math.pi * t
        out.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return out


def rot4(p, k):
    """Rotate a point (x, y, z) about the Y axis by k quarter turns."""
    x, y, z = p
    for _ in range(k % 4):
        x, z = -z, x
    return (x, y, z)


def sta(y, a, w):
    """Loft station for a chamfered square given main-face apothem a and main-face half-width w."""
    return (y, a, (a + w) / SQ2)


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
    fade = max(0.0, 1 - sig / 0.10) ** 2          # gathered pleats where the fabric leaves the crown
    r *= 1 + 0.085 * fade * math.cos(4 * math.pi * q)
    return r * math.cos(th), y, r * math.sin(th)


def build_membrane(tip_h):
    m = Mesh()
    NQ, NS = 24 * 12, 44
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
        r0 = R_FUNNEL if i % 4 == 0 else 1.3 if i % 2 == 0 else 2.4     # keep the gathered collar mostly white
        pts = [pol(q, r0 + (r1 - r0) * k / 60) for k in range(61)]
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
    base = np.array([196, 176, 160], np.float32)
    a = np.ones((size, size, 3), np.float32) * base
    a += _noise(size, 5, 26)[..., None]
    a += rng.normal(0, 7, (size, size, 1))
    spk = rng.random((size, size)) > 0.985
    a[spk] *= 0.78
    a[:5, :, :] *= 0.72; a[5:8, :, :] *= 1.06            # joint + highlight
    for x in (0, size // 2):
        a[:, x:x + 3, :] *= 0.86                          # vertical joints
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def tex_gold_engraved(size=256):
    """Gilded sheet with chased arabesque scrollwork (lamp header, side panels, frames)."""
    a = np.ones((size, size, 3), np.float32) * np.array([246, 168, 40], np.float32)
    a += _noise(size, 31, 14)[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im)
    dark, lite = (176, 118, 30), (255, 222, 130)
    n = 4; c = size / n
    for j in range(n):
        for i in range(n):
            cx, cy = (i + .5) * c, (j + .5) * c; sg = 1 if (i + j) % 2 == 0 else -1
            pts = []
            for k in range(70):
                t = k / 69 * 2.6 * math.pi; r = c * 0.06 + c * 0.38 * (1 - k / 69)
                pts.append((cx + r * math.cos(t) * sg, cy + r * math.sin(t)))
            d.line(pts, fill=dark, width=4); d.line([(x + 1.5, y - 1.5) for x, y in pts], fill=lite, width=1)
            d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=dark)
            for q in range(4):                       # leaves in the gaps
                t = q * math.pi / 2 + math.pi / 4
                x, y = cx + c * 0.47 * math.cos(t), cy + c * 0.47 * math.sin(t)
                d.polygon([(x - 7, y), (x, y - 7), (x + 7, y), (x, y + 7)], fill=dark)
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
    """Lamp glass: bluish prismatic panes over a horizontally ribbed reflector."""
    a = np.ones((size, size, 3), np.float32) * np.array([196, 210, 220], np.float32)
    y = np.arange(size)[:, None] / size
    rib = (y * 14) % 1.0
    a *= (0.88 + 0.14 * rib)[..., None]
    a *= (1.04 - 0.12 * y)[..., None]
    x = np.arange(size)[None, :] / size
    a *= (0.94 + 0.06 * np.cos(x * math.pi * 2))[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
MATERIALS = {
    "membrane":  dict(tex="membrane", rough=0.85, metal=0.0, double=True),
    "stone":     dict(tex="stone", rough=0.55, metal=0.0),
    "base":      dict(color=(0.90, 0.80, 0.74), tex="stone", rough=0.22, metal=0.0),
    "caststone": dict(color=(0.69, 0.67, 0.63), rough=0.85, metal=0.0),
    "slate":     dict(color=(0.30, 0.38, 0.46), rough=0.55, metal=0.0),
    "gold_engraved": dict(tex="gold_engraved", rough=0.32, metal=1.0, double=True),
    "gold":      dict(color=(1.0, 0.62, 0.11), rough=0.24, metal=1.0),
    "gold_dark": dict(color=(0.72, 0.52, 0.20), rough=0.4, metal=1.0),
    "glass":     dict(color=(0.70, 0.83, 0.92), alpha=0.30, rough=0.05, metal=0.0, double=True),
    "reflector": dict(color=(0.86, 0.89, 0.93), rough=0.30, metal=0.7, emissive=(1.0, 0.86, 0.62), estr=1.0, double=True),
    "steel":     dict(color=(0.93, 0.92, 0.89), rough=0.45, metal=0.15),
    "mosaic":    dict(tex="mosaic", rough=0.3, metal=0.0),
    "fan":       dict(color=(0.90, 0.86, 0.78), rough=0.6, metal=0.0),
    "fan_dark":  dict(color=(0.35, 0.33, 0.30), rough=0.6, metal=0.3),
    "floor":     dict(tex="floor", rough=0.36, metal=0.0),
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
    AS = A_SHAFT
    # pedestal: square granite block, corners broached up to an octagonal top, with a
    # clipped-corner sunk panel on each face; then a low course, scotia and one big roll. [P]
    PS, PYB, PYT = .92, .44, .70
    PW = PS * (SQ2 - 1)
    m = Mesh()
    for k in range(4):
        q = lambda x, y, z: rot4((x, y, z), k)
        hx = np.array(rot4((1, 0, 0), k)); hd = np.array(rot4((1, 0, 1), k))
        m.quad(q(PS, 0, -PS), q(PS, 0, PS), q(PS, PYB, PS), q(PS, PYB, -PS),
               uv=((0, 0), (2, 0), (2, -PYB), (0, -PYB)), hint=hx)
        m.quad(q(PS, PYB, -PS), q(PS, PYB, PS), q(PS, PYT, PW), q(PS, PYT, -PW),
               uv=((0, -PYB), (2, -PYB), (1.4, -PYT), (.6, -PYT)), hint=hx)
        tri_h(m, q(PS, PYB, PS), q(PS, PYT, PW), q(PW, PYT, PS), hd + (0, 1, 0))                      # broach facet
        tri_h(m, q(0, PYT, 0), q(PS, PYT, -PW), q(PS, PYT, PW), (0, 1, 0))                            # top ledge
        tri_h(m, q(0, PYT, 0), q(PS, PYT, PW), q(PW, PYT, PS), (0, 1, 0))
    prof = [(PYT, .56), (PYT + .012, .565), (.82, .565), (.835, .55), (.85, .525), (.90, .505), (.925, .505)]
    for kk in range(11):                                  # the roll
        t = kk / 10 * math.pi
        prof.append((.925 + .235 * (1 - math.cos(t)) / 2, .505 + .078 * math.sin(t) ** .8))
    prof += [(1.165, .50), (1.175, .49), (1.255, .49), (H_SHAFT0, AS)]
    loft(m, [(y, a_, None) for (y, a_) in prof], vscale=1.2)
    add("Base_Pedestal_and_Roll", "Column", m, "base")
    m = Mesh()
    Fp = Frame((PS, 0, 0), (0, 0, 1), (0, 1, 0))
    pu, pv0, pv1, pc = .50, .085, .455, .075
    panel = [(-pu + pc, pv0), (pu - pc, pv0), (pu, pv0 + pc), (pu, pv1 - pc), (pu - pc, pv1), (-pu + pc, pv1), (-pu, pv1 - pc), (-pu, pv0 + pc)]
    ribbon(m, Fp, panel, .020, .020, closed=True, top=.5)
    inner = [(u * .93, pv0 + .02 + (v - pv0) * (pv1 - pv0 - .04) / (pv1 - pv0)) for u, v in panel]
    ribbon(m, Fp, inner, .008, .008, closed=True)
    add("Base_Pedestal_Panels", "Column", m, "base", R4)
    m = Mesh()                                            # shaft, regular octagon 0.90 m across flats
    loft(m, [(H_SHAFT0, AS, None), (H_SHAFT1, AS, None)], vscale=1 / 1.025)
    add("Shaft", "Column", m, "stone")
    m = Mesh()                                            # three roll mouldings under the capital [P]
    prof = [(H_SHAFT1, AS)]
    for (y0, y1, r) in ((5.505, 5.56, .045), (5.565, 5.615, .035), (5.62, 5.685, .05)):
        for k in range(7):
            t = k / 6 * math.pi
            prof.append((y0 + (y1 - y0) * (1 - math.cos(t)) / 2, AS + .005 + r * math.sin(t)))
    prof.append((H_CAP0, AS + .005))
    loft(m, [(y, a, None) for (y, a) in prof])
    add("Astragal_Rolls", "Column", m, "caststone")

    # capital: regular octagon at the shaft -> chamfered square under the frieze.
    # Main faces are trapezoids (0.37 -> 1.20 m), corner faces stay 0.37 m wide. [P]
    CA1, CW1 = .86, .60
    m = Mesh()
    loft(m, [(H_CAP0, AS + .005, None), sta(H_CAP1, CA1, CW1)])
    loft(m, [sta(H_CAP1, CA1, CW1), sta(H_CAP1, CA1 + .018, CW1 + .012), sta(H_CAP1 + .03, CA1 + .018, CW1 + .012),
             sta(H_CAP1 + .03, CA1 + .008, CW1 + .008), sta(H_FRIEZE0, CA1 + .008, CW1 + .008)])      # plain necking band
    add("Capital_Core", "Column", m, "caststone")

    a0 = AS + .005; w0 = a0 * (SQ2 - 1)
    Fm = Frame((a0, H_CAP0, 0), (0, 0, 1), (CA1 - a0, H_CAP1 - H_CAP0, 0))
    Lm = math.hypot(CA1 - a0, H_CAP1 - H_CAP0)
    hwf = lambda v: w0 + (CW1 - w0) * v / Lm
    m = Mesh()
    # shield medallion outline (right half, top -> bottom), mirrored
    half = [(0.0, .955), (.032, .925), (.030, .895), (.10, .915), (.20, .905), (.290, .880), (.335, .800),
            (.315, .700), (.275, .580), (.222, .460), (.150, .320), (.070, .190), (0.0, .112)]
    half = [(u * 0.92, v * Lm / 1.06) for u, v in half]
    outline = half + [(-u, v) for u, v in half[-2:0:-1]]
    shield = curve(outline, 5, closed=True)
    ribbon(m, Fm, shield, .024, .034, closed=True)
    cen = np.array((0.0, .60 * Lm / 1.06))
    inner = [tuple(cen + (np.asarray(p) - cen) * .80) for p in shield]
    ribbon(m, Fm, inner, .012, .020, closed=True)
    bc = (0.0, .70 * Lm / 1.06)                            # sphere boss with collar
    dome(m, Fm, bc, .088, .088, .075, n=20, k=6)
    ribbon(m, Fm, [(bc[0] + .118 * math.cos(t), bc[1] + .118 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 28, endpoint=False)], .011, .018, closed=True)
    ribbon(m, Fm, [(0, bc[1] - .118), (0, .30), (0, .185)], .011, .020)                      # stem
    pyramid(m, Fm, [(0, .36), (.028, .40), (0, .44), (-.028, .40)], .022)
    for sg in (-1, 1):                                    # scrollwork inside the shield
        ribbon(m, Fm, spiral((sg * .098, .475), .070, .014, math.pi / 2 if sg > 0 else math.pi / 2, 1.15, sgn=-sg), .010, .018)
        ribbon(m, Fm, spiral((sg * .058, .305), .046, .010, math.pi / 2, 1.05, sgn=-sg), .008, .015)
        ribbon(m, Fm, curve([(sg * .012, .56), (sg * .10, .60), (sg * .19, .66), (sg * .225, .75), (sg * .19, .81)], 5), .010, .018)
        ribbon(m, Fm, spiral((sg * .168, .805), .030, .008, 0 if sg > 0 else math.pi, .9, sgn=sg), .008, .015)
        ribbon(m, Fm, curve([(sg * .03, .875), (sg * .075, .86), (sg * .10, .835)], 4), .008, .015)
        ribbon(m, Fm, curve([(sg * .012, .245), (sg * .05, .262), (sg * .085, .30)], 4), .007, .013)
    ribbon(m, Fm, spiral((0, .905), .026, .026, 0, 1.0, n=14), .007, .014, closed=False)      # finial eye
    # quilted diamond lattice filling the rest of the face
    guard = [tuple(cen + (np.asarray(p) - cen) * 1.075) for p in shield]
    pch = .060
    for j in range(1, int(Lm / (pch / 2))):
        v = j * pch / 2
        for i in range(-12, 13):
            u = (i + (0.5 if j % 2 else 0.0)) * pch
            base = [(u, v - pch / 2 * .93), (u + pch / 2 * .93, v), (u, v + pch / 2 * .93), (u - pch / 2 * .93, v)]
            if v - pch / 2 < .03 or v + pch / 2 > Lm - .03:
                continue
            if any(abs(bu) > hwf(bv) - .018 for bu, bv in base) or any(in_poly(b, guard) for b in base) or in_poly((u, v), guard):
                continue
            pyramid(m, Fm, base, .013)
    ribbon(m, Fm, [(-hwf(.02) + .02, .02), (hwf(.02) - .02, .02)], .010, .014)
    ribbon(m, Fm, [(-CW1 + .02, Lm - .02), (CW1 - .02, Lm - .02)], .012, .016)
    add("Capital_Shield_and_Lattice", "Column", m, "caststone", R4)

    d0 = a0; d1 = (CA1 + CW1) / SQ2                         # corner face: arabesque panel + bud [P]
    Fc = Frame((d0 / SQ2, H_CAP0, d0 / SQ2), (-1, 0, 1), ((d1 - d0) / SQ2, H_CAP1 - H_CAP0, (d1 - d0) / SQ2))
    Lc = math.hypot(d1 - d0, H_CAP1 - H_CAP0)
    m = Mesh()
    pu, pv0, pv1 = .125, .06, .64
    ribbon(m, Fc, [(-pu, pv0), (pu, pv0), (pu, pv1), (-pu, pv1)], .014, .022, closed=True)
    ribbon(m, Fc, [(0, pv0 + .02), (0, pv1 - .02)], .008, .016)
    for vc in (.155, .30, .445, .575):
        hh = .068 if vc < .55 else .045
        for sg in (-1, 1):
            ribbon(m, Fc, curve([(0, vc - hh), (sg * .060, vc - hh * .45), (sg * .088, vc), (sg * .060, vc + hh * .45), (0, vc + hh)], 5), .008, .015)
            ribbon(m, Fc, spiral((sg * .052, vc), .026, .007, math.pi / 2, .95, sgn=-sg, n=16), .006, .012)
        pyramid(m, Fc, [(0, vc - .022), (.016, vc), (0, vc + .022), (-.016, vc)], .020)
    for vc in (.228, .372, .512):
        for sg in (-1, 1):
            pyramid(m, Fc, [(sg * .095, vc - .020), (sg * .112, vc), (sg * .095, vc + .020), (sg * .078, vc)], .014)
    bv = .84                                               # bud above the panel
    dome(m, Fc, (0, bv), .060, .115, .072, n=16, k=5)
    ribbon(m, Fc, [(-.07, bv - .125), (.07, bv - .125)], .012, .020)
    for sg in (-1, 1):
        ribbon(m, Fc, curve([(sg * .02, bv - .11), (sg * .105, bv - .05), (sg * .112, bv + .05), (sg * .05, bv + .15)], 5), .009, .016)
        ribbon(m, Fc, curve([(sg * .03, .70), (sg * .10, .685), (sg * .135, .715)], 4), .007, .013)
    pyramid(m, Fc, [(0, bv + .12), (.02, bv + .16), (0, bv + .215), (-.02, bv + .16)], .02)
    add("Capital_Corner_Arabesque", "Column", m, "caststone", R4)

    # frieze: slate panels with bevelled frame and three eight-pointed stars; light chamfer faces [P]
    FA, FW, REC = .84, .62, .032
    FH = H_FRIEZE1 - H_FRIEZE0
    m = Mesh(); loft(m, [sta(H_FRIEZE0, FA, FW), sta(H_FRIEZE1, FA, FW)], faces=(1, 3, 5, 7))
    Ff = Frame(((FA + FW) / 2, H_FRIEZE0, (FA + FW) / 2), (-1, 0, 1), (0, 1, 0))
    cwid = (FA - FW) * SQ2 / 2
    mc = Mesh()
    ribbon(mc, Ff, [(-cwid + .045, .08), (cwid - .045, .08), (cwid - .045, FH - .08), (-cwid + .045, FH - .08)], .012, .016, closed=True)
    plate(mc, Ff, [(0, .17), (.05, FH / 2), (0, FH - .17), (-.05, FH / 2)], .014, inset=.014)
    dome(mc, Ff, (0, FH / 2), .022, .022, .028, n=10, k=3)
    add("Frieze_Chamfer_Faces", "Column", m, "caststone"); add("Frieze_Chamfer_Panels", "Column", mc, "caststone", R4)
    m = Mesh()
    Fs = Frame((FA - REC, H_FRIEZE0, 0), (0, 0, 1), (0, 1, 0))
    b1, b2 = .105, .145                                    # frame width, bevel foot
    O = [(-FW, 0), (FW, 0), (FW, FH), (-FW, FH)]
    I1 = [(-FW + b1, b1), (FW - b1, b1), (FW - b1, FH - b1), (-FW + b1, FH - b1)]
    I2 = [(-FW + b2, b2), (FW - b2, b2), (FW - b2, FH - b2), (-FW + b2, FH - b2)]
    for i in range(4):
        j = (i + 1) % 4
        m.quad(Fs.p(*O[i], REC), Fs.p(*O[j], REC), Fs.p(*I1[j], REC), Fs.p(*I1[i], REC), hint=Fs.n)     # frame
        m.quad(Fs.p(*I1[i], REC), Fs.p(*I1[j], REC), Fs.p(*I2[j]), Fs.p(*I2[i]), hint=Fs.n)             # bevel
    m.quad(Fs.p(*I2[0]), Fs.p(*I2[1]), Fs.p(*I2[2]), Fs.p(*I2[3]), hint=Fs.n)                           # sunk panel
    for uc in (-.305, 0.0, .305):                          # eight-pointed stars in low relief
        star = []
        for k in range(16):
            t = math.pi / 2 + k * math.pi / 8; r = .135 if k % 2 == 0 else .135 * .765
            star.append((uc + r * math.cos(t), FH / 2 + r * math.sin(t)))
        plate(m, Fs, star, .013, inset=.016)
        ros = []
        for k in range(32):
            t = k * math.pi / 16; r = .062 + .014 * math.cos(8 * t)
            ros.append((uc + r * math.cos(t), FH / 2 + r * math.sin(t)))
        Fr = Frame(Fs.p(0, 0, .013), (0, 0, 1), (0, 1, 0))
        ribbon(m, Fr, ros, .008, .009, closed=True)
        dome(m, Fr, (uc, FH / 2), .026, .026, .016, n=12, k=3)
    add("Frieze_Slate_Star_Panel", "Column", m, "slate", R4)

    # dog-tooth cornice between frieze and lantern block [P]
    BA, BW = .90, .66
    CY0, CY1 = H_FRIEZE1 + .02, H_BODY0 - .015
    m = Mesh()
    loft(m, [sta(H_FRIEZE1, FA, FW), sta(CY0, FA + .012, FW + .008), sta(CY1, BA + .035, BW + .02),
             sta(H_BODY0, BA + .035, BW + .02), sta(H_BODY0, BA, BW)])
    add("Cornice_Core", "Column", m, "caststone")
    m = Mesh()
    Fd = Frame((FA + .012, CY0, 0), (0, 0, 1), (BA + .035 - FA - .012, CY1 - CY0, 0))
    Ld = math.hypot(BA + .035 - FA - .012, CY1 - CY0); nt = 9
    for i in range(nt):
        ua = -FW + (2 * FW) * i / nt; ub = ua + 2 * FW / nt
        pyramid(m, Fd, [(ua + .006, .004), (ub - .006, .004), (ub - .006, Ld - .004), (ua + .006, Ld - .004)], .036)
    add("Cornice_Dogtooth_Main", "Column", m, "caststone", R4)
    m = Mesh()
    e0 = (FA + .012 + FW + .008) / 2; e1 = (BA + .035 + BW + .02) / 2
    Fe = Frame((e0, CY0, e0), (-1, 0, 1), (e1 - e0, CY1 - CY0, e1 - e0))
    Le = math.hypot((e1 - e0) * SQ2, CY1 - CY0); ch = (FA - FW) * SQ2 / 2
    for i in range(3):
        ua = -ch + 2 * ch * i / 3; ub = ua + 2 * ch / 3
        pyramid(m, Fe, [(ua + .005, .004), (ub - .005, .004), (ub - .005, Le - .004), (ua + .005, Le - .004)], .032)
    add("Cornice_Dogtooth_Corner", "Column", m, "caststone", R4)

    # ---------------- lantern block ------------------------------------------
    # granite block, chamfered square below; the corners are cut back to re-entrant
    # notches beside the lamps, each ending in a pointed stop. [P]
    YB, YS0, YS1, YT = H_BODY0, 8.50, 8.63, H_LANT1
    NN = .715
    m = Mesh()
    for k in range(4):
        q = lambda x, y, z: rot4((x, y, z), k)
        hx = np.array(rot4((1, 0, 0), k)); hd = np.array(rot4((1, 0, 1), k)); hz = np.array(rot4((0, 0, 1), k))
        m.quad(q(BA, YB, -BW), q(BA, YB, BW), q(BA, YT, BW), q(BA, YT, -BW),
               uv=((0, -YB), (1.3, -YB), (1.3, -YT), (0, -YT)), hint=hx)                              # main face
        m.quad(q(BA, YB, BW), q(BW, YB, BA), q(BW, YS0, BA), q(BA, YS0, BW),
               uv=((0, -YB), (.35, -YB), (.35, -YS0), (0, -YS0)), hint=hd)                            # lower chamfer
        tri_h(m, q(BA, YS0, BW), q(BW, YS0, BA), q(NN, YS1, NN), hd + (0, .6, 0))                     # pointed stop
        tri_h(m, q(BA, YS0, BW), q(NN, YS1, NN), q(BA, YS1, BW), hz)
        tri_h(m, q(BW, YS0, BA), q(NN, YS1, NN), q(BW, YS1, BA), hx)
        m.quad(q(BA, YS1, BW), q(NN, YS1, NN), q(NN, YT, NN), q(BA, YT, BW), hint=hz)                 # notch returns
        m.quad(q(BW, YS1, BA), q(NN, YS1, NN), q(NN, YT, NN), q(BW, YT, BA), hint=hx)
    add("Lantern_Block_Granite", "Lantern", m, "stone")

    # gilded roof deck, faceted crown and collar [P]
    m = Mesh()
    loft(m, [sta(YT, BA + .02, BW + .02), sta(YT + .03, BA + .02, BW + .02), (9.66, .50, None)])
    ang = lambda i, off: math.radians(45 * i + off)
    RB, RT, y0c, y1c = .585, .585, 9.66, 9.92
    bot = [(RB * math.cos(ang(i, 22.5)), y0c, RB * math.sin(ang(i, 22.5))) for i in range(8)]
    topr = [(RT * math.cos(ang(i, 0)), y1c, RT * math.sin(ang(i, 0))) for i in range(8)]
    for i in range(8):                                    # antiprism band = alternating triangular facets
        hint = (math.cos(ang(i, 0)), 0, math.sin(ang(i, 0)))
        tri_h(m, bot[i - 1], bot[i], topr[i], hint)
        hint2 = (math.cos(ang(i, 22.5)), 0, math.sin(ang(i, 22.5)))
        tri_h(m, bot[i], topr[(i + 1) % 8], topr[i], hint2)
    for i in range(8):                                    # lower lip of the crown
        j = (i + 1) % 8
        m.quad(bot[i], bot[j], (bot[j][0] * .9, y0c - .04, bot[j][2] * .9), (bot[i][0] * .9, y0c - .04, bot[i][2] * .9),
               hint=(bot[i][0] + bot[j][0], -.5, bot[i][2] + bot[j][2]))
        m.quad(topr[i], topr[j], (topr[j][0] * .93, y1c + .05, topr[j][2] * .93), (topr[i][0] * .93, y1c + .05, topr[i][2] * .93),
               hint=(topr[i][0] + topr[j][0], .5, topr[i][2] + topr[j][2]))
    add("Lantern_Roof_Deck_and_Faceted_Crown", "Lantern", m, "gold")

    # one lamp on the +X face (instanced x4), after the close-up photos [P] -----------
    XB = BA; D = .36; HW = .38
    yBot = YT - 1.505                                      # underside of the bottom band
    yH = YT - .20                                          # underside of the engraved header
    yG1, yGb, yG0 = yH - .03, 8.185, 8.06                  # glass: top / start of bottom bevel / bottom
    ZP = HW - .03                                          # plane of the engraved side panels
    g, ge, gl, rf = Mesh(), Mesh(), Mesh(), Mesh()
    # polished back frame: two stiles and the bottom band
    for sg in (-1, 1):
        beam(g, (XB + .0275, yBot, sg * (HW - .025)), (XB + .0275, YT, sg * (HW - .025)), .05, .055, up=(1, 0, 0))
    beam(g, (XB + .04, yBot, 0), (XB + .04, yBot + .075, 0), 2 * HW, .08, up=(1, 0, 0))
    # base under the glass: stud band, scotia, bottom band
    beam(g, (XB + .065, yBot + .075, 0), (XB + .11, yBot + .175, 0), .60, .13, .67, .22, up=(1, 0, 0))
    beam(g, (XB + .11, yBot + .175, 0), (XB + .11, yG0, 0), .67, .22, up=(1, 0, 0))
    beam(g, (XB + .115, yG0 - .012, 0), (XB + .115, yG0, 0), .69, .235, up=(1, 0, 0))
    for zz in (-.16, 0, .16):
        sphere(g, (XB + .222, (yBot + .175 + yG0) / 2, zz), .017, 8)
    # engraved header box with plain borders
    hx0, hx1 = XB, XB + D
    ge.quad((hx1, yH + .03, -HW + .03), (hx1, yH + .03, HW - .03), (hx1, YT - .035, HW - .03), (hx1, YT - .035, -HW + .03),
            uv=((0, 1), (3, 1), (3, .35), (0, .35)), hint=(1, 0, 0))
    g.quad((hx1 - .004, yH, -HW), (hx1 - .004, yH, HW), (hx1 - .004, YT, HW), (hx1 - .004, YT, -HW), hint=(1, 0, 0))
    for sg in (-1, 1):
        g.quad((hx0, yH, sg * HW), (hx1, yH, sg * HW), (hx1, YT, sg * HW), (hx0, YT, sg * HW), hint=(0, 0, sg))
        ge.quad((hx0 + .05, yH + .03, sg * (HW + .003)), (hx1 - .03, yH + .03, sg * (HW + .003)), (hx1 - .03, YT - .035, sg * (HW + .003)),
                (hx0 + .05, YT - .035, sg * (HW + .003)), uv=((0, 1), (1.3, 1), (1.3, .35), (0, .35)), hint=(0, 0, sg))
    g.quad((hx0, yH, -HW), (hx1, yH, -HW), (hx1, yH, HW), (hx0, yH, HW), hint=(0, -1, 0))
    beam(g, (hx1 + .008, yH + .013, -HW - .008), (hx1 + .008, yH + .013, HW + .008), .026, .026)          # bead under the header
    for sg in (-1, 1):
        beam(g, (hx0, yH + .013, sg * (HW + .008)), (hx1 + .02, yH + .013, sg * (HW + .008)), .026, .026)
    # stepped cornice between header and eave
    for (dy, ex) in ((.035, .02), (.0, .045)):
        beam(g, (XB + (D + ex) / 2, YT - dy - .035, 0), (XB + (D + ex) / 2, YT - dy, 0), 2 * (HW + ex), D + ex, up=(1, 0, 0))
    # arched side panels: full depth under the header, a quick quarter-arch back to a strip at the wall
    strip, yspr, ybot = .075, yH - .27, yBot + .075

    def side_x(y):
        if y <= yspr:
            return strip
        t = math.asin(min((y - yspr) / (yH - yspr), 1.0))
        return strip + (D - .01 - strip) * (1 - math.cos(t)) ** .85
    ys = [ybot, yspr] + [yspr + (yH - yspr) * math.sin(k / 16 * math.pi / 2) for k in range(1, 17)]
    for sg in (-1, 1):
        for k in range(len(ys) - 1):
            ya, yb2 = ys[k], ys[k + 1]
            for zz, hh in ((sg * ZP, sg), (sg * (ZP - .015), -sg)):
                ge.quad((XB, ya, zz), (XB + side_x(ya), ya, zz), (XB + side_x(yb2), yb2, zz), (XB, yb2, zz),
                        uv=((0, ya * 4), (side_x(ya) * 4, ya * 4), (side_x(yb2) * 4, yb2 * 4), (0, yb2 * 4)), hint=(0, 0, hh))
            cyl(g, (XB + side_x(ya), ya, sg * (ZP - .0075)), (XB + side_x(yb2), yb2, sg * (ZP - .0075)), .017, n=8, caps=False)   # polished arch bead
            sphere(g, (XB + side_x(yb2), yb2, sg * (ZP - .0075)), .017, 6)
    # clear glass: nearly upright panes, bevelled back at the bottom
    gx = lambda y: XB + (.275 + (.335 - .275) * (y - yGb) / (yG1 - yGb))
    gz = lambda y: .285 + (.315 - .285) * (y - yGb) / (yG1 - yGb)
    F0 = [(gx(yGb), yGb, -gz(yGb)), (gx(yGb), yGb, gz(yGb))]; F1 = [(gx(yG1), yG1, -gz(yG1)), (gx(yG1), yG1, gz(yG1))]
    gl.quad(F0[0], F0[1], F1[1], F1[0], hint=(1, 0, 0))
    for sg, i in ((-1, 0), (1, 1)):
        gl.quad((XB + .01, yGb, sg * gz(yGb)), F0[i], F1[i], (XB + .01, yG1, sg * gz(yG1)), hint=(0, 0, sg))
    bx, bz = XB + .20, .255
    B0 = [(bx, yG0, -bz), (bx, yG0, bz)]
    gl.quad(B0[0], B0[1], F0[1], F0[0], hint=(1, -1, 0))
    for sg, i in ((-1, 0), (1, 1)):
        gl.quad((XB + .01, yG0, sg * bz), B0[i], F0[i], (XB + .01, yGb, sg * gz(yGb)), hint=(0, -.3, sg))
    for (p, q2) in ((F0[0], F1[0]), (F0[1], F1[1]), (F0[0], F0[1]), (F1[0], F1[1]), (B0[0], F0[0]), (B0[1], F0[1])):
        cyl(g, p, q2, .008, n=6, caps=False)                                                 # slim gilt glazing bars
    # ribbed reflector seen through the glass (this is what glows at night)
    rz = lambda y: gz(max(y, yGb)) - .035
    rf.quad((XB + .03, yG0 + .02, -bz + .03), (XB + .03, yG0 + .02, bz - .03), (XB + .03, yG1 - .01, rz(yG1)), (XB + .03, yG1 - .01, -rz(yG1)), hint=(1, 0, 0))
    nsl = 13
    for k in range(nsl):
        y = yG0 + .07 + (yG1 - .05 - yG0 - .07) * k / (nsl - 1)
        dep = (gx(max(y, yGb)) - XB - .06) * (.42 if y > yGb else .30)
        rf.quad((XB + .035, y + .028, -rz(y)), (XB + .035, y + .028, rz(y)), (XB + .035 + dep, y - .022, rz(y)), (XB + .035 + dep, y - .022, -rz(y)), hint=(.4, 1, 0))
    # hipped roof: deep eave fascia, then slopes running back to the crown
    ex0, ex1, ez, ye = XB - .03, XB + D + .085, HW + .09, YT
    beam(g, ((ex0 + ex1) / 2, ye, 0), ((ex0 + ex1) / 2, ye + .075, 0), 2 * ez, ex1 - ex0, up=(1, 0, 0))
    beam(g, ((ex0 + ex1) / 2 - .006, ye + .075, 0), ((ex0 + ex1) / 2 - .006, ye + .095, 0), 2 * ez - .02, ex1 - ex0 - .012, 2 * ez - .05, ex1 - ex0 - .03, up=(1, 0, 0))
    yr = ye + .095; rz2 = ez - .025; rx = ex1 - .024
    apex = (.50, 9.72, 0); P0 = (ex0, yr, -rz2); P1 = (rx, yr, -rz2); P2 = (rx, yr, rz2); P3 = (ex0, yr, rz2)
    tri_h(g, P1, P2, apex, (1, 1, 0)); tri_h(g, P0, P1, apex, (0, 1, -1)); tri_h(g, P2, P3, apex, (0, 1, 1))
    add("Lamp_Polished_Gilt", "Lantern", g, "gold", R4)
    add("Lamp_Engraved_Gilt", "Lantern", ge, "gold_engraved", R4)
    add("Lamp_Reflector", "Lantern", rf, "reflector", R4)
    add("Lamp_Glass", "Lantern", gl, "glass", R4)

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
    cx = A_SHAFT + 0.12 + 0.56; R = 0.56; dep = 0.50
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
    beam(f, (A_SHAFT - .05, H_FAN + R + .19, 0), (cx + .30, H_FAN + R + .19, 0), .50, .26)           # bracket housing
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
        pbr = dict(baseColorFactor=list(d.get("color", (1, 1, 1))) + [d.get("alpha", 1.0)], metallicFactor=d["metal"], roughnessFactor=d["rough"])
        if "tex" in d:
            pbr["baseColorTexture"] = dict(index=tex_names.index(d["tex"]))
        mt = dict(name=n, pbrMetallicRoughness=pbr, doubleSided=bool(d.get("double", False)))
        if "alpha" in d:
            mt["alphaMode"] = "BLEND"
        if "emissive" in d:
            mt["emissiveFactor"] = list(d["emissive"])
            if "tex" in d:
                mt["emissiveTexture"] = dict(index=tex_names.index(d["tex"]))
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
                   spot=dict(innerConeAngle=0.6, outerConeAngle=1.2), range=40.0),
              dict(name="Collar_Glow", type="point", color=[1.0, 0.90, 0.74], intensity=600.0, range=6.0)]
    nodes.append(dict(name="Lighting", children=[])); li = len(nodes) - 1; nodes[0]["children"].append(li)
    for k in range(8):                                    # facade lighting: 8 uplights on the lantern crown
        a = math.radians(45 * k); r = 1.05 if k % 2 == 0 else 1.15
        d = (math.cos(a) * 0.75, 0.66, math.sin(a) * 0.75)
        nodes.append(dict(name="Membrane_Uplight_%d" % k, translation=[r * math.cos(a), H_LANT1 + .42, r * math.sin(a)],
                          rotation=quat_from_to((0, 0, -1), d), extensions={"KHR_lights_punctual": {"light": 0}}))
        nodes[li]["children"].append(len(nodes) - 1)
    nodes.append(dict(name="Collar_Glow", translation=[0.0, H_LANT1 + .45, 0.0],          # lifts the pleats above the crown
                      extensions={"KHR_lights_punctual": {"light": 2}}))
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
    textures = dict(membrane=tex_membrane(), stone=tex_stone(), gold_engraved=tex_gold_engraved(),
                    mosaic=tex_mosaic(), floor=tex_floor())
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
