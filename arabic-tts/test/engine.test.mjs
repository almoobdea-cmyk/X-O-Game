import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tokenizeIpa, phonemize } from '../src/phonemize.mjs';
import { synthesizeFormant, phoneBoundaries } from '../src/formant.mjs';
import { trackPitch, psola, pitchMarks, splitOnSilence, FRAME } from '../src/dsp.mjs';
import { decodeWav, encodeWav, SR } from '../src/wav.mjs';
import { enrollItem, buildVoice, serializeVoice, deserializeVoice, alignPhones, features } from '../src/voice.mjs';
import { synthesize, detectMode } from '../src/index.mjs';

test('IPA tokenizer handles multi-character symbols, geminates and word boundaries', () => {
  assert.deepEqual(tokenizeIpa('ðahaba tˤ-tˤaːlibu'), ['ð', 'a', 'h', 'a', 'b', 'a', ' ', 'tˤ', 'tˤ', 'aː', 'l', 'i', 'b', 'u']);
  assert.deepEqual(tokenizeIpa('dʒiːt aʃ-ʃams'), ['dʒ', 'iː', 't', ' ', 'a', 'ʃ', 'ʃ', 'a', 'm', 's']);
});

test('phonemize: gemination folds, long vowels, pauses and question contour', () => {
  const { phones, segments } = phonemize('الطَّالِبُ يَكْتُبُ، هَلْ رَأَيْتَهُ؟', { mode: 'fusha', f0Base: 120 });
  const tt = phones.find(p => p.p === 'tˤ'); assert.equal(tt.geminate, true);
  assert.ok(phones.some(p => p.p === 'aː' && p.long));
  const pauses = phones.filter(p => p.p === '_'); assert.equal(pauses.length, 2);
  assert.equal(pauses[0].dur, 250); assert.equal(pauses[1].dur, 600);
  assert.equal(segments[1].type, 'question');
  const q = phones.filter(p => p.segment === 1 && p.voiced);
  assert.ok(q[q.length - 1].f0 > q[0].f0, 'question ends higher than it starts');
  const s = phonemize('رَأَيْتُهُ.', { mode: 'fusha', f0Base: 120 }).phones.filter(p => p.voiced);
  assert.ok(s[s.length - 1].f0 < s[0].f0, 'statement ends lower');
});

test('phonemize: Saudi mode sounds (q→g, ay→ē, ta marbuta→a)', () => {
  const ph = phonemize('وَقْتْ بَيْتْ بُكْرَة', { mode: 'saudi' }).phones.map(p => p.p);
  assert.ok(ph.includes('g') && !ph.includes('q'));
  assert.ok(ph.includes('eː'));
  assert.equal(ph.filter(p => p !== '_').slice(-1)[0], 'a');
});

test('formant synthesizer renders the planned duration', () => {
  const { phones, totalMs } = phonemize('سَلَامٌ.', { mode: 'fusha' });
  const x = synthesizeFormant(phones, { f0Base: 120 });
  assert.ok(Math.abs(x.length - totalMs * SR / 1000) < SR * 0.05);
  let m = 0; for (const v of x) m = Math.max(m, Math.abs(v)); assert.ok(m > 0.5 && m <= 0.7001);
  assert.equal(phoneBoundaries(phones).length, phones.length);
});

test('pitch tracker recovers the f0 of a synthetic voiced vowel without octave errors', () => {
  for (const f0 of [95, 140, 210]) {
    const plan = [{ p: 'aː', cls: 'vowel', voiced: true, dur: 400, f0, long: true }];
    const x = synthesizeFormant(plan, { f0Base: f0 });
    const { f0: tr } = trackPitch(x);
    const v = Array.from(tr).filter(f => f > 0);
    assert.ok(v.length > 20, 'voiced frames found');
    const med = v.sort((a, b) => a - b)[Math.floor(v.length / 2)];
    assert.ok(Math.abs(med - f0) / f0 < 0.06, `f0 ${f0} tracked as ${med.toFixed(1)}`);
  }
});

