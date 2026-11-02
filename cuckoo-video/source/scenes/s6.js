/* s6 build: the mother feeds the hatchling beak to beak; it grows visibly */
(() => {
  const P = AZ.plan.scenes.s6, S = AZ.scene('s6', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's6'), { seg, eio, eo, ei, lerp, fmt } = window.W;
  const H = W.B.host, C = W.C; W.show(H, true); W.show(W.E.e2, false); W.show(C, true);
  const dipAt = (lt, a) => eio(seg(lt, a, a + 0.35)) * (1 - eio(seg(lt, a + 0.6, a + 0.95)));
  S.draw(lt => {
    const t = lt + P.start;
    W.setCam(575, 978, lerp(2.2, 2.05, eio(seg(lt, 0, 4.6))));
    const n = W.toScreen(575, 985); W.glowAt(n.x, n.y, 0.9);
    const d = Math.max(dipAt(lt, 1.1), dipAt(lt, 2.6), dipAt(lt, 3.9));
    H.set(690, 950 + Math.sin(t * 2) * 1.5, -1, 0);
    H.flap(Math.sin(t * 1.4) * 1.5 + d * 6);
    H.dip(0.1 + 0.9 * d, -30, 24, 62);
    const g = 0.1 + 0.32 * seg(lt, 0, 4.6);
    C.set(560, 1002 + Math.sin(t * 2.3) * 1.2, 1, -4 + 8 * d); C.grow(g); C.gape(6 + 26 * d + 4 * Math.max(0, Math.sin(t * 5)));
    C.hl.setAttribute('opacity', 0);
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('feed1', 1.1, { sound: 'click', gain_db: -12 });
  S.label('feed2', 2.6, { sound: 'click', gain_db: -12 });
  S.label('feed3', 3.9, { sound: 'click', gain_db: -12 });
})();
