// Nataq (ناطق): a self-contained Arabic text-to-voice engine. Fusha and Saudi white dialect, voice enrollment and reuse.
// No external model or service is used at runtime.
import { phonemize } from './phonemize.mjs';
import { synthesizeFormant } from './formant.mjs';
import { synthesizeConcat } from './concat.mjs';
import { enrollItem, buildVoice, serializeVoice, deserializeVoice, splitRecording } from './voice.mjs';
import { decodeWav, encodeWav, SR } from './wav.mjs';
import { detectMode } from './mode.mjs';

export const DEFAULT_PROFILE = { name: 'الصوت الافتراضي', f0Base: 118, f0Range: 1.0, formantScale: 1.0, rate: 1.0, breathiness: 0.08 };

/**
 * Synthesize vocalized Arabic text.
 * @param text fully vocalized text (fusha or Saudi convention)
 * @param opts { mode: 'auto'|'fusha'|'saudi', voice: {profile, units} | null, profile overrides }
 * @returns { samples: Float32Array (16 kHz), plan, mode, engine: 'formant'|'concat', stats }
 */
export function synthesize(text, opts = {}) {
  const mode = !opts.mode || opts.mode === 'auto' ? detectMode(text) : opts.mode;
  const voice = opts.voice || null;
  const profile = { ...DEFAULT_PROFILE, ...(voice?.profile || {}), ...(opts.profile || {}) };
  const plan = phonemize(text, { mode, f0Base: profile.f0Base, f0Range: profile.f0Range, rate: profile.rate });
  if (voice && voice.units && voice.units.length) {
    const r = synthesizeConcat(plan.phones, { profile, units: voice.units });
    return { samples: r.samples, plan, mode, engine: 'concat', stats: { fallbackCount: r.fallbackCount, unitCount: r.unitCount, durationMs: Math.round(r.samples.length / SR * 1000) } };
  }
  const samples = synthesizeFormant(plan.phones, profile);
  return { samples, plan, mode, engine: 'formant', stats: { durationMs: Math.round(samples.length / SR * 1000) } };
}

export { phonemize, synthesizeFormant, synthesizeConcat, enrollItem, buildVoice, serializeVoice, deserializeVoice, splitRecording, decodeWav, encodeWav, detectMode, SR };
