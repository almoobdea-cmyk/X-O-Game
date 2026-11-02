/* s2 setup: the cuckoo lands, targets one egg, grabs it and flings it away */
(() => {
  const P = AZ.plan.scenes.s2, S = AZ.scene('s2', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's2'), { seg, eio, eo, ei, lerp } = window.W;
  const CK = W.B.cuckoo; W.show(CK, true);
  const PX = 690, PY = 952, K = CK.K;
  S.draw(lt => {
    const t = lt + P.start;
    W.setCam(600, 990, lerp(1.7, 1.9, eio(seg(lt, 0, 4.8))));
    const n = W.toScreen(560, 990); W.glowAt(n.x, n.y, 0.9);
    /* fly in: arc from the top right, flaps slow down on landing */
    const f = eo(seg(lt, 0.3, 2.0)), air = 1 - seg(lt, 1.85, 2.05);
    const bx = lerp(1380, PX, f), by = lerp(220, PY, f) - Math.sin(f * Math.PI) * 160;
    CK.set(bx, by, -1, lerp(-22, 0, f));
    CK.flap(air > 0 ? Math.sin(t * 26) * 42 * (0.4 + 0.6 * air) : Math.sin(t * 1.4) * 1.5);
    /* head dip and grab */
    const d = seg(lt, 3.2, 3.9) - 0.8 * seg(lt, 3.9, 4.3);
    CK.dip(eio(d > 0 ? Math.min(1, d) : 0), -12, 0, 52);
    const tip = CK.tip(eio(Math.max(0, Math.min(1, d))), -12, 0, 52);
    const ex = bx - tip.x * K, ey = by + tip.y * K;
    const [e2x, e2y, e2r] = W.EP.e2;
    if (lt < 3.9) W.E.e2.set(e2x, e2y, e2r);
    else if (lt < 4.3) W.E.e2.set(ex, ey + 12, e2r - 20);
    else { const q = ei(seg(lt, 4.3, 4.85)); W.E.e2.set(lerp(ex, 1250, q), lerp(ey + 12, 1550, q) - Math.sin(q * Math.PI) * 180, e2r - 20 + q * 540); }
    /* annotations: reticle, then chevron burst at the grab */
    const sE = W.toScreen(e2x, e2y);
    const ro = eo(seg(lt, 2.2, 2.6)) * (1 - seg(lt, 3.5, 3.8));
    W.A.reticle(sE.x, sE.y, ro, t, lerp(1.6, 1, eo(seg(lt, 2.2, 2.9))));
    const co = eo(seg(lt, 3.9, 4.0)) * (1 - seg(lt, 4.4, 4.7));
    const sG = W.toScreen(ex, ey + 12);
    W.A.chev(sG.x, sG.y, 120 + 60 * (1 - eo(seg(lt, 3.9, 4.3))), co, t);
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('land', 2.0, { sound: 'thud', gain_db: -10 });
  S.label('grab', 3.9, { sound: 'pop', gain_db: -8 });
})();