test('PSOLA changes length and pitch of a voiced unit', () => {
  const plan = [{ p: 'aː', cls: 'vowel', voiced: true, dur: 300, f0: 120, long: true }];
  const x = synthesizeFormant(plan, { f0Base: 120 });
  const { f0 } = trackPitch(x);
  const marks = pitchMarks(x, f0);
  const target = new Float32Array(60).fill(180);
  const y = psola(x, marks, Math.round(x.length * 1.5), target);
  assert.equal(y.length, Math.round(x.length * 1.5));
  const v = Array.from(trackPitch(y).f0).filter(f => f > 0).sort((a, b) => a - b);
  const med = v[Math.floor(v.length / 2)];
  assert.ok(Math.abs(med - 180) / 180 < 0.08, `pitch shifted to ${med.toFixed(1)}`);
});

test('WAV encode/decode round trip and silence splitting', () => {
  const plan = phonemize('بَابَا', { mode: 'fusha' }).phones.filter(p => p.p !== '_');
  const x = synthesizeFormant(plan, { f0Base: 120 });
  const padded = new Float32Array(x.length * 2 + 16000); padded.set(x, 4000); padded.set(x, 4000 + x.length + 8000);
  const dec = decodeWav(encodeWav(padded));
  assert.equal(dec.samples.length, padded.length);
  assert.ok(Math.abs(dec.samples[5000] - padded[5000]) < 1e-3);
  assert.equal(splitOnSilence(dec.samples).length, 2);
});

test('alignment of a synthetic word places vowel boundaries near the truth', () => {
  const text = 'كِتَابٌ';
  const plan = phonemize(text, { mode: 'fusha' }).phones.filter(p => p.p !== '_');
  const x = synthesizeFormant(plan, { f0Base: 130 });
  const truth = phoneBoundaries(plan);
  const ali = alignPhones(plan.map(p => p.p), features(x));
  assert.equal(ali.length, plan.length);
  const total = ali[ali.length - 1].end;
  for (let i = 0; i < ali.length - 1; i++) {
    const got = ali[i].end * FRAME, want = truth[i].end;
    assert.ok(Math.abs(got - want) < 0.09 * SR, `${plan[i].p} boundary off by ${((got - want) / SR * 1000).toFixed(0)} ms`);
  }
});

test('enrollment builds a reusable voice whose profile tracks the recorded pitch', () => {
  const words = [['سَلَامٌ', 'fusha'], ['كِتَابٌ', 'fusha'], ['بُكْرَة', 'saudi'], ['يَوْمْ', 'saudi']];
  const items = words.map(([text, mode]) => {
    const plan = phonemize(text, { mode, f0Base: 170 }).phones.filter(p => p.p !== '_');
    const x = synthesizeFormant(plan, { f0Base: 170 });
    const padded = new Float32Array(x.length + 3200); padded.set(x, 1600);
    return enrollItem({ text, mode, samples: padded });
  });
  const voice = buildVoice(items, { name: 't' });
  assert.ok(Math.abs(voice.profile.f0Base - 170) < 15, `f0Base ${voice.profile.f0Base}`);
  assert.ok(voice.units.length >= 15);
  const v2 = deserializeVoice(serializeVoice(voice));
  assert.equal(v2.units.length, voice.units.length);
  const r = synthesize('سَلَامٌ يَا كِتَابٌ.', { mode: 'fusha', voice: v2 });
  assert.equal(r.engine, 'concat');
  assert.ok(r.samples.length > SR * 0.8);
  assert.ok(r.stats.unitCount > r.stats.fallbackCount);
});

test('mode detection', () => {
  assert.equal(detectMode('وش تبي تاكل اليوم'), 'saudi');
  assert.equal(detectMode('ذَهَبَ الطَّالِبُ إِلَى الْمَدْرَسَةِ صَبَاحًا'), 'fusha');
  assert.equal(synthesize('بَسْ خَلَاصْ.').mode, 'saudi');
});
