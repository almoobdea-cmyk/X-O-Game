// Voice enrollment: turn recordings of the enrollment script into a speaker profile and a unit inventory.
import { SR } from './wav.mjs';
import { FRAME, frameEnergyDb, trackPitch, spectralCentroid, lpcPeaks, A_PEAK_REFERENCE, pitchMarks, splitOnSilence } from './dsp.mjs';
import { phonemize, VOWELS, classOf } from './phonemize.mjs';

/** Per-frame features for alignment. */
export function features(x) {
  const e = frameEnergyDb(x), { f0, voicing } = trackPitch(x), c = spectralCentroid(x);
  const n = Math.min(e.length, voicing.length, c.length);
  let maxE = -100, minE = 100; for (let i = 0; i < n; i++) { maxE = Math.max(maxE, e[i]); minE = Math.min(minE, e[i]); }
  const feats = [];
  for (let i = 0; i < n; i++) feats.push({ e: (e[i] - minE) / Math.max(1, maxE - minE), v: voicing[i], c: c[i], f0: f0[i] });
  return feats;
}

const CENTROID_FRIC = { f: 2500, 'θ': 3000, 'ð': 3000, 'ðˤ': 2500, s: 5000, z: 4500, 'sˤ': 4000, 'ʃ': 2800, x: 1800, 'ɣ': 1700, 'ħ': 1500, h: 1500, v: 2500 };

/** Frame cost of assigning phone `p` to features `ft`. Lower is better. */
export function frameCost(p, ft) {
  const cls = classOf(p);
  switch (cls) {
    case 'vowel': return (1 - ft.v) * 2.5 + (1 - ft.e) * 2 + Math.max(0, ft.c - 2500) / 2000;
    case 'nasal': case 'liquid': case 'glide': case 'pharyngeal_app': return (1 - ft.v) * 2 + Math.abs(ft.e - 0.6) * 1.5 + Math.max(0, ft.c - 2200) / 2000;
    case 'vfric': return (1 - ft.v) * 0.8 + Math.max(0, (CENTROID_FRIC[p] || 3000) - ft.c) / 3000 + Math.abs(ft.e - 0.5);
    case 'ufric': return ft.v * 2 + Math.max(0, (CENTROID_FRIC[p] || 3000) - ft.c) / 3000 + Math.abs(ft.e - 0.45) * 0.8;
    case 'ustop': return ft.e * 2.2 + ft.v * 1.2;
    case 'vstop': return ft.e * 1.8 + (1 - ft.v) * 0.4;
    default: return 1;
  }
}

/** Segmental DP: align the expected phone sequence to frames. Returns [{p, start, end}] in frames. */
export function alignPhones(phones, feats) {
  const T = feats.length, N = phones.length;
  if (!T || !N) return [];
  const minD = phones.map(p => VOWELS.has(p) ? 3 : 2);
  const maxD = phones.map(p => VOWELS.has(p) ? (p.length === 2 ? 45 : 28) : (classOf(p) === 'ufric' ? 40 : 30));
  // prefix sums of per-phone frame costs
  const pre = phones.map(p => { const s = new Float64Array(T + 1); for (let t = 0; t < T; t++) s[t + 1] = s[t] + frameCost(p, feats[t]); return s; });
  const best = Array.from({ length: N }, () => new Float64Array(T + 1).fill(Infinity));
  const back = Array.from({ length: N }, () => new Int32Array(T + 1).fill(-1));
  for (let t = minD[0]; t <= Math.min(T, maxD[0]); t++) { best[0][t] = pre[0][t]; back[0][t] = 0; }
  for (let i = 1; i < N; i++) {
    for (let t = 1; t <= T; t++) {
      let b = Infinity, bs = -1;
      for (let d = minD[i]; d <= maxD[i] && d <= t; d++) {
        const s = t - d; const prev = best[i - 1][s];
        if (prev === Infinity) continue;
        const c = prev + pre[i][t] - pre[i][s];
        if (c < b) { b = c; bs = s; }
      }
      best[i][t] = b; back[i][t] = bs;
    }
  }
  // end: allow trailing frames to be absorbed by the last phone up to maxD, else pick the best end
  let endT = T, bestEnd = Infinity;
  for (let t = Math.max(1, T - 10); t <= T; t++) if (best[N - 1][t] < bestEnd) { bestEnd = best[N - 1][t]; endT = t; }
  if (bestEnd === Infinity) { // fall back to proportional split
    const per = T / N; return phones.map((p, i) => ({ p, start: Math.round(i * per), end: Math.round((i + 1) * per) }));
  }
  const out = []; let t = endT;
  for (let i = N - 1; i >= 0; i--) { const s = back[i][t]; out.unshift({ p: phones[i], start: s, end: t }); t = s; }
  return out;
}

export function trimSilence(x, marginMs = 40) {
  const chunks = splitOnSilence(x, { minSilenceMs: 150 });
  if (!chunks.length) return x;
  const margin = Math.round(marginMs * SR / 1000);
  const start = Math.max(0, chunks[0].start - margin), end = Math.min(x.length, chunks[chunks.length - 1].end + margin);
  return x.subarray(start, end);
}

