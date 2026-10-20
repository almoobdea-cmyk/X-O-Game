// Signal-processing primitives: framing, pitch tracking (YIN-style), spectral features, LPC formants, resonators, PSOLA.
import { SR } from './wav.mjs';

export const FRAME = 160;   // 10 ms hop at 16 kHz
export const WIN = 640;     // 40 ms analysis window

export function hann(n) { const w = new Float32Array(n); for (let i = 0; i < n; i++) w[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1)); return w; }

export function frameEnergyDb(x, hop = FRAME, win = 320) {
  const n = Math.max(0, Math.floor((x.length - win) / hop) + 1);
  const out = new Float32Array(n);
  for (let f = 0; f < n; f++) { let e = 0; const o = f * hop; for (let i = 0; i < win; i++) e += x[o + i] * x[o + i]; out[f] = 10 * Math.log10(e / win + 1e-10); }
  return out;
}

export function zeroCrossRate(x, hop = FRAME, win = 320) {
  const n = Math.max(0, Math.floor((x.length - win) / hop) + 1);
  const out = new Float32Array(n);
  for (let f = 0; f < n; f++) { let z = 0; const o = f * hop; for (let i = 1; i < win; i++) if ((x[o + i] >= 0) !== (x[o + i - 1] >= 0)) z++; out[f] = z / win; }
  return out;
}

/** YIN-style pitch per frame. Returns { f0: Float32Array (0 = unvoiced), voicing: Float32Array (0..1) }. */
export function trackPitch(x, { hop = FRAME, win = WIN, fmin = 60, fmax = 420, threshold = 0.12 } = {}) {
  const n = Math.max(0, Math.floor((x.length - win) / hop) + 1);
  const f0 = new Float32Array(n), voicing = new Float32Array(n);
  const tauMin = Math.floor(SR / fmax), tauMax = Math.ceil(SR / fmin);
  const half = Math.floor(win / 2);
  const d = new Float32Array(tauMax + 1), cmnd = new Float32Array(tauMax + 1);
  for (let f = 0; f < n; f++) {
    const o = f * hop;
    let energy = 0; for (let i = 0; i < win; i++) energy += x[o + i] * x[o + i];
    if (energy / win < 1e-6) { continue; }
    for (let tau = 1; tau <= tauMax; tau++) { let s = 0; for (let i = 0; i < half; i++) { const dd = x[o + i] - x[o + i + tau]; s += dd * dd; } d[tau] = s; }
    let run = 0; cmnd[0] = 1;
    for (let tau = 1; tau <= tauMax; tau++) { run += d[tau]; cmnd[tau] = d[tau] * tau / (run || 1e-9); }
    let best = -1;
    for (let tau = tauMin; tau <= tauMax; tau++) {
      if (cmnd[tau] < threshold) { while (tau + 1 <= tauMax && cmnd[tau + 1] < cmnd[tau]) tau++; best = tau; break; }
    }
    if (best < 0) { let m = 1e9; for (let tau = tauMin; tau <= tauMax; tau++) if (cmnd[tau] < m) { m = cmnd[tau]; best = tau; } if (m > 0.5) { voicing[f] = Math.max(0, 1 - m); continue; } }
    // octave check: a dip at half the true period can pass the threshold; prefer 2τ when it is clearly deeper
    if (2 * best <= tauMax && cmnd[2 * best] < 0.6 * cmnd[best]) best = 2 * best;
    // parabolic interpolation
    let t = best;
    if (best > tauMin && best < tauMax) { const a = cmnd[best - 1], b = cmnd[best], c = cmnd[best + 1]; const den = a - 2 * b + c; if (Math.abs(den) > 1e-9) t = best + 0.5 * (a - c) / den; }
    f0[f] = SR / t; voicing[f] = Math.max(0, Math.min(1, 1 - cmnd[best]));
  }
  // median smoothing (5 frames) to remove octave glitches
  const sm = new Float32Array(n);
  for (let i = 0; i < n; i++) { const w = []; for (let k = -2; k <= 2; k++) if (f0[i + k] > 0) w.push(f0[i + k]); if (f0[i] > 0 && w.length >= 3) { w.sort((a, b) => a - b); sm[i] = w[Math.floor(w.length / 2)]; } else sm[i] = f0[i]; }
  return { f0: sm, voicing };
}

// ---- FFT (radix-2) ----
export function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) { let bit = n >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit; if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; } }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let j = 0; j < len / 2; j++) {
        const ur = re[i + j], ui = im[i + j], vr = re[i + j + len / 2] * cr - im[i + j + len / 2] * ci, vi = re[i + j + len / 2] * ci + im[i + j + len / 2] * cr;
        re[i + j] = ur + vr; im[i + j] = ui + vi; re[i + j + len / 2] = ur - vr; im[i + j + len / 2] = ui - vi;
        const t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
      }
    }
  }
}

