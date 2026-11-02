/* lib-world.js : shared forest world (tree, branch, nest, eggs, birds), camera, annotations, captions.
   Every frame is a pure function of t. Birds have no eyes (silhouette + plumage + posture only). */
window.W = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const lerp = (a, b, p) => a + (b - a) * p;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const eo = p => 1 - Math.pow(1 - clamp(p, 0, 1), 3);            /* cubic out */
  const eio = p => { p = clamp(p, 0, 1); return p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; };
  const ei = p => Math.pow(clamp(p, 0, 1), 3);
  const seg = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
  const rng = seed => { let s = seed >>> 0; return () => { s += 0x6D2B79F5; let r = Math.imul(s ^ (s >>> 15), 1 | s); r ^= r + Math.imul(r ^ (r >>> 7), 61 | r); return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; };
  const fmt = n => Math.round(n * 100) / 100;

  /* ---------- palette ---------- */
  const BROWNS = ['#5a3b1e', '#7a5230', '#3e2a14', '#8c6a3f', '#a07d4c', '#6b4726', '#4f3318'];
  const GREENS = ['#2f6b3f', '#3f8a4c', '#58a35a', '#7cc06a', '#245a36'];

  /* ---------- defs ---------- */
  function defs(svg, id) {
    const d = el('defs', {}, svg);
    const grad = (gid, stops, attrs, kind = 'linearGradient') => { const g = el(kind, Object.assign({ id: `${id}-${gid}` }, attrs), d); stops.forEach(s => el('stop', { offset: s[0], 'stop-color': s[1], 'stop-opacity': s[2] == null ? 1 : s[2] }, g)); };
    grad('sky', [[0, '#d9efb9'], [0.22, '#7fb86d'], [0.5, '#2f6b3f'], [0.8, '#133b29'], [1, '#07180f']], { x1: 0, y1: 0, x2: 0, y2: 1 });
    grad('glow', [[0, '#fff8e6', 0.72], [0.45, '#fff2cc', 0.28], [1, '#fff2cc', 0]], { cx: 0.5, cy: 0.5, r: 0.5 }, 'radialGradient');
    grad('bowl', [[0, '#1d1106'], [0.6, '#33200e'], [1, '#4b3118']], { cx: 0.5, cy: 0.45, r: 0.6 }, 'radialGradient');
    grad('bark', [[0, '#2b1a0c'], [0.35, '#5c3f22'], [0.6, '#8a6238'], [0.85, '#4a2f16'], [1, '#22140a']], { x1: 0, y1: 0, x2: 1, y2: 0 });
    grad('branch', [[0, '#7d5a34'], [0.45, '#5a3d20'], [1, '#2a1a0c']], { x1: 0, y1: 0, x2: 0, y2: 1 });
    grad('eggH', [[0, '#eef7ee'], [0.5, '#cfe3d4'], [1, '#8fa895']], { cx: 0.35, cy: 0.3, r: 0.8 }, 'radialGradient');
    grad('eggC', [[0, '#f0f3e6'], [0.5, '#cdd9c3'], [1, '#8d9d86']], { cx: 0.35, cy: 0.3, r: 0.8 }, 'radialGradient');
    grad('host', [[0, '#9a7d4e'], [0.55, '#6f5632'], [1, '#3d2d18']], { x1: 0, y1: 0, x2: 0.3, y2: 1 });
    grad('hostBelly', [[0, '#f3e9cf'], [1, '#cdb98f']], { x1: 0, y1: 0, x2: 0, y2: 1 });
    grad('cuck', [[0, '#8e97a3'], [0.5, '#5f6b78'], [1, '#2e3640']], { x1: 0, y1: 0, x2: 0.3, y2: 1 });
    grad('cuckBelly', [[0, '#f4f4f0'], [1, '#c9ccc7']], { x1: 0, y1: 0, x2: 0, y2: 1 });
    grad('chick', [[0, '#f0c7b4'], [0.6, '#d49a86'], [1, '#9c6b5c']], { cx: 0.4, cy: 0.35, r: 0.8 }, 'radialGradient');
    grad('chickF', [[0, '#8a7a68'], [0.6, '#5c4f42'], [1, '#2f2820']], { cx: 0.4, cy: 0.35, r: 0.8 }, 'radialGradient');
    grad('leaf', [[0, '#8fd078'], [1, '#2d6b3b']], { x1: 0, y1: 0, x2: 1, y2: 1 });
    grad('shadow', [[0, '#000', 0.55], [1, '#000', 0]], { cx: 0.5, cy: 0.5, r: 0.5 }, 'radialGradient');
    grad('ray', [[0, '#fff6d8', 0.55], [1, '#fff6d8', 0]], { x1: 0, y1: 0, x2: 0, y2: 1 });
    const blur = (fid, sd) => { const f = el('filter', { id: `${id}-${fid}`, x: '-20%', y: '-20%', width: '140%', height: '140%' }, d); el('feGaussianBlur', { stdDeviation: sd }, f); };
    blur('bFar', 11); blur('bMid', 3.5); blur('bNear', 9); blur('bSoft', 2); blur('bGlow', 18);
    const g = el('filter', { id: `${id}-outline`, x: '-40%', y: '-40%', width: '180%', height: '180%' }, d);
    el('feGaussianBlur', { stdDeviation: 6, result: 'b' }, g);
    const m = el('feMerge', {}, g); el('feMergeNode', { in: 'b' }, m); el('feMergeNode', { in: 'b' }, m); el('feMergeNode', { in: 'SourceGraphic' }, m);
    const n = el('filter', { id: `${id}-tex`, x: '0', y: '0', width: '100%', height: '100%' }, d);
    el('feTurbulence', { type: 'fractalNoise', baseFrequency: '0.9', numOctaves: 2, seed: 3, result: 'n' }, n);
    el('feColorMatrix', { type: 'matrix', values: '0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.12 0', in: 'n', result: 'a' }, n);
    el('feComposite', { in: 'a', in2: 'SourceGraphic', operator: 'in', result: 'c' }, n);
    el('feBlend', { in: 'c', in2: 'SourceGraphic', mode: 'multiply' }, n);
  }

  /* ---------- background layers ---------- */
  function farTrees(g, id, R) {
    for (let i = 0; i < 14; i++) {
      const x = -500 + i * 170 + R() * 60, h = 900 + R() * 900, w = 26 + R() * 40, top = -700 + R() * 500;
      el('rect', { x, y: top, width: w, height: 3000, fill: i % 2 ? '#1c4a35' : '#163d2b', opacity: 0.85 }, g);
      for (let k = 0; k < 4; k++) el('ellipse', { cx: x + w / 2 + (R() - .5) * 220, cy: top + 120 + k * 160 + R() * 80, rx: 150 + R() * 140, ry: 70 + R() * 50, fill: ['#2a6a44', '#1f5637', '#3a7a4e'][k % 3], opacity: 0.9 }, g);
    }
  }
  function midTrees(g, id, R) {
    const xs = [-380, 60, 1180, 1480];
    xs.forEach((x, i) => {
      const w = 90 + R() * 70;
      el('rect', { x, y: -800, width: w, height: 3400, fill: `url(#${id}-bark)`, rx: 20 }, g);
      for (let k = 0; k < 7; k++) {
        const ly = -600 + k * 230 + R() * 100, dir = (k % 2 ? 1 : -1);
        el('path', { d: `M ${x + w / 2} ${ly} q ${dir * 160} ${-90 + R() * 40} ${dir * 420} ${-40}`, stroke: '#3b2612', 'stroke-width': 14 - k, fill: 'none', 'stroke-linecap': 'round' }, g);
        for (let j = 0; j < 5; j++) el('ellipse', { cx: x + w / 2 + dir * (120 + j * 70 + R() * 40), cy: ly - 60 - j * 12 + (R() - .5) * 90, rx: 60 + R() * 50, ry: 36 + R() * 20, fill: GREENS[(j + k) % 5], opacity: 0.92, transform: `rotate(${(R() - .5) * 60} ${x} ${ly})` }, g);
      }
    });
  }
  function rays(g, id, R) {
    const out = [];
    for (let i = 0; i < 6; i++) {
      const x = 700 + i * 120 + R() * 40, w = 60 + R() * 90;
      const p = el('polygon', { points: `${x},-300 ${x + w},-300 ${x + w - 420},2300 ${x - 560},2300`, fill: `url(#${id}-ray)`, opacity: 0.18 + R() * 0.16, filter: `url(#${id}-bGlow)` }, g);
      out.push({ p, x, ph: R() * 6.28, base: 0.16 + R() * 0.14 });
    }
    return out;
  }
  function nearLeaves(g, id, R) {
    const spots = [[-40, 300], [1080, 180], [60, 1750], [1060, 1600], [-60, 1100], [1120, 900]];
    spots.forEach(([x, y], i) => { for (let k = 0; k < 7; k++) el('ellipse', { cx: x + (R() - .5) * 260, cy: y + (R() - .5) * 320, rx: 70 + R() * 60, ry: 32 + R() * 24, fill: ['#0f3a24', '#1b5a36', '#143f2a'][k % 3], opacity: 0.9, transform: `rotate(${R() * 180} ${x} ${y})` }, g); });
  }
  function dust(g, R) {
    const out = [];
    for (let i = 0; i < 240; i++) { const d = { x: R() * 1080, y: R() * 1920, r: 1.2 + R() * 2.6, sp: 22 + R() * 16, sw: 6 + R() * 18, ph: R() * 6.28, o: 0.18 + R() * 0.45 }; d.e = el('circle', { cx: d.x, cy: d.y, r: d.r, fill: '#fff4d6', opacity: d.o }, g); out.push(d); }
    return out;
  }

  /* ---------- subject: tree, branch, leaves ---------- */
  function tree(g, id, R) {
    const trunk = el('g', {}, g);
    el('path', { d: 'M 40 -900 C 20 -300, 70 300, 30 900 C 10 1300, 60 1900, 20 2600 L 330 2600 C 300 1900, 330 1300, 290 900 C 260 300, 310 -300, 280 -900 Z', fill: `url(#${id}-bark)`, filter: `url(#${id}-tex)` }, trunk);
    for (let i = 0; i < 46; i++) { const x = 50 + R() * 220, y0 = -850 + R() * 3300, l = 140 + R() * 300; el('path', { d: `M ${x} ${y0} c ${(R() - .5) * 30} ${l * .4}, ${(R() - .5) * 30} ${l * .6}, ${(R() - .5) * 18} ${l}`, stroke: R() > .5 ? '#20120a' : '#a37a4b', 'stroke-width': 1.5 + R() * 3.5, opacity: 0.35 + R() * 0.5, fill: 'none', 'stroke-linecap': 'round' }, trunk); }
    for (let i = 0; i < 18; i++) el('ellipse', { cx: 60 + R() * 200, cy: 600 + R() * 1200, rx: 18 + R() * 40, ry: 8 + R() * 14, fill: '#4f8a3c', opacity: 0.25 + R() * 0.35 }, trunk);
    /* branch: tapered body from the trunk to the right */
    const br = el('g', {}, g);
    el('path', { d: 'M 150 1210 C 360 1080, 700 1010, 1060 935 C 1070 950, 1065 962, 1060 968 C 700 1050, 380 1130, 160 1262 Z', fill: `url(#${id}-branch)`, filter: `url(#${id}-tex)` }, br);
    el('path', { d: 'M 150 1210 C 360 1080, 700 1010, 1060 935', stroke: '#a57f52', 'stroke-width': 4, fill: 'none', opacity: 0.6 }, br);
    el('path', { d: 'M 170 1250 C 380 1120, 700 1040, 1058 964', stroke: '#1d110a', 'stroke-width': 5, fill: 'none', opacity: 0.7 }, br);
    for (let i = 0; i < 40; i++) { const t = R(), x = 160 + t * 900, y = 1225 - t * 270 + (R() - .5) * 26; el('path', { d: `M ${x} ${y} l ${30 + R() * 50} ${-(8 + R() * 14)}`, stroke: R() > .5 ? '#2a180c' : '#b08a5a', 'stroke-width': 1.2 + R() * 2.2, opacity: 0.5, fill: 'none', 'stroke-linecap': 'round' }, br); }
    const twigs = [[860, 985, -1], [1000, 950, -1], [330, 1150, -1], [760, 1010, 1], [1040, 945, 1]];
    twigs.forEach(([x, y, d], i) => {
      el('path', { d: `M ${x} ${y} c ${20 * d} ${-60}, ${60 * d} ${-90}, ${110 * d} ${-150 * (d > 0 ? -0.3 : 1)}`, stroke: '#3b2612', 'stroke-width': 9 - i, fill: 'none', 'stroke-linecap': 'round' }, br);
      const ex = x + 110 * d, ey = y - 150 * (d > 0 ? -0.3 : 1);
      for (let k = 0; k < 9; k++) el('ellipse', { cx: ex + (R() - .5) * 120, cy: ey + (R() - .5) * 110, rx: 34 + R() * 22, ry: 14 + R() * 9, fill: `url(#${id}-leaf)`, opacity: 0.95, transform: `rotate(${R() * 180} ${ex} ${ey})` }, br);
    });
    return { trunk, br };
  }

  /* ---------- nest ---------- */
  function nest(g, id, R, cx, cy) {
    const back = el('g', {}, g), front = el('g', {}, g);
    el('ellipse', { cx: cx + 10, cy: cy + 70, rx: 190, ry: 46, fill: `url(#${id}-shadow)` }, back);
    const twig = (parent, a0, len, rx, ry, dy, w, col, op) => {
      let d = ''; const n = 14;
      for (let k = 0; k <= n; k++) { const a = a0 + len * k / n, jr = 1 + (R() - .5) * 0.08; const x = cx + Math.cos(a) * rx * jr, y = cy + dy + Math.sin(a) * ry * jr; d += (k ? ' L ' : 'M ') + fmt(x) + ' ' + fmt(y); }
      el('path', { d, stroke: col, 'stroke-width': w, fill: 'none', opacity: op, 'stroke-linecap': 'round' }, parent);
    };
    /* outer body: rings stacked downwards (cup shape), darker toward the bottom */
    for (let ring = 0; ring < 9; ring++) { const f = ring / 8, rx = 165 - f * 95, ry = 62 - f * 30, dy = f * 95; for (let i = 0; i < 16; i++) twig(back, R() * 6.28, 0.5 + R() * 1.4, rx + (R() - .5) * 18, ry + (R() - .5) * 8, dy, 2.5 + R() * 4, BROWNS[(i + ring) % BROWNS.length], 0.75 + R() * 0.25); }
    el('ellipse', { cx, cy: cy - 8, rx: 128, ry: 50, fill: `url(#${id}-bowl)` }, back);
    for (let i = 0; i < 40; i++) twig(back, R() * 6.28, 0.3 + R() * 0.9, 50 + R() * 70, 20 + R() * 26, -4 + R() * 10, 1 + R() * 1.6, i % 3 ? '#b79a6a' : '#6f5537', 0.6);
    /* front rim: over the eggs */
    for (let i = 0; i < 38; i++) twig(front, 0.1 + R() * 2.9, 0.5 + R() * 1.6, 150 + (R() - .5) * 20, 58 + (R() - .5) * 10, (R() - .5) * 10, 2.5 + R() * 4.5, BROWNS[i % BROWNS.length], 0.85 + R() * 0.15);
    for (let i = 0; i < 12; i++) twig(front, 0.3 + R() * 2.5, 0.2 + R() * 0.5, 160 + R() * 30, 64 + R() * 10, -2, 1.5 + R(), '#c2a26e', 0.7);
    return { back, front };
  }

  /* ---------- egg ---------- */
  function egg(parent, id, R, kind) {
    const g = el('g', {}, parent), cuck = kind === 'cuckoo', rx = cuck ? 25 : 23, ry = cuck ? 33 : 31;
    el('ellipse', { cx: 0, cy: 36, rx: rx * 1.1, ry: 8, fill: `url(#${id}-shadow)` }, g);
    const body = el('g', {}, g);
    el('ellipse', { cx: 0, cy: 0, rx, ry, fill: `url(#${id}-${cuck ? 'eggC' : 'eggH'})` }, body);
    const n = cuck ? 34 : 26;
    for (let i = 0; i < n; i++) { const a = R() * 6.28, r = Math.sqrt(R()) * 0.92; const x = Math.cos(a) * r * rx, y = Math.sin(a) * r * ry; el('ellipse', { cx: x, cy: y, rx: 1.2 + R() * 2.4, ry: 1 + R() * 1.8, fill: cuck ? '#5a4a3a' : '#6e5440', opacity: 0.45 + R() * 0.45, transform: `rotate(${R() * 180} ${x} ${y})` }, body); }
    el('ellipse', { cx: -7, cy: -12, rx: 7, ry: 10, fill: '#fff', opacity: 0.35 }, body);
    return { g, body, rx, ry, set(x, y, rot, s = 1) { g.setAttribute('transform', `translate(${fmt(x)} ${fmt(y)}) rotate(${fmt(rot)}) scale(${fmt(s)})`); } };
  }

  /* ---------- birds (faceless) ---------- */
  function bird(parent, id, kind) {
    const g = el('g', {}, parent), flip = el('g', {}, g), cuck = kind === 'cuckoo', K = cuck ? 1.75 : 1;
    const sc = el('g', { transform: `scale(${K})` }, flip);
    const tail = el('g', {}, sc);
    if (cuck) { el('path', { d: 'M -42 -4 C -70 -8, -110 -2, -150 14 C -140 22, -100 26, -40 18 Z', fill: '#2a3139' }, tail); for (let i = 0; i < 5; i++) el('ellipse', { cx: -70 - i * 16, cy: 6 + i * 1.6, rx: 3.2, ry: 2.2, fill: '#f2f2ee', opacity: 0.9 }, tail); }
    else { el('path', { d: 'M -40 -2 C -60 -8, -85 -4, -98 8 C -90 14, -62 16, -40 14 Z', fill: '#5a4226' }, tail); el('path', { d: 'M -46 2 L -92 10', stroke: '#2a1c0e', 'stroke-width': 1, opacity: 0.6 }, tail); }
    const body = el('g', {}, sc);
    el('path', { d: 'M -50 0 C -50 -34, -10 -42, 20 -34 C 45 -28, 56 -10, 48 8 C 40 28, 0 36, -30 26 C -48 18, -52 10, -50 0 Z', fill: `url(#${id}-${cuck ? 'cuck' : 'host'})` }, body);
    el('path', { d: 'M -34 10 C -20 30, 20 32, 46 10 C 40 24, 10 34, -24 26 Z', fill: `url(#${id}-${cuck ? 'cuckBelly' : 'hostBelly'})` }, body);
    if (cuck) for (let i = 0; i < 6; i++) el('path', { d: `M ${-30 + i * 12} ${18 + Math.abs(i - 2.5) * 1.6} q 6 7 12 0`, stroke: '#3a4149', 'stroke-width': 1.6, fill: 'none', opacity: 0.8 }, body);
    const wing = el('g', {}, body);
    el('path', { d: cuck ? 'M -30 -12 C -10 -34, 40 -34, 70 -40 C 50 -20, 20 -2, -36 0 Z' : 'M -30 -14 C -10 -32, 30 -30, 44 -20 C 24 -8, -2 2, -36 -2 Z', fill: cuck ? '#3d4651' : '#4a3620' }, wing);
    for (let i = 0; i < 5; i++) el('path', { d: cuck ? `M ${-20 + i * 14} ${-8 - i * 3} L ${30 + i * 8} ${-26 - i * 3}` : `M ${-22 + i * 11} ${-6 - i * 2} L ${12 + i * 6} ${-18 - i * 2}`, stroke: cuck ? '#1f252c' : '#2a1c0e', 'stroke-width': 1.2, opacity: 0.55 }, wing);
    const head = el('g', {}, sc);
    el('path', { d: 'M 10 -4 C 14 -22, 26 -36, 40 -40 L 50 -22 C 36 -22, 26 -12, 22 2 Z', fill: cuck ? '#5f6b78' : '#6f5632' }, head);
    el('ellipse', { cx: 40, cy: -30, rx: 17, ry: 15, fill: cuck ? '#6a7480' : '#7a5f3a' }, head);
    el('path', { d: 'M 24 -36 C 34 -46, 50 -44, 56 -34 C 52 -22, 34 -20, 24 -28 Z', fill: cuck ? '#58626d' : '#6b5233' }, head);
    el('path', { d: cuck ? 'M 54 -32 L 80 -27 L 54 -22 Z' : 'M 55 -32 L 74 -28 L 55 -24 Z', fill: cuck ? '#2b2f33' : '#3a2a16' }, head);
    el('path', { d: cuck ? 'M 54 -27 L 80 -27' : 'M 55 -28 L 74 -28', stroke: '#111', 'stroke-width': 0.8, opacity: 0.7 }, head);
    const legs = el('g', {}, sc);
    [[-8, 24], [6, 26]].forEach(([x, y]) => { el('path', { d: `M ${x} ${y} L ${x + 2} ${y + 28} M ${x - 8} ${y + 32} L ${x + 2} ${y + 28} L ${x + 12} ${y + 31}`, stroke: cuck ? '#c9b26a' : '#5a4a3a', 'stroke-width': 2.4, fill: 'none', 'stroke-linecap': 'round' }, legs); });
    const o = { g, flip, body, wing, head, tail, legs, K };
    o.set = (x, y, face = 1, rot = 0, s = 1) => { g.setAttribute('transform', `translate(${fmt(x)} ${fmt(y)}) rotate(${fmt(rot)}) scale(${fmt(s)})`); flip.setAttribute('transform', `scale(${face} 1)`); };
    o.flap = a => wing.setAttribute('transform', `rotate(${fmt(a)} -30 -12)`);
    o.dip = (d, tx = 0, ty = 0, ang = 40) => head.setAttribute('transform', `translate(${fmt(tx * d * 0.35)} ${fmt(ty * d * 0.35)}) rotate(${fmt(ang * d)} 24 -16)`);
    o.tip = (d, tx = 0, ty = 0, ang = 40) => { const a = ang * d * Math.PI / 180, px = (cuck ? 80 : 74) - 24, py = (cuck ? -27 : -28) + 16; return { x: 24 + Math.cos(a) * px - Math.sin(a) * py + tx * d * 0.35, y: -16 + Math.sin(a) * px + Math.cos(a) * py + ty * d * 0.35 }; };
    return o;
  }
  function chick(parent, id) {
    const g = el('g', {}, parent), flip = el('g', {}, g), sc = el('g', {}, flip);
    const hl = el('g', { opacity: 0, filter: `url(#${id}-outline)` }, sc);
    el('ellipse', { cx: 0, cy: 0, rx: 42, ry: 32, fill: 'none', stroke: '#5cff6a', 'stroke-width': 5 }, hl);
    el('ellipse', { cx: 24, cy: -30, rx: 26, ry: 23, fill: 'none', stroke: '#5cff6a', 'stroke-width': 5 }, hl);
    const naked = el('g', {}, sc), feath = el('g', { opacity: 0 }, sc);
    [[naked, 'chick'], [feath, 'chickF']].forEach(([p, gr]) => {
      el('ellipse', { cx: 0, cy: 0, rx: 40, ry: 30, fill: `url(#${id}-${gr})` }, p);
      el('path', { d: 'M -20 -12 C -30 -34, 0 -40, 6 -24 C 0 -16, -8 -12, -20 -12 Z', fill: `url(#${id}-${gr})`, opacity: 0.9 }, p);
      el('ellipse', { cx: 24, cy: -30, rx: 24, ry: 21, fill: `url(#${id}-${gr})` }, p);
    });
    for (let i = 0; i < 7; i++) el('path', { d: `M ${-28 + i * 9} ${-4 + Math.abs(i - 3) * 3} q 5 9 10 0`, stroke: '#2b241d', 'stroke-width': 1.5, fill: 'none', opacity: 0.6 }, feath);
    const wing = el('g', {}, sc);
    el('path', { d: 'M -22 -8 C -8 -24, 28 -22, 44 -16 C 26 -4, 0 4, -28 0 Z', fill: '#4a3f36' }, wing);
    const beak = el('g', {}, sc);
    el('path', { d: 'M 42 -36 L 68 -31 L 42 -24 Z', fill: '#e6a24a' }, beak);
    el('path', { d: 'M 42 -31 L 68 -31', stroke: '#8a5a1e', 'stroke-width': 1, opacity: 0.8 }, beak);
    const o = { g, flip, sc, hl, feath, wing, beak };
    o.set = (x, y, face = 1, rot = 0) => { g.setAttribute('transform', `translate(${fmt(x)} ${fmt(y)}) rotate(${fmt(rot)})`); flip.setAttribute('transform', `scale(${face} 1)`); };
    o.grow = p => { p = clamp(p, 0, 1); sc.setAttribute('transform', `scale(${fmt(0.75 + p * 2.3)})`); feath.setAttribute('opacity', fmt(clamp((p - 0.25) / 0.5, 0, 1))); wing.setAttribute('opacity', fmt(clamp((p - 0.15) / 0.3, 0, 1))); };
    o.gape = a => beak.setAttribute('transform', `rotate(${fmt(-a)} 42 -31)`);
    o.flap = a => wing.setAttribute('transform', `rotate(${fmt(a)} -22 -8)`);
    return o;
  }

  /* ---------- annotations (screen space) ---------- */
  function anno(svg) {
    const g = el('g', { class: 'anno' }, svg);
    const ring = el('g', { opacity: 0 }, g); el('circle', { cx: 0, cy: 0, r: 100, fill: 'none', stroke: '#ffd23f', 'stroke-width': 7 }, ring); el('circle', { cx: 0, cy: 0, r: 100, fill: 'none', stroke: '#ffd23f', 'stroke-width': 2, opacity: 0.5, class: 'r2' }, ring);
    const chev = el('g', { opacity: 0 }, g), chs = [];
    for (let i = 0; i < 8; i++) { const c = el('path', { d: 'M -16 -22 L 0 0 L -16 22', stroke: '#ffe066', 'stroke-width': 7, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, chev); chs.push(c); }
    const arr = el('g', { opacity: 0 }, g), ars = [];
    for (let i = 0; i < 3; i++) { const a = el('path', { d: 'M -22 -30 L 0 0 L -22 30 M -46 -30 L -24 0 L -46 30', stroke: '#5fe8ff', 'stroke-width': 9, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, arr); ars.push(a); }
    const ret = el('g', { opacity: 0 }, g); el('circle', { cx: 0, cy: 0, r: 70, fill: 'none', stroke: '#ff3b3b', 'stroke-width': 4 }, ret); el('circle', { cx: 0, cy: 0, r: 6, fill: '#ff3b3b' }, ret);
    [[0, -95, 0, -55], [0, 55, 0, 95], [-95, 0, -55, 0], [55, 0, 95, 0]].forEach(([a, b, c, d]) => el('path', { d: `M ${a} ${b} L ${c} ${d}`, stroke: '#ff3b3b', 'stroke-width': 4, 'stroke-linecap': 'round' }, ret));
    return {
      g,
      ring(x, y, r, op, t) { ring.setAttribute('opacity', fmt(op)); const s = 1 + 0.06 * Math.sin(t * 7); ring.setAttribute('transform', `translate(${fmt(x)} ${fmt(y)}) scale(${fmt(r / 100 * s)})`); ring.querySelector('.r2').setAttribute('transform', `scale(${fmt(1 + 0.25 * (0.5 + 0.5 * Math.sin(t * 4)))})`); },
      chev(x, y, r, op, t) { chev.setAttribute('opacity', fmt(op)); chev.setAttribute('transform', `translate(${fmt(x)} ${fmt(y)})`); chs.forEach((c, i) => { const a = i / 8 * 360, rr = r + 14 * Math.sin(t * 9 + i); c.setAttribute('transform', `rotate(${a}) translate(${fmt(-rr)} 0) rotate(0)`); }); },
      arrows(x, y, ang, op, t) { arr.setAttribute('opacity', fmt(op)); arr.setAttribute('transform', `translate(${fmt(x)} ${fmt(y)}) rotate(${fmt(ang)})`); ars.forEach((a, i) => { const ph = (t * 2.2 + i * 0.33) % 1; a.setAttribute('transform', `translate(${fmt(-40 + i * 64 + ph * 20)} 0)`); a.setAttribute('opacity', fmt(0.35 + 0.65 * Math.pow(Math.sin(ph * Math.PI), 2))); }); },
      reticle(x, y, op, t, s = 1) { ret.setAttribute('opacity', fmt(op)); ret.setAttribute('transform', `translate(${fmt(x)} ${fmt(y)}) rotate(${fmt(t * 40)}) scale(${fmt(s)})`); },
    };
  }

  /* ---------- world ---------- */
  function build(S, id) {
    const root = S.mount(`
      <style>
        #${id} { background: #0a2419; }
        #${id} svg.world { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }
        #${id} .cap { position: absolute; left: 40px; right: 40px; top: 1440px; text-align: center; font-family: var(--font-display); font-weight: 900; font-size: 84px; line-height: 1.25; color: #fff;
                      -webkit-text-stroke: 11px #0b0b0b; paint-order: stroke fill; text-shadow: 0 8px 22px rgba(0,0,0,.65); opacity: 0; transform-origin: 50% 50%; }
        #${id} .cap span { display: inline-block; }
        #${id} .tint { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; opacity: 0; pointer-events: none; }
      </style>
      <svg class="world" viewBox="0 0 1080 1920"></svg>
      <div class="tint"></div>
      <div class="cap" dir="auto"><span></span></div>`);
    const svg = root.querySelector('svg.world');
    defs(svg, id);
    const R = rng(1234);
    el('rect', { x: -800, y: -1500, width: 2700, height: 5000, fill: `url(#${id}-sky)` }, svg);
    const far = el('g', { filter: `url(#${id}-bFar)` }, svg); farTrees(far, id, R);
    el('rect', { x: -800, y: -1500, width: 2700, height: 5000, fill: '#2f6b3f', opacity: 0.35 }, svg);
    const rayG = el('g', {}, svg); const rayL = rays(rayG, id, R);
    const mid = el('g', { filter: `url(#${id}-bMid)` }, svg); midTrees(mid, id, R);
    const glowG = el('g', {}, svg); const glow = el('ellipse', { cx: 540, cy: 900, rx: 520, ry: 640, fill: `url(#${id}-glow)` }, glowG);
    const subj = el('g', {}, svg);
    const T = tree(subj, id, R);
    const NX = 560, NY = 1010;
    const N = nest(subj, id, R, NX, NY);
    const eggsG = el('g', {}, subj); subj.insertBefore(eggsG, N.front);
    const E = { e1: egg(eggsG, id, R, 'host'), e2: egg(eggsG, id, R, 'host'), e3: egg(eggsG, id, R, 'host'), ec: egg(eggsG, id, R, 'cuckoo') };
    const EP = { e1: [505, 1000, -15], e2: [578, 990, 10], e3: [545, 1024, 28] };
    E.e1.set(...EP.e1); E.e2.set(...EP.e2); E.e3.set(...EP.e3); E.ec.set(...EP.e2); E.ec.g.setAttribute('display', 'none');
    const chickG = el('g', {}, subj); subj.insertBefore(chickG, N.front);
    const C = chick(chickG, id); C.set(555, 1000, 1); C.grow(0); C.g.setAttribute('display', 'none');
    const birdsG = el('g', {}, subj);
    const B = { host: bird(birdsG, id, 'host'), cuckoo: bird(birdsG, id, 'cuckoo') };
    B.host.set(440, 975, 1); B.host.g.setAttribute('display', 'none'); B.cuckoo.g.setAttribute('display', 'none');
    const near = el('g', { filter: `url(#${id}-bNear)` }, svg); nearLeaves(near, id, R);
    const dustG = el('g', {}, svg); const D = dust(dustG, R);
    const A = anno(svg);
    const cap = root.querySelector('.cap'), capSpan = cap.querySelector('span'), tint = root.querySelector('.tint');
    const layers = [[far, 0.15], [mid, 0.4], [subj, 1.0], [near, 1.35]];
    const cam = { x: 540, y: 960, z: 1 };
    const W = {
      root, svg, R, E, EP, C, B, A, N, T, cam, glow, cap, tint,
      setCam(cx, cy, z) {
        cam.x = cx; cam.y = cy; cam.z = z;
        layers.forEach(([g, p]) => { const zp = 1 + (z - 1) * p; const tx = 540 - 540 * zp - (cx - 540) * p * zp, ty = 960 - 960 * zp - (cy - 960) * p * zp; g.setAttribute('transform', `translate(${fmt(tx)} ${fmt(ty)}) scale(${fmt(zp)})`); });
      },
      toScreen(wx, wy) { return { x: 540 + (wx - cam.x) * cam.z, y: 960 + (wy - cam.y) * cam.z }; },
      ambient(t) {
        D.forEach(d => { const y = ((d.y - t * d.sp) % 1920 + 1920) % 1920, x = d.x + Math.sin(t * 0.7 + d.ph) * d.sw; d.e.setAttribute('cx', fmt(x)); d.e.setAttribute('cy', fmt(y)); d.e.setAttribute('opacity', fmt(d.o * (0.6 + 0.4 * Math.sin(t * 1.3 + d.ph)) * Math.min(1, y / 120, (1920 - y) / 120))); });
        rayL.forEach((r, i) => { r.p.setAttribute('opacity', fmt(r.base * (0.75 + 0.25 * Math.sin(t * 0.5 + r.ph)))); r.p.setAttribute('transform', `rotate(${fmt(1.5 * Math.sin(t * 0.21 + r.ph))} ${r.x} -300)`); });
        glow.setAttribute('rx', fmt(520 + 14 * Math.sin(t * 0.9))); glow.setAttribute('ry', fmt(640 + 16 * Math.cos(t * 0.7)));
      },
      glowAt(sx, sy, k = 1) { glow.setAttribute('cx', fmt(sx)); glow.setAttribute('cy', fmt(sy)); glowG.setAttribute('opacity', fmt(k)); },
      caption(t, reads) {
        let cur = null; for (const r of reads) if (t >= r.in && t < r.out) cur = r;
        if (!cur) { cap.style.opacity = 0; return; }
        if (capSpan.textContent !== cur.text) capSpan.textContent = cur.text;
        const p = eo(seg(t, cur.in, cur.in + 0.14));
        cap.style.opacity = fmt(p); cap.style.transform = `scale(${fmt(0.9 + 0.1 * p)}) translateY(${fmt((1 - p) * 14)}px)`;
      },
      setTint(color, op) { tint.style.background = color; tint.style.opacity = fmt(op); },
      show(o, on) { o.g.setAttribute('display', on ? '' : 'none'); },
    };
    W.setCam(540, 960, 1);
    return W;
  }
  return { build, lerp, clamp, eo, eio, ei, seg, rng, fmt };
})();
