/* s4 build: the mother returns, settles on the clutch; day-night-day time lapse */
(() => {
  const P = AZ.plan.scenes.s4, S = AZ.scene('s4', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's4'), { seg, eio, eo, ei, lerp } = window.W;
  const H = W.B.host; W.show(H, true); W.show(W.E.e2, false); W.show(W.E.ec, true);
  S.draw(lt => {
    const t = lt + P.start;
    W.setCam(560, 990, lerp(1.45, 1.6, eio(seg(lt, 0, 4.4))));
    const n = W.toScreen(560, 990); W.glowAt(n.x, n.y, 0.9);
    const f = eo(seg(lt, 0.1, 1.3)), air = 1 - seg(lt, 1.15, 1.35), h = eio(seg(lt, 1.6, 2.2));
    const bx = lerp(-260, 450, f) + h * 70, by = lerp(640, 970, f) - Math.sin(f * Math.PI) * 140 + h * 26;
    H.set(bx, by, 1, lerp(14, 0, f) + (h > 0 && h < 1 ? -8 * Math.sin(h * Math.PI) : 0));
    H.flap(air > 0 ? Math.sin(t * 30) * 40 : Math.sin(t * 1.4) * 1.5);
    H.dip(0.1 + 0.08 * Math.sin(t * 1.9) + 0.25 * seg(lt, 2.0, 2.4));
    /* time lapse: two days in 2 s. q = 0..2 cycles of dusk, night, dawn */
    const q = (seg(lt, 2.4, 4.3) * 2) % 1, on = lt > 2.4 && lt < 4.3;
    let col = '#ff9a3c', op = 0;
    if (on) { if (q < 0.25) { col = '#ff9a3c'; op = 0.4 * Math.sin(q / 0.25 * Math.PI); } else if (q < 0.65) { col = '#061a3a'; op = 0.68 * Math.sin((q - 0.25) / 0.4 * Math.PI); } else { col = '#ffd08a'; op = 0.35 * Math.sin((q - 0.65) / 0.35 * Math.PI); } }
    W.setTint(col, op);
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('land', 1.3, { sound: 'thud', gain_db: -14 });
  S.label('lapse', 2.4, { sound: 'paper', gain_db: -14 });
})();