/** Enroll one recorded item (vocalized text + samples). Returns units and analysis data. */
export function enrollItem({ text, mode = 'fusha', samples }) {
  const x = trimSilence(samples);
  const plan = phonemize(text, { mode }).phones.filter(p => p.p !== '_');
  const expected = plan.map(p => p.p);
  const feats = features(x);
  const ali = alignPhones(expected, feats);
  const { f0 } = trackPitch(x);
  const units = ali.map((a, i) => {
    const s = a.start * FRAME, e = Math.min(x.length, a.end * FRAME + 320);
    const seg = x.slice(s, e);
    const f0seg = f0.subarray(a.start, Math.min(f0.length, a.end));
    const voiced = Array.from(f0seg).filter(v => v > 0);
    const f0mean = voiced.length ? voiced.reduce((p, q) => p + q, 0) / voiced.length : 0;
    const marks = pitchMarks(seg, f0seg);
    return { p: a.p, cls: classOf(a.p), prev: expected[i - 1] || '#', next: expected[i + 1] || '#', samples: seg, f0mean, marks, durMs: Math.round(seg.length / SR * 1000) };
  });
  // formant estimate from the middle of every short /a/ vowel
  const formants = [];
  ali.forEach(a => {
    if ((a.p === 'a' || a.p === 'aː') && a.end - a.start >= 5) {
      const mid = Math.round((a.start + a.end) / 2) * FRAME - 320; const fr = x.subarray(Math.max(0, mid), Math.max(0, mid) + 640);
      if (fr.length === 640) { const peak = lpcPeaks(fr).find(f => f >= 500 && f <= 1600); if (peak) formants.push(peak); }
    }
  });
  const f0s = Array.from(f0).filter(v => v > 0);
  return { units, f0s, formants, alignment: ali, frames: feats.length, phones: expected, durationMs: Math.round(x.length / SR * 1000) };
}

function median(arr) { if (!arr.length) return 0; const s = [...arr].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; }
function quantile(arr, q) { if (!arr.length) return 0; const s = [...arr].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; }

/** Build a voice (profile + unit inventory) from enrolled items. */
export function buildVoice(items, { name = 'صوتي' } = {}) {
  const units = [], f0s = [], formants = []; let phonesTotal = 0, msTotal = 0;
  for (const it of items) { units.push(...it.units); f0s.push(...it.f0s); formants.push(...it.formants); phonesTotal += it.phones.length; msTotal += it.durationMs; }
  const f0Base = median(f0s) || 120;
  const f0Range = f0s.length ? Math.min(2, Math.max(0.5, (quantile(f0s, 0.85) - quantile(f0s, 0.15)) / f0Base / 0.5)) : 1;
  let formantScale = 1;
  if (formants.length) formantScale = Math.min(1.35, Math.max(0.75, median(formants) / A_PEAK_REFERENCE));
  const rate = msTotal ? Math.min(1.4, Math.max(0.7, (phonesTotal / (msTotal / 1000)) / 8)) : 1;
  const covered = new Set(units.map(u => u.p));
  return {
    profile: { name, f0Base: Math.round(f0Base), f0Range: +f0Range.toFixed(2), formantScale: +formantScale.toFixed(3), rate: +rate.toFixed(2), breathiness: 0.08, unitCount: units.length, phonesCovered: [...covered].sort(), createdAt: new Date().toISOString() },
    units,
  };
}

// ---- serialization (units as base64 Int16) ----
export function serializeVoice(voice) {
  const units = voice.units.map(u => {
    const i16 = new Int16Array(u.samples.length); for (let i = 0; i < i16.length; i++) i16[i] = Math.max(-32768, Math.min(32767, Math.round(u.samples[i] * 32767)));
    const bytes = new Uint8Array(i16.buffer);
    let bin = ''; for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    const b64 = typeof btoa === 'function' ? btoa(bin) : Buffer.from(bin, 'binary').toString('base64');
    return { p: u.p, cls: u.cls, prev: u.prev, next: u.next, f0mean: Math.round(u.f0mean), marks: u.marks.map(m => [m.pos, m.period, m.voiced ? 1 : 0]), durMs: u.durMs, pcm: b64 };
  });
  return JSON.stringify({ format: 'arabic-tts-voice/1', profile: voice.profile, units });
}

export function deserializeVoice(json) {
  const d = typeof json === 'string' ? JSON.parse(json) : json;
  const units = (d.units || []).map(u => {
    const bin = typeof atob === 'function' ? atob(u.pcm) : Buffer.from(u.pcm, 'base64').toString('binary');
    const bytes = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const i16 = new Int16Array(bytes.buffer); const samples = new Float32Array(i16.length); for (let i = 0; i < i16.length; i++) samples[i] = i16[i] / 32767;
    return { ...u, samples, marks: u.marks.map(m => ({ pos: m[0], period: m[1], voiced: !!m[2] })) };
  });
  return { profile: d.profile, units };
}

/** Split one long recording of the whole script into items, in script order. */
export function splitRecording(samples, script) {
  const chunks = splitOnSilence(samples, { minSilenceMs: 350 });
  if (chunks.length !== script.length) return { ok: false, found: chunks.length, expected: script.length, chunks };
  return { ok: true, items: script.map((s, i) => ({ ...s, samples: samples.subarray(chunks[i].start, chunks[i].end) })) };
}
