#!/usr/bin/env python3
"""
3D-printable miniature of the open umbrella for a 0.4 mm nozzle (FDM).

  python3 print_model.py              -> print_100mm/*.stl   (100 mm across the fabric)
  python3 print_model.py --size 150   -> print_150mm/*.stl

This is a separate, purpose-built design, not the display model scaled down: every piece is a
watertight solid, walls are at least 0.8 mm, and the three pieces print without supports.
The fabric becomes a 1 mm shell carried on ribs that stand in for the arms.
Needs: numpy, manifold3d
"""
import math, os, struct, sys
import numpy as np
import manifold3d as m3
import build_umbrella as B

HERE = os.path.dirname(os.path.abspath(__file__))
SQ2 = math.sqrt(2.0)
M = m3.Manifold
TIP_H = B.VARIANTS["low"]["tip"]                      # 14.5 m


def H(pts):
    return M.hull_points(np.asarray(pts, np.float64))


def union(lst):
    return M.batch_boolean(lst, m3.OpType.Add)


def ring(y, r, n=24, phase=0.0):
    return [(r * math.cos(phase + 2 * math.pi * i / n), y, r * math.sin(phase + 2 * math.pi * i / n)) for i in range(n)]


def octr(y, a, d=None):
    return [(x, y, z) for x, z in B.octa(a, d)]


def csq(y, a, w):                                     # chamfered square: face apothem a, face half-width w
    return octr(y, a, (a + w) / SQ2)


def rot(pts, k):
    return [B.rot4(p, k) for p in pts]


