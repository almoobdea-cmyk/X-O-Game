// Klatt-style cascade formant synthesizer for Arabic phones. Self-contained: no model, no data files.
import { SR } from './wav.mjs';
import { resonator } from './dsp.mjs';
import { VOWELS, classOf } from './phonemize.mjs';

// Formant targets (Hz), bandwidths, source amplitudes and frication centres per phone. Male reference voice.
const V = (f1, f2, f3) => ({ f: [f1, f2, f3], bw: [80, 100, 140], av: 1.0, af: 0, kind: 'vowel' });
export const PHONES = {
  a: V(700, 1250, 2500), 'aː': V(720, 1250, 2500), i: V(310, 2150, 2900), 'iː': V(300, 2200, 2950),
  u: V(340, 820, 2350), 'uː': V(320, 780, 2300), e: V(450, 1900, 2600), 'eː': V(430, 1950, 2650), o: V(450, 900, 2400), 'oː': V(440, 870, 2400),
  // nasals, liquids, glides, pharyngeal approximant
  m: { f: [250, 1100, 2200], bw: [120, 200, 250], av: 0.45, af: 0, kind: 'sonorant' },
  n: { f: [250, 1500, 2500], bw: [120, 200, 250], av: 0.45, af: 0, kind: 'sonorant' },
  l: { f: [350, 1200, 2700], bw: [100, 150, 200], av: 0.6, af: 0, kind: 'sonorant' },
  r: { f: [380, 1300, 2200], bw: [100, 150, 200], av: 0.65, af: 0, kind: 'sonorant', trill: true },
  w: { f: [330, 750, 2300], bw: [90, 120, 200], av: 0.7, af: 0, kind: 'sonorant' },
  j: { f: [300, 2100, 2800], bw: [90, 120, 200], av: 0.7, af: 0, kind: 'sonorant' },
  'ʕ': { f: [750, 1300, 2400], bw: [150, 200, 250], av: 0.6, af: 0.1, kind: 'sonorant', fric: [1200, 1500], f0mul: 0.9 },
  // fricatives
  f: { f: [350, 1300, 2400], bw: [150, 200, 250], av: 0, af: 0.3, kind: 'fric', fric: [1800, 4000] },
  'θ': { f: [350, 1500, 2600], bw: [150, 200, 250], av: 0, af: 0.3, kind: 'fric', fric: [3200, 4000] },
  'ð': { f: [350, 1500, 2600], bw: [150, 200, 250], av: 0.35, af: 0.25, kind: 'fric', fric: [3200, 4000] },
  'ðˤ': { f: [450, 1050, 2300], bw: [150, 200, 250], av: 0.35, af: 0.25, kind: 'fric', fric: [2600, 3500] },
  s: { f: [350, 1600, 2600], bw: [150, 200, 250], av: 0, af: 0.8, kind: 'fric', fric: [6000, 2000] },
  z: { f: [350, 1600, 2600], bw: [150, 200, 250], av: 0.35, af: 0.6, kind: 'fric', fric: [6000, 2000] },
  'sˤ': { f: [450, 1050, 2300], bw: [150, 200, 250], av: 0, af: 0.8, kind: 'fric', fric: [4500, 2000] },
  'ʃ': { f: [350, 1800, 2600], bw: [150, 200, 250], av: 0, af: 0.8, kind: 'fric', fric: [3000, 1400] },
  x: { f: [350, 1300, 2500], bw: [150, 200, 250], av: 0, af: 0.6, kind: 'fric', fric: [1900, 1000] },
  'ɣ': { f: [400, 1200, 2400], bw: [150, 200, 250], av: 0.4, af: 0.4, kind: 'fric', fric: [1900, 1000] },
  'ħ': { f: [720, 1450, 2500], bw: [200, 250, 300], av: 0, af: 0.55, kind: 'fric', fric: [1600, 2500], aspiration: true },
  h: { f: [500, 1500, 2500], bw: [250, 300, 350], av: 0, af: 0.4, kind: 'fric', fric: [1500, 3000], aspiration: true, inherit: true },
  v: { f: [350, 1300, 2400], bw: [150, 200, 250], av: 0.35, af: 0.25, kind: 'fric', fric: [1800, 4000] },
  // stops: locus formants, burst centre
  b: { f: [200, 900, 2200], bw: [100, 150, 200], av: 0.15, af: 0, kind: 'stop', voiced: true, burst: [800, 1500] },
  d: { f: [200, 1700, 2600], bw: [100, 150, 200], av: 0.15, af: 0, kind: 'stop', voiced: true, burst: [3500, 2000] },
  'dˤ': { f: [250, 1100, 2300], bw: [100, 150, 200], av: 0.15, af: 0, kind: 'stop', voiced: true, burst: [2000, 1500] },
  g: { f: [250, 1900, 2500], bw: [100, 150, 200], av: 0.15, af: 0, kind: 'stop', voiced: true, burst: [2500, 1500] },
  t: { f: [200, 1700, 2600], bw: [100, 150, 200], av: 0, af: 0, kind: 'stop', voiced: false, burst: [4000, 2000] },
  'tˤ': { f: [250, 1100, 2300], bw: [100, 150, 200], av: 0, af: 0, kind: 'stop', voiced: false, burst: [2500, 1500] },
  k: { f: [250, 1900, 2500], bw: [100, 150, 200], av: 0, af: 0, kind: 'stop', voiced: false, burst: [2500, 1500] },
  q: { f: [250, 1000, 2300], bw: [100, 150, 200], av: 0, af: 0, kind: 'stop', voiced: false, burst: [1200, 1200] },
  p: { f: [200, 900, 2200], bw: [100, 150, 200], av: 0, af: 0, kind: 'stop', voiced: false, burst: [800, 1500] },
  'ʔ': { f: [500, 1500, 2500], bw: [100, 150, 200], av: 0, af: 0, kind: 'stop', voiced: false, burst: null, glottal: true },
  'dʒ': { f: [250, 1800, 2600], bw: [100, 150, 200], av: 0.15, af: 0, kind: 'affricate', voiced: true, fric: [2800, 1400] },
  'tʃ': { f: [250, 1800, 2600], bw: [100, 150, 200], av: 0, af: 0, kind: 'affricate', voiced: false, fric: [2800, 1400] },
};

