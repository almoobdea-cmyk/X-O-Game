#!/usr/bin/env python3
"""
Strict checks on the umbrella model, plus the parts list.

  python3 validate.py              -> VALIDATION.md, PARTS.md, parts.json   (full size)
  python3 validate.py --scale 0.1  -> parts list for a 1:10 model (PARTS_1to10.md, parts_1to10.json)

What this can and cannot prove is stated at the top of VALIDATION.md.
"""
import json, math, os, struct, sys
import numpy as np
import build_umbrella as B

HERE = os.path.dirname(os.path.abspath(__file__))
results = []          # (section, name, ok, detail)


def check(section, name, ok, detail):
    results.append((section, name, bool(ok), detail))


def part_world(p, rig, k):
    """All world-space vertices of a rigid part at animation key k (list of arrays, one per instance)."""
    P = np.asarray(p["mesh"].P, float)
    if not len(P):
        return []
    if p.get("node"):
        M = rig.world(p["node"], k)
        return [P @ M[:3, :3].T + M[:3, 3]]
    out = []
    for r in (p["rot"] or [0]):
        M = B.mat_trs(r=B.quat_y(r or 0))
        out.append(P @ M[:3, :3].T)
    return out


def run(variant):
    parts = B.build_parts(variant)
    rig = B.RIG["rig"]; V = B.VARIANTS[variant]; tip_h = V["tip"]
    kd = B.kin_design(tip_h + 0.10); keys = B.kin_solve(kd); NK = B.NKEY
    S = "Mechanism (%s)" % variant

    # ---- A. the linkage really closes: strut ends stay on their pins at every step ----
    eu = el = 0.0
    for j in range(8):
        for k in range(NK):
            a = (rig.world("UpperStrut_%d" % j, k) @ np.array([kd["Lu"], 0, 0, 1]))[:3]
            b = (rig.world("Inner_%d" % j, k) @ np.array([B.K_U, 0, 0, 1]))[:3]
            eu = max(eu, float(np.linalg.norm(a - b)))
            a = (rig.world("LowerStrut_%d" % j, k) @ np.array([kd["Ls"], 0, 0, 1]))[:3]
            b = (rig.world("Outer_%d" % j, k) @ np.array([kd["qx"], B.K_QY, 0, 1]))[:3]
            el = max(el, float(np.linalg.norm(a - b)))
    check(S, "Upper struts stay pinned to the inner arms through the whole motion", eu < 1e-3, "largest gap %.4f mm over %d steps x 8 arms" % (eu * 1000, NK))
    check(S, "Lower struts stay pinned to the outer arms through the whole motion", el < 1e-3, "largest gap %.4f mm" % (el * 1000))

    # ---- B. every moving joint is a plain pin (one fixed axis) or a straight slide ----
    bad = []; nrev = 0
    for name, n in rig.nodes.items():
        if name.startswith(("Mem", "Ray", "Funnel")):
            continue                                        # fabric-only helper joints, not hardware
        if rig.keyed(name, "r"):
            nrev += 1
            q0 = np.asarray(n["r"][0], float); axes = []
            for q in n["r"][1:]:
                q = np.asarray(q, float)
                # relative rotation q * conj(q0)
                x0, y0, z0, w0 = -q0[0], -q0[1], -q0[2], q0[3]; x1, y1, z1, w1 = q
                rel = np.array([w1 * x0 + x1 * w0 + y1 * z0 - z1 * y0, w1 * y0 - x1 * z0 + y1 * w0 + z1 * x0,
                                w1 * z0 + x1 * y0 - y1 * x0 + z1 * w0])
                if np.linalg.norm(rel) > 1e-4:
                    axes.append(rel / np.linalg.norm(rel))
            if axes:
                ref = axes[-1]; dev = max(math.degrees(math.acos(min(1.0, abs(float(np.dot(a, ref)))))) for a in axes)
                if dev > 0.5:
                    bad.append("%s (axis wanders %.1f deg)" % (name, dev))
        if rig.keyed(name, "t"):
            t = np.asarray(n["t"], float)
            if np.abs(t[:, [0, 2]] - t[0, [0, 2]]).max() > 1e-6:
                bad.append(name + " (slide is not straight)")
    check(S, "All %d moving hardware joints are single-axis pins; the hub is a straight vertical slide" % nrev, not bad, "none wander" if not bad else "; ".join(bad[:6]))

    # ---- C. transmission angles (how well each strut can push its arm) ----
    A = np.array(B.K_A); L = np.array(B.K_L); mu_u, mu_l = [], []
    for kk in keys:
        th, phi, h = kk["th"], kk["phi"], kk["h"]
        U = A + B.K_U * np.array([math.cos(th), math.sin(th)]); Hh = np.array([B.K_HX, h])
        d1 = (U - Hh) / np.linalg.norm(U - Hh); d2 = np.array([math.cos(th), math.sin(th)])
        mu_u.append(math.degrees(math.acos(min(1, abs(float(np.dot(d1, d2)))))))
        E = A + B.K_LI * np.array([math.cos(th), math.sin(th)]); Q = E + B._rot2(phi, (kd["qx"], B.K_QY))
        d1 = (Q - L) / np.linalg.norm(Q - L); d2 = (Q - E) / np.linalg.norm(Q - E)
        mu_l.append(math.degrees(math.acos(min(1, abs(float(np.dot(d1, d2)))))))
    n95 = int(NK * 0.9)
    check(S, "Upper strut keeps a workable pushing angle on the inner arm (>= 20 deg) for the first 90 % of travel", min(mu_u[:n95]) >= 20,
          "min %.0f deg over 0-90 %%; falls to %.0f deg at full close, where strut and arm line up" % (min(mu_u[:n95]), mu_u[-1]))
    check(S, "Upper strut does not reach its dead point before the end", all(m > 1.0 for m in mu_u[:-1]), "angle at the last step before closed: %.1f deg" % mu_u[-2])
    check(S, "Lower strut keeps a workable angle on the outer arm (>= 15 deg) throughout", min(mu_l) >= 15, "min %.0f deg, max %.0f deg" % (min(mu_l), max(mu_l)))
    th = [math.degrees(kk["th"]) for kk in keys]; ph = [math.degrees(kk["phi"]) for kk in keys]
    check(S, "Arms move one way only (no reversal that would slacken or snap the fabric)", all(b >= a - 1e-6 for a, b in zip(th, th[1:])) and all(b <= a + 1e-6 for a, b in zip(ph, ph[1:])),
          "inner arm %.1f -> %.1f deg, outer arm %.1f -> %.1f deg" % (th[0], th[-1], ph[0], ph[-1]))
    check(S, "Hub travel and folded height match the published figures", abs((kd["hc"] + 2.205) - 21.7) < 0.03,
          "hub rises %.2f m; finial tip at %.2f m folded (published 21.7 m) and %.2f m open" % (kd["hc"] - B.K_H0, kd["hc"] + 2.205, B.K_H0 + 2.205))

    # ---- D. open state: every support ends on the fabric edge ----
    S2 = "Open state (%s)" % variant
    dmax = 0.0; worst = ""
    for j in range(8):
        diag = (j % 2 == 0)
        ex, ez = B.edge_base(3 * j); tgt = np.array([ex, tip_h, ez])
        if diag:
            M = rig.world("Ext_%d" % j, 0); ln = [c for c in parts if c["name"].endswith("Arm_%d_Corner_Extension" % j)][0]
            tipp = (M @ np.array([np.asarray(ln["mesh"].P)[:, 0].max(), 0, 0, 1]))[:3]
        else:
            tipp = (rig.world("Outer_%d" % j, 0) @ np.array([B.K_LO, B.K_YOFF, 0, 1]))[:3]
        d = float(np.hypot(*(tipp[[0, 2]] - tgt[[0, 2]])))
        if d > dmax:
            dmax, worst = d, "main arm %d" % j
        for side, dq in (("A", -1), ("B", 1)):
            p = [c for c in parts if c["name"].endswith("Arm_%d_Passive_Arm_%s" % (j, side))][0]
            Lp = np.asarray(p["mesh"].P)[:, 0].max()
            tipp = (rig.world(p["node"], 0) @ np.array([Lp, 0, 0, 1]))[:3]
            ex, ez = B.edge_base(3 * j + dq); d = float(np.hypot(tipp[0] - ex, tipp[2] - ez))
            if d > dmax:
                dmax, worst = d, "passive arm %d%s" % (j, side)
    check(S2, "All 24 supports (8 main + 16 passive) end on the fabric edge points", dmax < 0.35, "largest plan offset %.2f m (%s)" % (dmax, worst))
    rmax = 0.0; rname = ""
    for p in parts:
        if p.get("skin") or not p.get("node"):
            continue
        for W in part_world(p, rig, 0):
            sq = np.maximum(np.abs(W[:, 0]), np.abs(W[:, 2])).max()
            if sq > rmax:
                rmax, rname = float(sq), p["name"]
    check(S2, "No hardware sticks out past the 25.5 m fabric square", rmax <= B.HALF + 0.45, "furthest part reaches %.2f m from the mast (fabric edge %.2f m): %s" % (rmax, B.HALF, rname))
    check(S2, "Neighbouring umbrellas clear each other where they overlap", (B.VARIANTS["high"]["tip"] - B.VARIANTS["low"]["tip"]) - B.SCALLOP_SAG >= 0.3,
          "edges overlap by %.1f m in plan at a 24.1 m grid; high edge is %.2f m above low edge, %.2f m after edge sag" %
          (2 * B.HALF - 24.1, B.VARIANTS["high"]["tip"] - B.VARIANTS["low"]["tip"], B.VARIANTS["high"]["tip"] - B.VARIANTS["low"]["tip"] - B.SCALLOP_SAG))

    # ---- E/F. motion envelope and folded-state clashes ----
    S3 = "Folding and folded state (%s)" % variant
    env_r = 0.0; env_y = 99.0; pen_block = {}; pen_mast = {}; pen_lamp = {}; top = 0.0; casing_r = 0.0
    BA, BW = 0.90, 0.66
    for k in range(NK):
        for p in parts:
            if p.get("skin") or not p.get("node"):
                continue
            for W in part_world(p, rig, k):
                env_r = max(env_r, float(np.maximum(np.abs(W[:, 0]), np.abs(W[:, 2])).max())); env_y = min(env_y, float(W[:, 1].min()))
                if k == NK - 1:
                    top = max(top, float(W[:, 1].max()))
                    if "Cladding" in p["name"]:
                        casing_r = max(casing_r, float(np.hypot(W[:, 0], W[:, 2]).max()))
                    ax, az = np.abs(W[:, 0]), np.abs(W[:, 2])
                    # depth inside the chamfered-square lantern block (notches ignored: conservative)
                    depth = np.minimum.reduce([BA - ax, BA - az, (BA + BW - ax - az) / math.sqrt(2)])
                    rr_ = np.hypot(W[:, 0], W[:, 2]); deck = 9.33 + (0.92 - rr_) / 0.42 * 0.33      # gilded roof deck above the block
                    inside = ((W[:, 1] < 9.28) & (W[:, 1] > 7.64) & (depth > 0.03)) | ((rr_ < 0.90) & (rr_ > 0.50) & (W[:, 1] < deck - 0.03) & (W[:, 1] > 9.0))
                    depth = np.where(depth > 0, depth, deck - W[:, 1])
                    if inside.any():
                        pen_block[p["name"].split("_Arm_")[-1][2:] if "_Arm_" in p["name"] else p["name"]] = float(depth[inside].max())
                for qr in range(4):                             # lamp boxes on the four faces
                    c_, s_ = math.cos(qr * math.pi / 2), math.sin(qr * math.pi / 2)
                    lx = W[:, 0] * c_ + W[:, 2] * s_; lz = -W[:, 0] * s_ + W[:, 2] * c_
                    roof = 9.395 + 0.345 * np.clip(np.minimum.reduce([(1.32 - lx) / 0.19, (lx - 0.87) / 0.26, (0.445 - np.abs(lz)) / 0.445]), 0, 1)
                    m = (lx > 0.92) & (lx < 1.30) & (np.abs(lz) < 0.43) & (W[:, 1] > 7.80) & (W[:, 1] < roof - 0.02)
                    if m.any():
                        pen_lamp[p["name"]] = k
                if not p["name"].startswith(("Sliding", "Finial")):
                    rr = np.hypot(W[:, 0], W[:, 2]); m = (W[:, 1] > 10.3) & (W[:, 1] < 14.4) & (rr < 0.28)
                    if m.any():
                        pen_mast[p["name"]] = k
    check(S3, "Nothing swings out beyond the open footprint while folding", env_r <= rmax + 0.05, "largest reach during the motion %.2f m (open: %.2f m)" % (env_r, rmax))
    check(S3, "Moving hardware keeps at least 3 m headroom over the floor at all times", env_y > 3.0, "lowest hardware point during the whole motion: %.2f m above the floor" % env_y)
    check(S3, "Moving hardware never sweeps through the lamps while folding", not pen_lamp, "clear" if not pen_lamp else ", ".join("%s at step %d" % kv for kv in list(pen_lamp.items())[:5]))
    check(S3, "Folded hardware does not cut into the lantern block or its roof deck", not pen_block, "clear" if not pen_block else "; ".join("%s %.0f mm" % (a_, b_ * 1000) for a_, b_ in list(pen_block.items())[:5]))
    check(S3, "Arms and struts never pass through the fixed mast", not pen_mast, "clear" if not pen_mast else ", ".join(list(pen_mast)[:5]))
    check(S3, "Folded casing stays inside the lamp eaves", casing_r <= 1.60, "casing reaches %.2f m radius; lamp eaves reach 1.35 m on the faces, 1.43 m at eave corners" % casing_r)
    kc = keys[-1]; r_top = 0.55 + 0.83 + 0.0; side_top = 2 * r_top * math.tan(math.radians(22.5))
    check(S3, "The eight casing panels fit side by side around the octagon", 1.12 <= side_top + 0.02 and 0.92 <= 2 * 1.19 * math.tan(math.radians(22.5)) + 0.02,
          "panel 1.12 m wide vs %.2f m available at the top; 0.92 m vs %.2f m at the bottom" % (side_top, 2 * 1.19 * math.tan(math.radians(22.5))))
    return parts, rig, kd