def build(size_mm):
    k = size_mm / (2 * B.HALF)                        # mm per metre
    mm = lambda v: v / k                              # a length in mm, expressed in model metres
    T_SHELL = mm(1.0)                                 # fabric shell: 1.0 mm (two 0.4 mm walls + margin)
    W_MIN = mm(0.9)                                   # thinnest rib
    YD = TIP_H - 0.15 + T_SHELL                       # flat datum = top of the fabric at the arm tips; the canopy prints upside down on it

    # ---------------- fabric surface (no micro-pleats: they are below the nozzle size) ----------------
    def surf(q, sig):
        x, y, z = B.membrane_point(q, sig, TIP_H)
        f = 1 + 0.085 * max(0.0, 1 - sig / 0.10) ** 2 * math.cos(4 * math.pi * q)
        return np.array([x / f, y, z / f])

    def sig_at(q, r):
        ex, ez, _ = B.edge_point(q); Re = math.hypot(ex, ez)
        return min(max((r - B.R_FUNNEL) / (Re - B.R_FUNNEL), 0.0), 1.0)

    NQ, NS = 144, 34
    sigs = np.linspace(0, 1, NS + 1) ** 1.5
    L = np.array([[surf(24.0 * a / NQ, s) for s in sigs] for a in range(NQ)])
    up = np.array([0, T_SHELL, 0])
    cells = []
    for a in range(NQ):
        b = (a + 1) % NQ
        for s in range(NS):
            q4 = [L[a, s], L[a, s + 1], L[b, s + 1], L[b, s]]
            cells.append(H(q4 + [p + up for p in q4]))
    # dense copy for height look-ups under the ribs
    GQ, GS = 288, 70
    G = np.array([surf(24.0 * a / GQ, s) for a in range(GQ) for s in np.linspace(0, 1, GS + 1) ** 1.5])

    def fabric_y(x, z):
        i = np.argmin((G[:, 0] - x) ** 2 + (G[:, 2] - z) ** 2)
        return float(G[i, 1])

    # ---------------- ribs = the arms, as fins from the flat datum down into the fabric shell ----------------
    def rib(p0, p1, w0, w1, step=0.35):
        p0 = np.asarray(p0, float); p1 = np.asarray(p1, float); d = p1 - p0; Ln = np.linalg.norm(d); d /= Ln
        perp = np.array([-d[1], d[0]]); n = max(int(Ln / step), 1); out = []; prev = None
        for i in range(n + 1):
            t = i / n; c = p0 + d * Ln * t; w = w0 + (w1 - w0) * t; sec = []
            for sgn in (-1, 1):
                e = c + perp * sgn * w / 2
                yb = min(fabric_y(e[0], e[1]) + T_SHELL * 0.5, YD - mm(0.3))
                sec += [(e[0], YD, e[1]), (e[0], yb, e[1])]
            if prev is not None:
                out.append(H(prev + sec))
            prev = sec
        return out

    ribs = []
    for j in range(8):
        ang = math.radians(-45 + 45 * j); u = np.array([math.cos(ang), math.sin(ang)])
        diag = (j % 2 == 0)
        ex, ez = B.edge_base(3 * j); r_end = math.hypot(ex, ez)
        if diag:                                       # clad part to 13.4 m, then the slim corner extension
            ribs += rib(u * 0.25, u * 13.4, 0.95, 0.78) + rib(u * 13.4, u * (r_end - 0.05), max(0.36, W_MIN * 1.4), max(0.30, W_MIN * 1.2))
            fork = 4.5 + 6.2
        else:
            ribs += rib(u * 0.25, u * (r_end - 0.05), 0.95, 0.75)
            fork = 4.5 + 4.4
        for dq in (-1, 1):                             # two passive arms per main arm
            px, pz = B.edge_base(3 * j + dq)
            tgt = np.array([px, pz]); tgt = tgt - (tgt - u * fork) / np.linalg.norm(tgt - u * fork) * 0.05
            ribs += rib(u * fork, tgt, max(0.24, W_MIN), max(0.24, W_MIN))

    # ---------------- ornament raised 0.3 mm on the underside: 24 seams and the ring of 24 diamonds ----------------
    orn = []; hgt = np.array([0, -mm(0.32), 0]); hw = mm(0.35)
    for q in range(24):
        rs = np.linspace(1.3, math.hypot(*B.edge_point(q)[:2]) * 0.985, 26); prev = None
        for r in rs:
            dq = hw / (r * math.radians(15)); s = sig_at(q, r)
            sec = [surf(q - dq, s), surf(q + dq, s)]; sec += [p + hgt for p in sec]
            sec = [p + np.array([0, T_SHELL * 0.3, 0]) if i < 2 else p for i, p in enumerate(sec)]
            if prev is not None:
                orn.append(H(prev + sec))
            prev = sec
        c = [surf(q, sig_at(q, 3.5)), surf(q + 0.36, sig_at(q + 0.36, 4.5)), surf(q, sig_at(q, 5.9)), surf(q - 0.36, sig_at(q - 0.36, 4.5))]
        orn.append(H([p + np.array([0, T_SHELL * 0.3, 0]) for p in c] + [p + hgt * 1.3 for p in c]))

    # ---------------- mast, collar and plug ----------------
    R_PLUG = max(0.34, mm(1.3)); Y_PLUG = 9.25
    mast = [H(ring(YD, R_PLUG) + ring(Y_PLUG + mm(0.4), R_PLUG) + ring(Y_PLUG, R_PLUG - mm(0.3))),
            H(ring(9.99, R_PLUG + mm(1.1)) + ring(10.45, R_PLUG + mm(0.9)) + ring(10.9, R_PLUG))]
    canopy = union(cells + ribs + orn + mast).trim_by_plane((0.0, -1.0, 0.0), -YD)

    # ---------------- cap: small upper canopy, crown and finial (prints upright on its flat base) ----------------
    cap = []; y1 = YD + mm(0.8); yt = B.K_H0 - 0.50
    for i in range(8):
        a0 = math.radians(-45 + 45 * i); pts = []
        for (r, da) in ((3.3, 0.0), (2.65, -22.5), (2.65, 22.5), (0.0, 0.0)):
            a = a0 + math.radians(da)
            pts += [(r * math.cos(a), YD, r * math.sin(a)), (r * math.cos(a), y1, r * math.sin(a))]
        for da in (-22.5, 0.0, 22.5):
            a = a0 + math.radians(da); pts.append((1.25 * math.cos(a), yt, 1.25 * math.sin(a)))
        pts.append((0, yt, 0)); cap.append(H(pts))
    prof = [(1.21, -.47), (1.18, -.38), (.95, -.18), (.66, .14), (.40, .48), (.22, .76), (.16, .90)]
    core = []
    for (r0, h0), (r1, h1) in zip(prof[:-1], prof[1:]):
        core.append(H(ring(B.K_H0 + h0, r0 * 0.80, 32) + ring(B.K_H0 + h1, r1 * 0.80, 32)))
    for i in range(8):                                 # the eight ridges of the gilded crown
        a = math.radians(22.5 + 45 * i); pts = [(0, B.K_H0 + prof[0][1], 0), (0, B.K_H0 + prof[-1][1], 0)]
        for r, h in prof:
            for da in (-0.16, 0.16):
                pts.append((r * math.cos(a + da), B.K_H0 + h, r * math.sin(a + da)))
        core.append(H(pts))
    yb = B.K_H0 + 1.19; rb = max(0.26, mm(1.0))
    core += [H(ring(yt - 0.05, 1.0) + ring(B.K_H0 - 0.3, 1.0)),
             H(ring(B.K_H0 + .85, max(0.2, mm(0.8))) + ring(yb, max(0.2, mm(0.8)))),
             H([(rb * math.cos(t) * math.cos(p), yb + rb * math.sin(t), rb * math.cos(t) * math.sin(p))
                for t in np.linspace(-math.pi / 2, math.pi / 2, 9) for p in np.linspace(0, 2 * math.pi, 16, endpoint=False)]),
             H(ring(yb, max(0.2, mm(0.8))) + ring(B.K_H0 + 2.205, max(0.1, mm(0.45))))]
    cap = union(cap + core)

    # ---------------- column: base, shaft, capital, frieze, lantern with lamps, socket (prints upright) ----------------
    AS = B.A_SHAFT; PS = 0.92; PW = PS * (SQ2 - 1)
    sq = lambda y, a: [(a, y, a), (-a, y, a), (-a, y, -a), (a, y, -a)]
    col = [H(sq(0, PS) + sq(0.44, PS) + octr(0.70, PS)),                                  # pedestal with broached corners
           H(octr(0.70, 0.565) + octr(0.84, 0.565) + octr(0.90, 0.505)),
           H([p for t in np.linspace(0, math.pi, 9) for p in octr(0.925 + 0.235 * (1 - math.cos(t)) / 2, 0.505 + 0.078 * math.sin(t))]),
           H(octr(0.88, 0.49) + octr(1.255, 0.49) + octr(B.H_SHAFT0, AS)),
           H(octr(B.H_SHAFT0 - 0.02, AS) + octr(B.H_CAP0 + 0.02, AS))]                     # shaft
    for (y0, y1_, r) in ((5.505, 5.56, .05), (5.565, 5.615, .04), (5.62, 5.685, .055)):
        col.append(H(octr(y0, AS) + octr((y0 + y1_) / 2, AS + r) + octr(y1_, AS)))
    col += [H(octr(B.H_CAP0, AS + .005) + csq(B.H_CAP1, .86, .60)),                         # capital
            H(csq(B.H_CAP1, .878, .612) + csq(B.H_CAP1 + .03, .878, .612) + csq(B.H_FRIEZE0, .868, .608)),
            H(csq(B.H_FRIEZE0 - .02, .84, .62) + csq(B.H_FRIEZE1 + .02, .84, .62)),          # frieze
            H(csq(B.H_FRIEZE1, .84, .62) + csq(B.H_BODY0 - .015, .935, .68) + csq(B.H_BODY0, .935, .68)),
            H(csq(B.H_BODY0 - .01, .90, .66) + csq(B.H_LANT1, .90, .66)),                   # lantern block
            H(csq(B.H_LANT1 - .01, .92, .68) + csq(B.H_LANT1 + .03, .92, .68) + octr(9.66, .50)),
            H(ring(9.66, .585, 8, math.radians(22.5)) + ring(9.97, .585, 8))]               # faceted crown
    for kq in range(4):
        col.append(H(rot([(.84, .19, z) for z in (-.38, .38)] + [(.84, .50, z) for z in (-.38, .38)] + [(.74, .50, z) for z in (-.38, .38)], kq)))
        fr = [(.86, B.H_FRIEZE0 + .12, -.50), (.86, B.H_FRIEZE0 + .12, .50), (.86, B.H_FRIEZE1 - .12, -.50), (.86, B.H_FRIEZE1 - .12, .50)]
        col.append(H(rot(fr + [(.80, p[1], p[2]) for p in fr], kq)))                        # frieze panel, 0.08 mm proud: reads as a plaque
        body = [(x, y, z) for x in (.88, 1.26) for y in (8.25, B.H_LANT1) for z in (-.38, .38)] + [(.88, 7.82, -.34), (.88, 7.82, .34)]
        roof = [(x, y, z) for x in (.87, 1.345) for y in (B.H_LANT1, 9.395) for z in (-.47, .47)] + [(1.13, 9.74, 0)]
        col += [H(rot(body, kq)), H(rot(roof, kq))]
    for kq in (0, 2):                                   # cooling fans: drum on a webbed bracket, pointed underside so it prints clean
        drum = [(1.05 + .48 * math.cos(t), B.H_FAN + .48 * math.sin(t), z) for t in np.linspace(0, 2 * math.pi, 8, endpoint=False) for z in (-.25, .25)]
        col.append(H(rot(drum, kq)))
        col.append(H(rot([(1.0, 4.30, -.14), (1.0, 4.30, .14), (1.0, 3.62, -.14), (1.0, 3.62, .14), (.40, 3.02, -.14), (.40, 3.02, .14), (.40, 4.30, -.14), (.40, 4.30, .14)], kq)))   # bracket, 45 degree underside
    col = union(col)
    hole = H(ring(9.15, R_PLUG + mm(0.18)) + ring(10.2, R_PLUG + mm(0.18)))
    col = col - hole
    return dict(canopy=canopy, cap=cap, column=col), k, YD