export function spectralCentroid(x, hop = FRAME, win = 512) {
  const n = Math.max(0, Math.floor((x.length - win) / hop) + 1);
  const out = new Float32Array(n), w = hann(win), re = new Float32Array(win), im = new Float32Array(win);
  for (let f = 0; f < n; f++) {
    const o = f * hop; for (let i = 0; i < win; i++) { re[i] = x[o + i] * w[i]; im[i] = 0; }
    fft(re, im);
    let num = 0, den = 0;
    for (let k = 1; k < win / 2; k++) { const m = Math.sqrt(re[k] * re[k] + im[k] * im[k]); num += m * k * SR / win; den += m; }
    out[f] = den > 1e-9 ? num / den : 0;
  }
  return out;
}

/** LPC via autocorrelation + Levinson-Durbin. Returns the predictor coefficients a[1..order] (a[0] = 1). */
export function lpc(frame, order = 14) {
  const n = frame.length, r = new Float64Array(order + 1);
  for (let k = 0; k <= order; k++) { let s = 0; for (let i = k; i < n; i++) s += frame[i] * frame[i - k]; r[k] = s; }
  if (r[0] < 1e-9) return null;
  const a = new Float64Array(order + 1); a[0] = 1; let err = r[0] * 1.0001;
  const tmp = new Float64Array(order + 1);
  for (let i = 1; i <= order; i++) {
    let acc = r[i]; for (let j = 1; j < i; j++) acc -= a[j] * r[i - j];
    const k = acc / err;
    for (let j = 0; j < i; j++) tmp[j] = a[j];
    for (let j = 1; j < i; j++) a[j] = tmp[j] - k * tmp[i - j];
    a[i] = k; err *= (1 - k * k); if (err <= 0) return null;
  }
  return a;
}

/** Spectral peaks of one voiced frame from the LPC envelope (Hz, ascending). Close formants such as F1/F2 of /a/ can merge into one peak;
 * callers use the first peak between 500 and 1600 Hz as a vocal-tract length proxy rather than as a true F1. */
export function lpcPeaks(frame, order = 16) {
  const pre = new Float32Array(frame.length); for (let i = 1; i < frame.length; i++) pre[i] = frame[i] - 0.97 * frame[i - 1];
  const w = hann(frame.length); for (let i = 0; i < frame.length; i++) pre[i] *= w[i];
  const a = lpc(pre, order); if (!a) return [];
  const bins = 512, env = new Float32Array(bins);
  for (let b = 0; b < bins; b++) {
    const wv = Math.PI * b / bins; let re = 0, im = 0;
    for (let k = 0; k <= order; k++) { re += a[k] * Math.cos(wv * k); im -= a[k] * Math.sin(wv * k); }
    env[b] = 1 / Math.sqrt(re * re + im * im + 1e-12);
  }
  const peaks = [];
  for (let b = 2; b < bins - 2; b++) if (env[b] > env[b - 1] && env[b] >= env[b + 1]) peaks.push(b * (SR / 2) / bins);
  return peaks;
}
/** Reference value of the /a/ peak proxy for this engine's own voice at formantScale 1 (measured on the synthesizer). */
export const A_PEAK_REFERENCE = 1063;

/** Estimate formants from one voiced frame by peak-picking the LPC envelope. Returns [F1, F2, F3] in Hz (or null). */
export function estimateFormants(frame, order = 14) {
  const pre = new Float32Array(frame.length); for (let i = 1; i < frame.length; i++) pre[i] = frame[i] - 0.97 * frame[i - 1];
  const w = hann(frame.length); for (let i = 0; i < frame.length; i++) pre[i] *= w[i];
  const a = lpc(pre, order); if (!a) return null;
  const bins = 512, env = new Float32Array(bins);
  for (let b = 0; b < bins; b++) {
    const wv = Math.PI * b / bins; let re = 0, im = 0;
    for (let k = 0; k <= order; k++) { re += a[k] * Math.cos(wv * k); im -= a[k] * Math.sin(wv * k); }
    env[b] = 1 / Math.sqrt(re * re + im * im + 1e-12);
  }
  const peaks = [];
  for (let b = 2; b < bins - 2; b++) if (env[b] > env[b - 1] && env[b] >= env[b + 1]) peaks.push({ f: b * (SR / 2) / bins, m: env[b] });
  const f1 = peaks.find(p => p.f >= 220 && p.f <= 1100);
  const f2 = peaks.find(p => p.f > (f1 ? f1.f + 150 : 800) && p.f <= 2800);
  const f3 = peaks.find(p => p.f > (f2 ? f2.f + 200 : 2000) && p.f <= 3800);
  if (!f1 || !f2) return null;
  return [f1.f, f2.f, f3 ? f3.f : 2700];
}