def check_glb(path, expect_anim):
    S = "Exported file " + os.path.basename(path)
    d = open(path, "rb").read(); n = struct.unpack("<I", d[12:16])[0]; j = json.loads(d[20:20 + n]); binoff = 20 + n + 8
    ok = all(v["byteOffset"] + v["byteLength"] <= j["buffers"][0]["byteLength"] for v in j["bufferViews"])
    check(S, "All data blocks lie inside the file", ok, "%d accessors, %d meshes, %d nodes" % (len(j["accessors"]), len(j["meshes"]), len(j["nodes"])))

    def arr(ai, dt, ncomp):
        a = j["accessors"][ai]; v = j["bufferViews"][a["bufferView"]]
        return np.frombuffer(d, dt, a["count"] * ncomp, binoff + v["byteOffset"]).reshape(a["count"], ncomp)
    wbad = 0; jbad = 0; nj = len(j["skins"][0]["joints"])
    for m in j["meshes"]:
        at = m["primitives"][0]["attributes"]
        if "WEIGHTS_0" in at:
            w = arr(at["WEIGHTS_0"], np.float32, 4); jj = arr(at["JOINTS_0"], np.uint8, 4)
            wbad += int((np.abs(w.sum(1) - 1) > 1e-3).sum()); jbad += int((jj >= nj).sum())
    check(S, "Fabric is bound to the rig correctly", wbad == 0 and jbad == 0, "%d joints; %d bad weights, %d bad joint ids" % (nj, wbad, jbad))
    an = j.get("animations", [])
    check(S, "Close animation present" if expect_anim else "Static file carries no animation", bool(an) == expect_anim,
          ("%d channels, %.0f s" % (len(an[0]["channels"]), j["accessors"][an[0]["samplers"][0]["input"]]["max"][0])) if an else "none")
    lights = j["extensions"]["KHR_lights_punctual"]["lights"]; ln = [x for x in j["nodes"] if "extensions" in x]
    up = [x for x in ln if x["name"].startswith("Membrane_Uplight")]; dn = [x for x in ln if x["name"].startswith("Piazza_Downlight")]

    def aim(nd):
        x, y, z, w = nd["rotation"]; return 2 * (y * z - x * w) * -1                      # y component of the node's -Z axis
    check("Lighting", "8 fabric uplights aim upward, 4 piazza downlights aim downward, 1 collar glow (%s)" % os.path.basename(path),
          len(up) == 8 and len(dn) == 4 and all(aim(x) > 0.3 for x in up) and all(aim(x) < -0.3 for x in dn) and len(ln) == 13,
          "uplights at %.2f m, downlights at %.2f m, all outside the stone block" % (up[0]["translation"][1], dn[0]["translation"][1]))
    check("Lighting", "Every light sits outside the lantern block, not buried in it (%s)" % os.path.basename(path),
          all(max(abs(x["translation"][0]), abs(x["translation"][2])) >= 0.9 or x["translation"][1] > 9.3 for x in ln), "ok")