def to_tris(man, k, flip_at=None):
    me = man.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]; T = np.asarray(me.tri_verts)
    if flip_at is None:
        P = np.stack([V[:, 0], -V[:, 2], V[:, 1]], 1) * k                 # upright, Z-up
    else:
        P = np.stack([V[:, 0], V[:, 2], flip_at - V[:, 1]], 1) * k        # upside down on the datum (a rotation, not a mirror)
    return P[T]


def write_stl(path, T):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); L = np.linalg.norm(n, axis=1, keepdims=True); L[L == 0] = 1
    rec = np.zeros(len(T), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = n / L, T
    with open(path, "wb") as f:
        f.write(os.path.basename(path).encode()[:80].ljust(80, b" ")); f.write(struct.pack("<I", len(T))); f.write(rec.tobytes())


def overhang(T, limit_deg=45.0, zmin=0.25):
    """Area (mm2) of faces that face down more steeply than the limit and are not on the bed."""
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); A = np.linalg.norm(n, axis=1) / 2
    ok = A > 1e-9; nz = np.zeros(len(T)); nz[ok] = n[ok, 2] / (2 * A[ok])
    down = (nz < -math.cos(math.radians(limit_deg))) & (T[:, :, 2].min(1) > zmin)
    return float(A[down].sum()), float(A.sum())