const EMPH_SHIFT = { f1: 60, f2: -320 };

function gaussian() { let u = 0, v = 0; while (u === 0) u = Math.random(); while (v === 0) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

/** Expand the phone plan into acoustic sub-segments with per-segment targets. */
function expand(plan, voice) {
  const segs = [];
  const fs = voice.formantScale ?? 1;
  const scaleF = (f) => f.map(v => v * fs);
  for (let i = 0; i < plan.length; i++) {
    const ph = plan[i];
    if (ph.p === '_') { segs.push({ kind: 'silence', dur: ph.dur, f0: 0 }); continue; }
    const base = PHONES[ph.p] || PHONES.a;
    let f = base.f.slice();
    if (ph.emphatic) { f[0] += EMPH_SHIFT.f1; f[1] += EMPH_SHIFT.f2; }
    // /h/ and glottal stop take the neighbouring vowel's shape
    if (base.inherit || base.glottal) { const nb = plan[i + 1] && VOWELS.has(plan[i + 1].p) ? PHONES[plan[i + 1].p] : (plan[i - 1] && VOWELS.has(plan[i - 1].p) ? PHONES[plan[i - 1].p] : null); if (nb) f = nb.f.slice(); }
    const common = { f: scaleF(f), bw: base.bw, f0: ph.f0 * (base.f0mul || 1), trill: !!base.trill, phone: ph.p };
    const dur = ph.dur;
    if (base.kind === 'stop') {
      const burst = base.burst ? 12 : 0, vot = base.voiced ? 5 : 25;
      const closure = Math.max(20, dur - burst - vot);
      segs.push({ ...common, kind: 'closure', dur: closure, av: base.av, af: 0 });
      if (base.burst) segs.push({ ...common, kind: 'burst', dur: burst, av: 0, af: 0.9, fric: scaleF(base.burst) });
      if (!base.voiced) segs.push({ ...common, kind: 'aspiration', dur: vot, av: 0, af: 0.35, fric: [1500 * fs, 3000] });
      else if (vot) segs.push({ ...common, kind: 'closure', dur: vot, av: 0.2, af: 0 });
    } else if (base.kind === 'affricate') {
      segs.push({ ...common, kind: 'closure', dur: Math.round(dur * 0.4), av: base.av, af: 0 });
      segs.push({ ...common, kind: 'fric', dur: Math.round(dur * 0.6), av: base.voiced ? 0.3 : 0, af: 0.8, fric: scaleF(base.fric) });
    } else {
      segs.push({ ...common, kind: base.kind, dur, av: base.av, af: base.af, fric: base.fric ? scaleF(base.fric) : null, aspiration: !!base.aspiration });
    }
  }
  return segs;
}

/** Render a phone plan to a Float32Array at 16 kHz. */
export function synthesizeFormant(plan, voice = {}) {
  const segs = expand(plan, voice);
  const total = segs.reduce((s, g) => s + g.dur, 0);
  const n = Math.round(total * SR / 1000);
  const out = new Float32Array(n);
  const breath = voice.breathiness ?? 0.08;
  const tilt = resonator(0, 100);            // glottal pulse shaping (-12 dB/oct)
  const F = [resonator(500, 80), resonator(1500, 100), resonator(2500, 140), resonator(3500, 300), resonator(4300, 400)];
  const fricRes = resonator(4000, 2000);
  const transMs = 32;
  let pos = 0, phase = 1, prevF = null, prevBw = null;
  for (let s = 0; s < segs.length; s++) {
    const g = segs[s];
    const len = Math.round(g.dur * SR / 1000);
    const fromF = prevF || g.f, fromBw = prevBw || g.bw;
    const trans = Math.min(len, Math.round(transMs * SR / 1000));
    for (let i = 0; i < len; i++, pos++) {
      if (pos >= n) break;
      if (g.kind === 'silence') { continue; }
      // formant interpolation from the previous target
      const a = trans ? Math.min(1, i / trans) : 1;
      for (let k = 0; k < 3; k++) F[k].set(fromF[k] + (g.f[k] - fromF[k]) * a, fromBw[k] + (g.bw[k] - fromBw[k]) * a);
      // amplitude envelope: 6 ms ramps at segment edges
      const ramp = Math.round(0.006 * SR);
      const env = Math.min(1, i / ramp, (len - i) / ramp);
      // voiced source
      let src = 0;
      if (g.av > 0 && g.f0 > 0) {
        phase += g.f0 / SR;
        if (phase >= 1) { phase -= 1; src = 1; }
        src = tilt.run(src / tilt.a * 0.6);   // impulse scaled so the shaped pulse peaks near 0.6
        if (g.trill) src *= 0.5 + 0.5 * Math.sin(2 * Math.PI * 28 * pos / SR);
        src *= g.av;
      }
      // aspiration noise through the cascade (breathiness and /h ħ/)
      let asp = gaussian() * (g.aspiration ? g.af * 0.5 : (g.av > 0 ? breath * g.av * 0.3 : 0));
      let x = src + asp;
      for (let k = 0; k < 5; k++) x = F[k].run(x);
      // frication noise through its own resonator, added in parallel
      let fr = 0;
      if (g.af > 0 && g.fric && !g.aspiration) { fricRes.set(g.fric[0], g.fric[1]); fr = fricRes.run(gaussian()) * g.af * 0.6; }
      out[pos] = (x + fr) * env;
    }
    prevF = g.f; prevBw = g.bw;
  }
  // radiation (first difference) and normalisation
  const rad = new Float32Array(n); let m = 0;
  for (let i = 1; i < n; i++) { rad[i] = out[i] - 0.95 * out[i - 1]; m = Math.max(m, Math.abs(rad[i])); }
  if (m > 0) for (let i = 0; i < n; i++) rad[i] = rad[i] / m * 0.7;
  return rad;
}

/** Sample boundaries (in samples) of each plan phone, for alignment tests and unit cutting. */
export function phoneBoundaries(plan) {
  const b = []; let t = 0;
  for (const ph of plan) { const len = Math.round(ph.dur * SR / 1000); b.push({ p: ph.p, start: t, end: t + len }); t += len; }
  return b;
}
