/* s7 turn: the blind naked chick backs each egg over the rim (cyan push arrows); wide cut as they fall */
(() => {
  const P = AZ.plan.scenes.s7, S = AZ.scene('s7', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's7'), { seg, eio, eo, ei, lerp, fmt } = window.W;
  const C = W.C; W.show(W.E.e2, false); W.show(C, true); W.show(W.B.host, false);
  const E1 = W.E.e1, E3 = W.E.e3;
  const pathEgg = (p, x0, y0, x1, y1, x2, y2) => { if (p < 0.6) { const q = eio(p / 0.6); return [lerp(x0, x1, q), lerp(y0, y1, q) - Math.sin(q * Math.PI) * 6]; } const q = eio((p - 0.6) / 0.4); return [lerp(x1, x2, q), lerp(y1, y2, q) + q * q * 30]; };
  const fall = (x0, y0, dx, tt) => [x0 + dx * tt, y0 + 900 * tt * tt + 120 * tt];
  S.draw(lt => {
    const t = lt + P.start, wide = lt >= 5.0;
    if (!wide) W.setCam(lerp(545, 560, eio(seg(lt, 0, 5))), 1000, lerp(2.4, 2.25, eio(seg(lt, 0, 5))));
    else W.setCam(520, lerp(1250, 1500, eio(seg(lt, 5.0, 7.2))), 0.85);
    const n = W.toScreen(560, 990); W.glowAt(n.x, n.y, wide ? 0.6 : 0.9);
    /* chick: faces left, backs into egg 1; then turns and backs into egg 3 */
    const m1 = eio(seg(lt, 1.4, 2.3)), m2 = eio(seg(lt, 3.3, 3.9));
    const face = lt < 3.1 ? 1 : -1;
    const cx = lt < 3.1 ? lerp(548, 526, m1) : lerp(548, 578, m2);
    C.set(cx, 1004 + Math.sin(t * 2.4) * 1.2, face, lt < 3.1 ? -6 * m1 : 6 * m2); C.grow(0.34 + 0.03 * seg(lt, 0, 7)); C.gape(4); C.hl.setAttribute('opacity', 0);
    C.flap(Math.sin(t * 9) * 8 * (m1 * (1 - seg(lt, 2.6, 3.0)) + m2 * (1 - seg(lt, 4.6, 5.0))));
    /* egg 1 */
    const p1 = seg(lt, 2.3, 3.3), [a1x, a1y] = pathEgg(p1, 505, 1000, 452, 960, 418, 985);
    const f1 = Math.max(0, lt - 3.3);
    const [e1x, e1y] = lt < 3.3 ? [a1x, a1y] : fall(418, 985, -60, f1);
    E1.set(e1x, e1y, -15 - p1 * 120 - f1 * 240);
    /* egg 3: starts at the right side of the cup */
    const p3 = seg(lt, 3.9, 4.9), [a3x, a3y] = pathEgg(p3, 612, 1016, 672, 962, 712, 988);
    const f3 = Math.max(0, lt - 4.9);
    const [e3x, e3y] = lt < 4.9 ? [a3x, a3y] : fall(712, 988, 55, f3);
    E3.set(e3x, e3y, 28 + p3 * 120 + f3 * 240);
    /* cyan push arrows behind the chick's back */
    const o1 = eo(seg(lt, 1.5, 1.8)) * (1 - seg(lt, 3.0, 3.25)), o2 = eo(seg(lt, 3.4, 3.7)) * (1 - seg(lt, 4.8, 5.0));
    const sA = W.toScreen(cx - 80, 996), sB = W.toScreen(cx + 80, 996);
    if (o1 > 0) W.A.arrows(sA.x, sA.y, 200, o1, t); else W.A.arrows(sB.x, sB.y, -20, wide ? 0 : o2, t);
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('push1', 2.3, { sound: 'swipe', gain_db: -8 });
  S.label('push2', 3.9, { sound: 'swipe', gain_db: -8 });
  S.label('drop', 5.3, { sound: 'whoosh', gain_db: -10 });
  S.label('ground', 6.6, { sound: 'thud', gain_db: -8 });
})();