def main():
    size = float(sys.argv[sys.argv.index("--size") + 1]) if "--size" in sys.argv else 100.0
    out = os.path.join(HERE, "print_%gmm" % size); os.makedirs(out, exist_ok=True)
    parts, k, YD = build(size)
    rows = []; asm = []
    A0 = np.concatenate([to_tris(man, k, None) for man in parts.values()]).reshape(-1, 3)
    fit = size / float(np.ptp(A0[:, :2], axis=0).max())                   # nothing may exceed the asked size
    k *= fit
    for name, man in parts.items():
        T = to_tris(man, k, YD if name == "canopy" else None)
        T[:, :, 2] -= T[:, :, 2].min()                                    # sit on the bed
        write_stl(os.path.join(out, "%s.stl" % name), T)
        ext = np.ptp(T.reshape(-1, 3), axis=0); oh, tot = overhang(T)
        rows.append((name, man.status() == m3.Error.NoError, man.genus(), len(T), ext, man.volume() * k ** 3 / 1000, oh))
        asm.append(to_tris(man, k, None))
    A = np.concatenate(asm); A[:, :, 2] -= A[:, :, 2].min()
    write_stl(os.path.join(out, "assembled_preview_do_not_print.stl"), A)
    ext = np.ptp(A.reshape(-1, 3), axis=0)
    print("scale 1:%.0f (%.3f mm per metre); assembled %.1f x %.1f x %.1f mm" % (1000 / k, k, ext[0], ext[1], ext[2]))
    for name, ok, genus, nt, e, vol, oh in rows:
        print("%-7s watertight=%s triangles=%d size %.1f x %.1f x %.1f mm, %.2f cm3, steep overhang %.0f mm2" % (name, ok, nt, e[0], e[1], e[2], vol, oh))
    return rows, k, ext


if __name__ == "__main__":
    main()
