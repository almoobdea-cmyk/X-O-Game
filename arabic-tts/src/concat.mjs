// Unit-concatenation synthesis from an enrolled voice, with PSOLA for duration and pitch, and formant fallback.
import { SR } from './wav.mjs';
import { psola, crossfadeConcat, FRAME } from './dsp.mjs';
import { synthesizeFormant } from './formant.mjs';
import { classOf } from './phonemize.mjs';

function unitCost(u, prev, next, targetMs) {
  let c = 0;
  c += u.prev === prev ? 0 : (classOf(u.prev) === classOf(prev) ? 0.6 : 1.5);
  c += u.next === next ? 0 : (classOf(u.next) === classOf(next) ? 0.6 : 1.5);
  const r = u.durMs / Math.max(20, targetMs); c += Math.abs(Math.log(Math.max(0.2, r))) * 0.8;
  return c;
}

/** Synthesize a phone plan with the enrolled voice. Phones without units fall back to the formant synthesizer. */
export function synthesizeConcat(plan, voice) {
  const byPhone = new Map();
  for (const u of voice.units) { if (!byPhone.has(u.p)) byPhone.set(u.p, []); byPhone.get(u.p).push(u); }
  const parts = []; let fallbackCount = 0;
  for (let i = 0; i < plan.length; i++) {
    const ph = plan[i];
    const len = Math.round(ph.dur * SR / 1000);
    if (ph.p === '_') { parts.push(new Float32Array(len)); continue; }
    const cands = byPhone.get(ph.p);
    if (!cands || !cands.length) {
      fallbackCount++;
      const seg = synthesizeFormant([{ ...ph, f0: ph.f0 || voice.profile.f0Base }], voice.profile);
      parts.push(seg); continue;
    }
    const prev = plan[i - 1]?.p || '#', next = plan[i + 1]?.p || '#';
    let best = cands[0], bc = Infinity;
    for (const u of cands) { const c = unitCost(u, prev, next, ph.dur); if (c < bc) { bc = c; best = u; } }
    const target = ph.voiced && ph.f0 > 0 ? new Float32Array(Math.ceil(len / FRAME) + 1).fill(ph.f0) : null;
    const seg = psola(best.samples, best.marks, len, target);
    // trim edge clicks
    const ramp = Math.min(40, seg.length >> 2);
    for (let k = 0; k < ramp; k++) { seg[k] *= k / ramp; seg[seg.length - 1 - k] *= k / ramp; }
    parts.push(seg);
  }
  const out = crossfadeConcat(parts, 64);
  let m = 0; for (let i = 0; i < out.length; i++) m = Math.max(m, Math.abs(out[i]));
  if (m > 0) for (let i = 0; i < out.length; i++) out[i] = out[i] / m * 0.7;
  return { samples: out, fallbackCount, unitCount: plan.filter(p => p.p !== '_').length - fallbackCount };
}