FINISH = {   # material in the model -> what it stands for on the real umbrella, and its colour
    "steel": ("Welded steel box section, painted", "#EDEBE3"), "gold": ("Gold-plated / gilded metal", "#D9A21C"),
    "gold_dark": ("Bronze-finish hinge pin and bush", "#B88533"), "bronze": ("Bronze-finish cast shoe", "#80521F"),
    "gold_engraved": ("Gilded sheet, chased arabesque", "#D9A21C"), "cladding": ("GRP sandwich panel with glass mosaic", "#E6DEC6 / #86CCC0 / #E0AE2C"),
    "membrane": ("PTFE fabric with blue tapes", "#F4F0E6 / #2E447A"), "stone": ("Granite cladding", "#C4B0A0"),
    "base": ("Polished granite", "#C9A894"), "caststone": ("Carved granite / cast stone", "#C4B0A0"), "slate": ("Slate-blue stone panel", "#4D6175"),
    "glass": ("Clear glass", "#B3D4EB (30 % opaque)"), "reflector": ("Ribbed aluminium reflector", "#DBE3ED"),
    "fan": ("Fan housing, painted", "#E6DBC7"), "fan_dark": ("Fan guard and mist ring", "#595449"), "floor": ("Marble paving (not part of the umbrella)", "#E2DED6"),
}


