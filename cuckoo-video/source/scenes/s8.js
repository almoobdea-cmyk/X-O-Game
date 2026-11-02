/* s8 payoff: alone in the nest it grows until it dwarfs the foster mother feeding it */
(() => {
  const P = AZ.plan.scenes.s8, S = AZ.scene('s8', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's8'), { seg, eio, eo, ei, lerp, fmt } = window.W;
  const H = W.B.host, C = W.C; W.show(H, true); W.show(C, true);
  ['e1', 'e2', 'e3', 'ec'].forEach(k => W.show(W.E[k], false));
  const dipAt = (lt, a) => eio(seg(lt, a, a + 0.35)) * (1 - eio(seg(lt, a + 0.6, a + 0.95)));
  S.draw(lt => {
    const t = lt + P.start;
    W.setCam(560, lerp(975, 950, eio(seg(lt, 0, 6))), lerp(1.9, 1.45, eio(seg(lt, 0, 6))));
    const n = W.toScreen(560, 970); W.glowAt(n.x, n.y, 0.95);
    const g = 0.5 + 0.5 * eio(seg(lt, 0.2, 5.0));
    const d = Math.max(dipAt(lt, 1.0), dipAt(lt, 2.9), dipAt(lt, 4.0));
    C.set(585, 985 + Math.sin(t * 2) * 1.5, -1, 3 * d); C.grow(g); C.gape(8 + 22 * d + 3 * Math.max(0, Math.sin(t * 4))); C.hl.setAttribute('opacity', 0);
    C.flap(Math.sin(t * 2.2) * 2 + d * 5);
    H.set(440, 968 + Math.sin(t * 2.2) * 1.5, 1, 0); H.flap(Math.sin(t * 1.5) * 1.5 + d * 6);
    H.dip(0.1 + 0.9 * d, 10, -8, lerp(10, -28, g));
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('feed1', 1.0, { sound: 'click', gain_db: -12 });
  S.label('feed2', 2.9, { sound: 'click', gain_db: -12 });
  S.label('feed3', 4.0, { sound: 'click', gain_db: -12 });
})();
