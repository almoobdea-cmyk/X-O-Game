/* s1 hook: wide forest, push in to the nest; the mother leaves at the end */
(() => {
  const P = AZ.plan.scenes.s1, S = AZ.scene('s1', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's1'), { seg, eio, eo, lerp } = window.W;
  W.show(W.B.host, true);
  S.draw(lt => {
    const t = lt + P.start, p = eio(seg(lt, 0, 3.8));
    W.setCam(lerp(500, 560, p), lerp(1080, 1000, p), lerp(0.78, 1.75, p));
    const n = W.toScreen(560, 990); W.glowAt(n.x, n.y, 0.9);
    const off = seg(lt, 3.3, 4.5), q = window.W.ei(off);
    const bob = Math.sin(t * 2.1) * 1.5;
    W.B.host.set(440 - q * 900, 975 + bob - q * 420 + Math.sin(off * 9) * 6 * off, 1, -off * 18);
    W.B.host.flap(off > 0 ? Math.sin(t * 34) * 38 : Math.sin(t * 1.5) * 1.5);
    W.B.host.dip(0.15 + 0.1 * Math.sin(t * 1.7), 0, 0, 20);
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('host_off', 3.4, { sound: 'swipe', gain_db: -14 });
})();