/** Second-order digital resonator (Klatt). Returns a filter function processing one sample. */
export function resonator(f, bw, sr = SR) {
  const c = -Math.exp(-2 * Math.PI * bw / sr), b = 2 * Math.exp(-Math.PI * bw / sr) * Math.cos(2 * Math.PI * f / sr), a = 1 - b - c;
  let y1 = 0, y2 = 0;
  const fn = (x) => { const y = a * x + b * y1 + c * y2; y2 = y1; y1 = y; return y; };
  fn.set = (nf, nbw) => { const nc = -Math.exp(-2 * Math.PI * nbw / sr), nb = 2 * Math.exp(-Math.PI * nbw / sr) * Math.cos(2 * Math.PI * nf / sr); fn.a = 1 - nb - nc; fn.b = nb; fn.c = nc; };
  fn.a = a; fn.b = b; fn.c = c;
  fn.run = (x) => { const y = fn.a * x + fn.b * y1 + fn.c * y2; y2 = y1; y1 = y; return y; };
  return fn;
}

/** Pitch marks for a voiced signal from a per-frame f0 track: one mark per period, aligned to local peaks. */
export function pitchMarks(x, f0, hop = FRAME, defaultPeriod = 133) {
  const marks = [];
  let t = 0;
  while (t < x.length) {
    const f = f0[Math.min(f0.length - 1, Math.floor(t / hop))] || 0;
    const period = f > 0 ? Math.round(SR / f) : defaultPeriod;
    // snap to the local maximum within ±period/4
    let best = t, bv = -Infinity; const r = Math.floor(period / 4);
    for (let k = Math.max(0, t - r); k < Math.min(x.length, t + r); k++) if (x[k] > bv) { bv = x[k]; best = k; }
    marks.push({ pos: best, period, voiced: f > 0 });
    t = best + period;
  }
  return marks;
}

/** TD-PSOLA: resynthesize `x` (with analysis pitch marks) at a new length and a target f0 contour (Hz per output frame; 0 = keep). */
export function psola(x, marks, outLength, targetF0 = null, hop = FRAME) {
  const out = new Float32Array(Math.max(1, outLength));
  const inLen = x.length, scale = inLen / Math.max(1, outLength);
  if (!marks.length) return out;
  let t = 0, mi = 0;
  while (t < outLength) {
    const tin = t * scale;
    while (mi + 1 < marks.length && Math.abs(marks[mi + 1].pos - tin) < Math.abs(marks[mi].pos - tin)) mi++;
    const m = marks[mi];
    const tf = targetF0 ? targetF0[Math.min(targetF0.length - 1, Math.floor(t / hop))] : 0;
    const period = (m.voiced && tf > 0) ? Math.round(SR / tf) : m.period;
    const win = 2 * m.period;
    for (let k = -m.period; k < m.period; k++) {
      const src = m.pos + k, dst = t + k;
      if (src < 0 || src >= inLen || dst < 0 || dst >= outLength) continue;
      const w = 0.5 - 0.5 * Math.cos(Math.PI * (k + m.period) / win * 2);
      out[dst] += x[src] * w;
    }
    t += Math.max(16, period);
  }
  return out;
}

export function crossfadeConcat(parts, fadeSamples = 80) {
  let total = 0; for (const p of parts) total += p.length;
  const out = new Float32Array(total); let pos = 0;
  for (const p of parts) {
    for (let i = 0; i < p.length; i++) {
      const dst = pos + i;
      if (i < fadeSamples && pos > 0 && dst < out.length) { const a = i / fadeSamples; out[dst] = out[dst] * (1 - a) + p[i] * a; }
      else out[dst] = p[i];
    }
    pos += p.length - Math.min(fadeSamples, p.length);
  }
  return out.subarray(0, pos + fadeSamples);
}

/** Split a recording into chunks separated by silence. Returns [{start, end}] in samples. */
export function splitOnSilence(x, { minSilenceMs = 250, thresholdDb = -38, minChunkMs = 120 } = {}) {
  const e = frameEnergyDb(x, FRAME, 320);
  let maxE = -100; for (const v of e) maxE = Math.max(maxE, v);
  const thr = Math.max(thresholdDb, maxE - 35);
  const minSil = Math.round(minSilenceMs / 10), minChunk = Math.round(minChunkMs / 10);
  const chunks = []; let inChunk = false, start = 0, sil = 0;
  for (let f = 0; f < e.length; f++) {
    const loud = e[f] > thr;
    if (!inChunk && loud) { inChunk = true; start = Math.max(0, f - 2); sil = 0; }
    else if (inChunk) {
      if (loud) sil = 0; else { sil++; if (sil >= minSil) { const end = f - sil + 2; if (end - start >= minChunk) chunks.push({ start: start * FRAME, end: Math.min(x.length, end * FRAME) }); inChunk = false; } }
    }
  }
  if (inChunk) chunks.push({ start: start * FRAME, end: x.length });
  return chunks;
}
