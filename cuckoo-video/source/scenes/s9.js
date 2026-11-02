/* s9 end: the grown cuckoo spreads its wings and flies off through the light; the mother stays on the empty nest */
(() => {
  const P = AZ.plan.scenes.s9, S = AZ.scene('s9', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's9'), { seg, eio, eo, ei, lerp, fmt } = window.W;
  const H = W.B.host, CK = W.B.cuckoo; W.show(H, true); W.show(CK, true);
  ['e1', 'e2', 'e3', 'ec'].forEach(k => W.show(W.E[k], false));
  S.draw(lt => {
    const t = lt + P.start;
    const fl = seg(lt, 3.3, 5.6), q = ei(fl);
    const camY = 960 - 140 * Math.sin(Math.min(1, seg(lt, 3.3, 6.4)) * Math.PI);
    W.setCam(lerp(580, 560, eio(seg(lt, 5.6, 7.6))), camY, lerp(1.2, 1.5, eio(seg(lt, 5.6, 7.6))));
    const n = W.toScreen(560, 990); W.glowAt(n.x, n.y, 0.9 + 0.1 * Math.sin(t * 1.1));
    const spread = eio(seg(lt, 1.3, 2.2));
    const bx = lerp(600, 1500, q), by = lerp(972, -260, q) - Math.sin(fl * Math.PI) * 120 + (fl === 0 ? Math.sin(t * 2) * 1.5 : 0);
    CK.set(bx, by, 1, lerp(0, -24, eo(fl)), 0.86);
    const flapA = fl > 0 && fl < 1 ? Math.sin(t * 22) * 46 : spread * (-30 + 22 * Math.sin(t * 7));
    CK.flap(flapA);
    CK.dip(0.05 + 0.1 * Math.sin(t * 1.6), 10, 10, 10);
    H.set(440, 968 + Math.sin(t * 2.2) * 1.5, 1, 0); H.flap(Math.sin(t * 1.5) * 1.5); H.dip(0.15 + 0.1 * Math.sin(t * 1.3) + 0.2 * seg(lt, 3.3, 4.0) * (1 - seg(lt, 5.5, 6.2)));
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('spread', 1.4, { sound: 'swipe', gain_db: -12 });
  S.label('takeoff', 3.3, { sound: 'whoosh', gain_db: -6 });
})();
