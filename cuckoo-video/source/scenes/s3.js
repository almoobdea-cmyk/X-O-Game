/* s3 build: the cuckoo lays its egg in the gap and leaves; macro on the imposter with a yellow ring */
(() => {
  const P = AZ.plan.scenes.s3, S = AZ.scene('s3', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's3'), { seg, eio, eo, ei, lerp } = window.W;
  const CK = W.B.cuckoo; W.show(CK, true); W.show(W.E.e2, false); W.show(W.E.ec, true);
  S.draw(lt => {
    const t = lt + P.start;
    const z = lerp(1.9, 3.2, eio(seg(lt, 1.6, 2.7))) + 0.12 * seg(lt, 2.7, 4.2);
    W.setCam(lerp(600, 575, eio(seg(lt, 1.6, 2.7))), lerp(990, 992, seg(lt, 1.6, 2.7)), z);
    const n = W.toScreen(575, 990); W.glowAt(n.x, n.y, 0.9);
    const h = eio(seg(lt, 0.1, 0.6)), up = ei(seg(lt, 1.5, 2.6));
    const bx = lerp(690, 640, h) + up * 900, by = lerp(952, 992, h) - Math.sin(h * Math.PI) * 40 - up * 700;
    CK.set(bx, by, -1, lerp(0, -16, up), 1);
    CK.flap(up > 0 && up < 1 ? Math.sin(t * 28) * 44 : (h > 0 && h < 1 ? Math.sin(t * 30) * 30 : Math.sin(t * 1.3) * 1.5));
    CK.dip(0.1, 10, 10, 10);
    const [ex, ey, er] = W.EP.e2, s = eo(seg(lt, 0.9, 1.3));
    W.E.ec.set(ex, ey + (1 - s) * 10, er, Math.max(0.001, s));
    const sE = W.toScreen(ex, ey);
    W.A.ring(sE.x, sE.y, lerp(150, 92, eo(seg(lt, 2.3, 2.9))), eo(seg(lt, 2.3, 2.5)), t);
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('lay', 0.9, { sound: 'thud', gain_db: -12 });
  S.label('ring', 2.3, { sound: 'pop', gain_db: -10 });
})();
