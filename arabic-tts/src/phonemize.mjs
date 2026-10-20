// Text → phones with durations and an F0 contour. Uses the skill's reading engine for the pronunciation rules
// (tashkeel, wasl, waqf, sun-letter assimilation, dialect sounds) and adds the acoustic plan.
import { readText, prosody } from '../../.claude/skills/arabic-harakat-reading/scripts/reading.mjs';

const SYMBOLS = ['dʒ', 'tʃ', 'tˤ', 'dˤ', 'sˤ', 'ðˤ', 'aː', 'iː', 'uː', 'eː', 'oː',
  'ʔ', 'b', 't', 'θ', 'ħ', 'x', 'd', 'ð', 'r', 'z', 's', 'ʃ', 'ʕ', 'ɣ', 'f', 'q', 'k', 'g', 'ɡ', 'l', 'm', 'n', 'h', 'w', 'j', 'a', 'i', 'u', 'p', 'v', 'e', 'o'];

export const VOWELS = new Set(['a', 'i', 'u', 'e', 'o', 'aː', 'iː', 'uː', 'eː', 'oː']);
export const EMPHATIC = new Set(['tˤ', 'dˤ', 'sˤ', 'ðˤ', 'q']);
export const CLASS = {
  vowel: new Set(['a', 'i', 'u', 'e', 'o', 'aː', 'iː', 'uː', 'eː', 'oː']),
  nasal: new Set(['m', 'n']), liquid: new Set(['l', 'r']), glide: new Set(['w', 'j']), pharyngeal_app: new Set(['ʕ']),
  vfric: new Set(['z', 'ð', 'ðˤ', 'ɣ', 'v']), ufric: new Set(['f', 'θ', 's', 'sˤ', 'ʃ', 'x', 'ħ', 'h']),
  vstop: new Set(['b', 'd', 'dˤ', 'g', 'ɡ', 'dʒ']), ustop: new Set(['t', 'tˤ', 'k', 'q', 'ʔ', 'p', 'tʃ']),
};
export function classOf(p) { for (const [k, s] of Object.entries(CLASS)) if (s.has(p)) return k; return 'other'; }
export const isVoiced = (p) => !(CLASS.ufric.has(p) || CLASS.ustop.has(p));

/** Base durations in ms by phone (before gemination, lengthening and rate). */
const DUR = { vowel: 75, long: 150, nasal: 65, liquid: 55, glide: 60, pharyngeal_app: 80, vfric: 85, ufric: 100, vstop: 70, ustop: 80, other: 70 };

export function tokenizeIpa(s) {
  const phones = [];
  const str = s.replace(/-/g, '');
  let i = 0;
  while (i < str.length) {
    if (str[i] === ' ') { phones.push(' '); i++; continue; }
    let hit = null;
    for (const sym of SYMBOLS) if (str.startsWith(sym, i)) { hit = sym; break; }
    if (!hit) { i++; continue; } // punctuation or unknown glyph: skip
    phones.push(hit === 'ɡ' ? 'g' : hit);
    i += hit.length;
  }
  return phones;
}

/**
 * Build the acoustic plan for vocalized Arabic text.
 * Returns { phones: [{p, dur, f0, voiced, geminate, emphatic, wordStart, wordEnd, segment}], segments, totalMs }.
 */
export function phonemize(text, { mode = 'fusha', f0Base = 120, f0Range = 1.0, rate = 1.0 } = {}) {
  const dialect = mode === 'saudi' ? 'saudi' : 'fusha';
  const segments = prosody(text);
  const plan = [];
  segments.forEach((sg, si) => {
    const ipa = readText(sg.text, { pause: true, scheme: 'ipa', dialect }).reading;
    const toks = tokenizeIpa(ipa);
    // words → phones with gemination folded
    const words = []; let cur = [];
    for (const t of toks) { if (t === ' ') { if (cur.length) words.push(cur); cur = []; } else cur.push(t); }
    if (cur.length) words.push(cur);
    const segPhones = [];
    words.forEach((w, wi) => {
      for (let k = 0; k < w.length; k++) {
        const p = w[k];
        if (k > 0 && w[k - 1] === p && !VOWELS.has(p)) { segPhones[segPhones.length - 1].geminate = true; continue; }
        const cls = classOf(p);
        const long = VOWELS.has(p) && p.length === 2;
        segPhones.push({ p, cls, voiced: isVoiced(p), geminate: false, long, wordStart: k === 0, wordEnd: k === w.length - 1, word: wi, segment: si });
      }
    });
    // emphatic spreading: vowels adjacent to an emphatic consonant get the emphatic colour
    for (let k = 0; k < segPhones.length; k++) {
      const ph = segPhones[k];
      if (VOWELS.has(ph.p)) ph.emphatic = EMPHATIC.has(segPhones[k - 1]?.p) || EMPHATIC.has(segPhones[k + 1]?.p);
    }
    // durations
    const n = segPhones.length;
    segPhones.forEach((ph, k) => {
      let d = VOWELS.has(ph.p) ? (ph.long ? DUR.long : DUR.vowel) : DUR[ph.cls];
      if (ph.geminate) d *= 1.8;
      if (ph.wordEnd && VOWELS.has(ph.p)) d *= 1.15;
      if (k >= n - 2) d *= 1.3; // phrase-final lengthening
      ph.dur = Math.round(d / rate);
    });
    // F0 contour: declination over the segment, type-specific ending
    let acc = 0; const segMs = segPhones.reduce((s, p) => s + p.dur, 0) || 1;
    segPhones.forEach(ph => {
      const pos = acc / segMs; acc += ph.dur;
      let f = f0Base * (1.12 - (sg.type === 'question' ? 0.08 : 0.18) * pos);
      if (sg.type === 'question') f *= 1 + 0.6 * Math.max(0, (pos - 0.55) / 0.45);   // rise over the last 45%
      else if (sg.type === 'exclamation') f *= 1.12;
      else if (sg.type === 'statement' && pos > 0.7) f *= 1 - 0.2 * (pos - 0.7) / 0.3; // final fall
      if (ph.geminate || ph.long) f *= 1.03; // slight prominence
      f = f0Base + (f - f0Base) * f0Range;
      ph.f0 = ph.voiced ? f : 0;
    });
    plan.push(...segPhones);
    if (sg.pauseMs) plan.push({ p: '_', cls: 'pause', dur: Math.round(sg.pauseMs / rate), f0: 0, voiced: false, segment: si });
  });
  const totalMs = plan.reduce((s, p) => s + p.dur, 0);
  return { phones: plan, segments, totalMs };
}
