#!/usr/bin/env python3
"""
Write the umbrella as binary STL for Blender (File > Import > STL, default settings).

  python3 export_stl.py            -> stl/*.stl at full size
  python3 export_stl.py --scale 0.1

STL holds shape only: no colours, lights or animation. So this writes fixed poses
(open low, open high, closed), each as one whole file and as one file per material,
so colours can be assigned per object in Blender. Files are Z-up, in metres.
"""
import os, struct, sys, zipfile
import numpy as np
import build_umbrella as B

HERE = os.path.dirname(os.path.abspath(__file__))


def world_tris(parts, rig, joints, k):
    """Yield (material, triangles[n,3,3]) in world space at animation key k."""
    for p in parts:
        if p["name"].startswith("Piazza_Floor"):
            continue
        P = np.asarray(p["mesh"].P, float); I = np.asarray(p["mesh"].I, int).reshape(-1, 3)
        if not len(P):
            continue
        if p.get("skin"):                                   # fabric: linear blend skinning to the rig pose
            J = np.asarray(p["skin"][0], int); Wt = np.asarray(p["skin"][1], float)
            M = np.stack([rig.world(n, k) @ np.linalg.inv(rig.world(n, 0)) for n in joints])
            Ph = np.c_[P, np.ones(len(P))]
            out = np.zeros((len(P), 3))
            for c in range(4):
                out += Wt[:, c:c + 1] * np.einsum("nij,nj->ni", M[J[:, c]], Ph)[:, :3]
            yield p["mat"], out[I]
        elif p.get("node"):
            M = rig.world(p["node"], k)
            yield p["mat"], (P @ M[:3, :3].T + M[:3, 3])[I]
        else:
            for r in (p["rot"] or [0]):
                M = B.mat_trs(r=B.quat_y(r or 0))
                yield p["mat"], (P @ M[:3, :3].T)[I]


def write_stl(path, tris, scale):
    T = np.asarray(tris, float) * scale
    T = np.stack([T[..., 0], -T[..., 2], T[..., 1]], -1)   # Y-up -> Z-up; this keeps the winding right-handed
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); L = np.linalg.norm(n, axis=1, keepdims=True)
    keep = L[:, 0] > 1e-12; T, n = T[keep], n[keep] / L[keep]
    rec = np.zeros(len(T), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, T
    with open(path, "wb") as f:
        f.write(os.path.basename(path).encode()[:80].ljust(80, b" ")); f.write(struct.pack("<I", len(T))); f.write(rec.tobytes())
    return len(T)


def main():
    scale = float(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 1.0
    tag = "" if scale == 1 else "_1to%g" % (1 / scale)
    out = os.path.join(HERE, "stl"); os.makedirs(out, exist_ok=True)
    for variant, k, name in (("low", 0, "open_low"), ("high", 0, "open_high"), ("low", B.NKEY - 1, "closed")):
        parts = B.build_parts(variant); rig, joints = B.RIG["rig"], B.RIG["joints"]
        by = {}
        for mat, t in world_tris(parts, rig, joints, k):
            by.setdefault(mat, []).append(t)
        allt = np.concatenate([np.concatenate(v) for v in by.values()])
        p = os.path.join(out, "madinah_umbrella_%s%s.stl" % (name, tag))
        n = write_stl(p, allt, scale); ext = np.ptp(allt.reshape(-1, 3), axis=0) * scale
        print("%s: %d triangles, %.1f MB, %.2f x %.2f x %.2f m (x, depth, height)" % (os.path.basename(p), n, os.path.getsize(p) / 1e6, ext[0], ext[2], ext[1]))
        zp = os.path.join(out, "madinah_umbrella_%s%s_by_material.zip" % (name, tag))
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for mat, v in by.items():
                tmp = os.path.join(out, "%s.stl" % mat); write_stl(tmp, np.concatenate(v), scale); z.write(tmp, "%s.stl" % mat); os.remove(tmp)
        print("  %s: %d files, %.1f MB" % (os.path.basename(zp), len(by), os.path.getsize(zp) / 1e6))


if __name__ == "__main__":
    main()