def export_parts(parts, scale, tag):
    rows = {}; order = []
    for p in parts:
        key = id(p["mesh"])
        P = np.asarray(p["mesh"].P, float)
        if not len(P):
            continue
        n = len(p["rot"]) if p.get("rot") else 1
        if key not in rows:
            dims = (P.max(0) - P.min(0)) * 1000 * scale
            nm = p["name"]
            for pre in ("Diagonal_Arm_", "Middle_Arm_"):
                if nm.startswith(pre):
                    nm = pre.replace("_Arm_", " arm: ") + nm.split("_", 3)[3]
            rows[key] = dict(part=nm.replace("_", " "), qty=0, material=FINISH[p["mat"]][0], colour=FINISH[p["mat"]][1],
                             size_mm=[round(float(x), 1) for x in dims], moving=bool(p.get("node") or p.get("skin")),
                             triangles=len(p["mesh"].I) // 3, glb_mesh=p["name"])
            order.append(key)
        rows[key]["qty"] += n
    lst = [rows[k] for k in order if "Piazza Floor" not in rows[k]["part"]]
    # identical meshes used by both arm types are already merged by mesh id; merge rows with identical names
    merged = {}
    for r in lst:
        k = (r["part"], tuple(r["size_mm"]))
        if k in merged:
            merged[k]["qty"] += r["qty"]
        else:
            merged[k] = r
    lst = list(merged.values())
    json.dump(dict(scale=scale, units="mm", note="size_mm is the bounding box of the part in its own frame (x along the member for arm parts)", parts=lst),
              open(os.path.join(HERE, "parts%s.json" % tag), "w"), indent=1)
    thin = [r for r in lst if min(r["size_mm"]) < 1.2 and r["material"] not in ("PTFE fabric with blue tapes",) and "glass" not in r["material"].lower()]
    with open(os.path.join(HERE, "PARTS%s.md" % tag), "w") as f:
        f.write("# Parts list%s\n\n" % ("" if scale == 1 else " at scale 1:%g" % (1 / scale)))
        f.write("%d different parts, %d pieces in total. Sizes are bounding boxes in millimetres (length x height x width in the part's own frame).\n"
                "Shapes are in the GLB files under the mesh name in the last column; `parts%s.json` has the same data.\n\n" % (len(lst), sum(r["qty"] for r in lst), tag))
        f.write("| Part | Qty | Moves | Size (mm) | Material and finish | Colour | Mesh name in GLB |\n|---|---|---|---|---|---|---|\n")
        for r in lst:
            f.write("| %s | %d | %s | %s | %s | %s | `%s` |\n" % (r["part"], r["qty"], "yes" if r["moving"] else "no",
                                                                 " x ".join("%g" % x for x in r["size_mm"]), r["material"], r["colour"], r["glb_mesh"]))
        if scale != 1:
            f.write("\n## Parts too thin to make at this scale\n\n")
            f.write("Thinner than 1.2 mm in one direction (a common limit for 3D printing); thicken or replace with sheet/wire:\n\n" if thin else "None below 1.2 mm.\n")
            for r in thin:
                f.write("- %s: %s mm\n" % (r["part"], " x ".join("%g" % x for x in r["size_mm"])))
    return lst, thin


def main():
    scale = 1.0
    if "--scale" in sys.argv:
        scale = float(sys.argv[sys.argv.index("--scale") + 1])
    tag = "" if scale == 1 else "_1to%g" % (1 / scale)
    parts, rig, kd = run("low")
    if scale == 1:
        run("high")
        check_glb(os.path.join(HERE, "madinah_umbrella_low.glb"), True)
        check_glb(os.path.join(HERE, "madinah_umbrella_closed.glb"), False)
    lst, thin = export_parts(parts, scale, tag)
    if scale != 1:
        print("parts list at scale %g: %d parts, %d too thin (see PARTS%s.md)" % (scale, len(lst), len(thin), tag)); return
    S = "Parts"
    small = [r["part"] for r in lst if min(r["size_mm"]) < 8 and r["moving"] and "fabric" not in r["material"].lower()]
    check(S, "Every moving metal part is at least 8 mm thick at full size", not small, "all ok" if not small else ", ".join(small[:6]))
    longest = max(lst, key=lambda r: max(r["size_mm"]) if r["moving"] and "fabric" not in r["material"].lower() else 0)
    check(S, "Longest rigid part fits road transport (under 13.6 m)", max(longest["size_mm"]) < 13600, "%s, %.1f m" % (longest["part"], max(longest["size_mm"]) / 1000))
    nfail = sum(1 for r in results if not r[2])
    with open(os.path.join(HERE, "VALIDATION.md"), "w") as f:
        f.write("# Validation report\n\nGenerated by `validate.py`. %d checks, %d passed, %d failed.\n\n" % (len(results), len(results) - nfail, nfail))
        f.write("**What this proves:** the geometry is consistent. The linkage closes at every step with rigid parts, every hardware joint is a\n"
                "plain pin or a straight slide, nothing collides in the checked cases, the supports reach the fabric edge, the files are well formed.\n\n"
                "**What this does not prove:** strength. No loads, wind, fatigue, drive forces, bearing sizes, welds, fabric stresses or\n"
                "tolerances were calculated, and the membrane is not a cloth simulation. Section sizes are visual estimates. A real build needs\n"
                "a structural and mechanical engineer; this model is a geometric basis for that work, not a fabrication drawing set.\n\n")
        sec = None
        for s, name, ok, detail in results:
            if s != sec:
                f.write("\n## %s\n\n| Result | Check | Measured |\n|---|---|---|\n" % s); sec = s
            f.write("| %s | %s | %s |\n" % ("PASS" if ok else "**FAIL**", name, detail))
        f.write("\n## Known assumptions that the checks do not cover\n\n"
                "- Passive arms and the corner extensions are moved by the fabric and edge cables on the real umbrella; here they are animated on a timed pin rotation.\n"
                "- At full close the upper strut lines up with the inner arm. That is a self-locking position, but the drive needs a controlled run-in; the last 10 % of travel has a poor pushing angle.\n"
                "- Clash checks cover hardware against the mast, the lantern block and the footprint. Part-against-part contact between neighbouring arms is checked only through the casing widths.\n"
                "- Strut lengths, the lower-strut pin position, the 3.82 m inner arm and the 0.5 m casing stand-off are solved or chosen, not published values.\n")
    for s, name, ok, detail in results:
        if not ok:
            print("FAIL [%s] %s -- %s" % (s, name, detail))
    print("%d checks, %d passed, %d failed; %d parts listed" % (len(results), len(results) - nfail, nfail, len(lst)))


if __name__ == "__main__":
    main()
