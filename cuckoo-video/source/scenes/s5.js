/* s5 turn: macro. the cuckoo egg cracks and hatches first; green outline on the hatchling */
(() => {
  const P = AZ.plan.scenes.s5, S = AZ.scene('s5', P.start, P.end, { still: P.still_at });
  const W = window.W.build(S, 's5'), { seg, eio, eo, ei, lerp, fmt } = window.W;
  W.show(W.E.e2, false); W.show(W.E.ec, true); W.show(W.C, true);
  const [ex, ey, er] = W.EP.e2, EC = W.E.ec;
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (tag, a, p) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); p.appendChild(e); return e; };
  const c1 = mk('path', { d: 'M -6 -30 L 2 -20 L -4 -10 L 6 -2 L 0 8', stroke: '#2b2118', 'stroke-width': 2.2, fill: 'none', 'stroke-linecap': 'round', 'stroke-dasharray': 60, 'stroke-dashoffset': 60 }, EC.body);
  const c2 = mk('path', { d: 'M -22 -8 L -12 -4 L -16 6 L -6 10 L -2 20 M 6 -2 L 16 0 L 14 10', stroke: '#2b2118', 'stroke-width': 2.2, fill: 'none', 'stroke-linecap': 'round', 'stroke-dasharray': 80, 'stroke-dashoffset': 80 }, EC.body);
  /* shell halves for the hatch */
  const cp = mk('clipPath', { id: 's5-clipTop' }, W.svg.querySelector('defs')); mk('rect', { x: -40, y: -50, width: 80, height: 44, transform: 'rotate(-12)' }, cp);
  const cpb = mk('clipPath', { id: 's5-clipBot' }, W.svg.querySelector('defs')); mk('rect', { x: -40, y: -6, width: 80, height: 60, transform: 'rotate(-12)' }, cpb);
  const topH = EC.body.cloneNode(true), botH = EC.body.cloneNode(true);
  topH.setAttribute('clip-path', 'url(#s5-clipTop)'); botH.setAttribute('clip-path', 'url(#s5-clipBot)');
  const halves = mk('g', { display: 'none' }, W.E.ec.g.parentNode); halves.appendChild(botH); halves.appendChild(topH);
  const C = W.C;
  S.draw(lt => {
    const t = lt + P.start;
    W.setCam(lerp(572, 578, eio(seg(lt, 0, 4.6))), 992, lerp(2.9, 3.15, eio(seg(lt, 0, 4.6))));
    const n = W.toScreen(578, 990); W.glowAt(n.x, n.y, 1);
    c1.setAttribute('stroke-dashoffset', fmt(60 * (1 - eo(seg(lt, 0.9, 1.3)))));
    c2.setAttribute('stroke-dashoffset', fmt(80 * (1 - eo(seg(lt, 1.6, 2.1)))));
    const wob = (lt > 0.6 && lt < 2.6) ? Math.sin(t * 22) * 3 * Math.pow(Math.sin(seg(lt, 0.6, 2.6) * Math.PI), 2) : 0;
    const open = lt >= 2.6;
    W.show(EC, !open); halves.setAttribute('display', open ? '' : 'none');
    EC.set(ex, ey, er + wob);
    const k = eo(seg(lt, 2.6, 3.3));
    botH.setAttribute('transform', `translate(${fmt(ex + k * 10)} ${fmt(ey + 4)}) rotate(${fmt(er + 18 * k)})`);
    topH.setAttribute('transform', `translate(${fmt(ex - 22 * k)} ${fmt(ey - 54 * k)}) rotate(${fmt(er - 70 * k)})`);
    topH.setAttribute('opacity', fmt(1 - seg(lt, 3.6, 4.4)));
    const r = eo(seg(lt, 2.6, 3.4));
    C.set(ex - 4, ey + 20 - r * 16, 1, -6 + 6 * r); C.grow(0.02 * r); C.gape(18 * Math.max(0, Math.sin(t * 3.5)) * r);
    C.hl.setAttribute('opacity', fmt(0.95 * eo(seg(lt, 2.95, 3.3)) * (0.75 + 0.25 * Math.sin(t * 6))));
    W.ambient(t); W.caption(t, P.reads);
  });
  S.label('crack1', 0.9, { sound: 'click', gain_db: -9 });
  S.label('crack2', 1.6, { sound: 'click', gain_db: -9 });
  S.label('hatch', 2.6, { sound: 'pop', gain_db: -8 });
})();
