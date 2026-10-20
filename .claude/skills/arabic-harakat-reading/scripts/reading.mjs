// Deterministic reader for fully vocalized Arabic.
// Converts tashkeel-bearing text into a phonetic reading (Latin transliteration or IPA),
// applying connected-speech rules (wasl) and pause rules (waqf).
// No dependencies. Works in Node and in the browser (the artifact inlines this file).

const LATIN = {
  'ء': 'ʾ', 'أ': 'ʾ', 'إ': 'ʾ', 'ؤ': 'ʾ', 'ئ': 'ʾ',
  'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'ḥ', 'خ': 'kh', 'د': 'd', 'ذ': 'dh',
  'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh', 'ص': 'ṣ', 'ض': 'ḍ', 'ط': 'ṭ', 'ظ': 'ẓ',
  'ع': 'ʿ', 'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
  'ه': 'h', 'و': 'w', 'ي': 'y', 'ة': 't', 'پ': 'p', 'چ': 'ch', 'ڤ': 'v', 'گ': 'g',
};
const IPA = {
  'ء': 'ʔ', 'أ': 'ʔ', 'إ': 'ʔ', 'ؤ': 'ʔ', 'ئ': 'ʔ',
  'ب': 'b', 'ت': 't', 'ث': 'θ', 'ج': 'dʒ', 'ح': 'ħ', 'خ': 'x', 'د': 'd', 'ذ': 'ð',
  'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'ʃ', 'ص': 'sˤ', 'ض': 'dˤ', 'ط': 'tˤ', 'ظ': 'ðˤ',
  'ع': 'ʕ', 'غ': 'ɣ', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
  'ه': 'h', 'و': 'w', 'ي': 'j', 'ة': 't', 'پ': 'p', 'چ': 'tʃ', 'ڤ': 'v', 'گ': 'g',
};
const VOWELS = {
  latin: { a: 'a', u: 'u', i: 'i', aa: 'ā', uu: 'ū', ii: 'ī' },
  ipa: { a: 'a', u: 'u', i: 'i', aa: 'aː', uu: 'uː', ii: 'iː' },
};

// Saudi white dialect: words that keep /q/ even though the dialect reads qaf as /g/
const QAF_KEEP = new Set(['قرآن', 'القرآن', 'قانون', 'القانون', 'قوانين', 'القوانين', 'قانوني', 'قانونية', 'القدس', 'القيامة', 'مقدس', 'المقدس', 'القاهرة', 'قاضي', 'القاضي']);
const LONG_E = { latin: 'ē', ipa: 'eː' };
const LONG_O = { latin: 'ō', ipa: 'oː' };
const HAMZA_LETTERS = new Set('ءأإؤئ');

const FATHA = 'َ', DAMMA = 'ُ', KASRA = 'ِ', SUKUN = 'ْ', SHADDA = 'ّ';
const FATHATAN = 'ً', DAMMATAN = 'ٌ', KASRATAN = 'ٍ', MADDA = 'ٓ', DAGGER = 'ٰ';
const MARKS = new Set([FATHA, DAMMA, KASRA, SUKUN, SHADDA, FATHATAN, DAMMATAN, KASRATAN, MADDA, DAGGER, 'ٔ', 'ٕ', 'ٖ']);
const TATWEEL = 'ـ';
const SUN = new Set('تثدذرزسشصضطظلن');
const SHORT = { [FATHA]: 'a', [DAMMA]: 'u', [KASRA]: 'i' };
const TANWEEN = { [FATHATAN]: 'an', [DAMMATAN]: 'un', [KASRATAN]: 'in' };
const ARABIC_LETTER = /[ء-غف-يٱٹ-ۓ]/;
const PUNCT_END = /[.!?؟،,;؛:…»"”)\]]+$/;

// Words whose standard spelling omits a long alif (read with a dagger alif) or carries a silent letter.
// key: bare skeleton (no marks). dagger: index of the letter that takes ā. silent: index of a letter not read.
const EXCEPTIONS = {
  'هذا': { dagger: 0 }, 'هذه': { dagger: 0 }, 'هذان': { dagger: 0 }, 'هذين': { dagger: 0 }, 'هؤلاء': { dagger: 0 },
  'ذلك': { dagger: 0 }, 'ذلكم': { dagger: 0 }, 'لكن': { dagger: 0 }, 'لكنه': { dagger: 0 }, 'لكنها': { dagger: 0 }, 'لكنهم': { dagger: 0 },
  'الله': { dagger: 2 }, 'اللهم': { dagger: 2 }, 'اله': { dagger: 1 }, 'الهم': { dagger: 1 }, 'الرحمن': { dagger: 4 }, 'أولئك': { dagger: 2, silent: 1 }, 'طه': { dagger: 0 },
  'عمرو': { silent: 3 }, 'مائة': { silent: 1 }, 'مائتان': { silent: 1 }, 'مائتين': { silent: 1 },
};
const PREFIXES = ['و', 'ف', 'ب', 'ل', 'ك', 'وب', 'ول', 'فب', 'فل'];

function applyExceptions(units) {
  const letters = units.map(u => u.ch);
  const skeleton = letters.join('');
  const tryKey = (key, offset) => {
    const ex = EXCEPTIONS[key];
    if (!ex) return false;
    if (ex.dagger !== undefined) {
      const u = units[offset + ex.dagger];
      if (u && !u.marks.includes(DAGGER)) u.marks.push(DAGGER);
    }
    if (ex.silent !== undefined) { const u = units[offset + ex.silent]; if (u) u.silent = true; }
    return true;
  };
  if (tryKey(skeleton, 0)) return;
  for (const p of PREFIXES) if (skeleton.startsWith(p) && tryKey(skeleton.slice(p.length), p.length)) return;
}

/** Split a word into [{ch, marks:[]}] units; marks attach to the preceding letter. */
export function segment(word) {
  const units = [];
  for (const ch of word.normalize('NFC')) {
    if (ch === TATWEEL) continue;
    if (MARKS.has(ch)) {
      if (units.length) units[units.length - 1].marks.push(ch);
      continue;
    }
    units.push({ ch, marks: [] });
  }
  return units;
}

/** لِلْكِتَابِ، وَلِلطَّالِبِ: the article's alif is dropped after the preposition lam; restore it for reading. */
function restoreArticleAlif(units) {
  for (const k of [0, 1]) {
    const a = units[k], b = units[k + 1];
    if (!a || !b || !units[k + 2]) continue;
    if (k === 1 && !('وف'.includes(units[0].ch) && units[0].marks.some(m => SHORT[m]))) continue;
    if (a.ch === 'ل' && a.marks.some(m => SHORT[m]) && b.ch === 'ل' && (b.marks.includes(SHADDA) || !b.marks.some(m => SHORT[m] || TANWEEN[m]))) {
      units.splice(k + 1, 0, { ch: 'ا', marks: [] });
      return;
    }
  }
}

/** Report letters that lack a required mark. Returns [] when the word is fully vocalized. */
export function checkCompleteness(word, { dialect = 'fusha' } = {}) {
  const units = segment(word);
  restoreArticleAlif(units);
  applyExceptions(units);
  const problems = [];
  let prevVowel = null; // short vowel carried into the next unit
  for (let i = 0; i < units.length; i++) {
    const u = units[i];
    const isLetter = ARABIC_LETTER.test(u.ch);
    if (!isLetter) { prevVowel = null; continue; }
    if (u.silent) { continue; }
    const marks = u.marks;
    const hasVowel = marks.some(m => SHORT[m] || TANWEEN[m]);
    const hasSukun = marks.includes(SUKUN);
    const hasShadda = marks.includes(SHADDA);
    const isLast = i === units.length - 1;
    const next = units[i + 1];
    if (u.ch === 'ا' || u.ch === 'ى' || u.ch === 'ٱ') { prevVowel = null; continue; }
    if (u.ch === 'آ') { prevVowel = 'a'; continue; }
    // ال article: alif bare, lam may be bare when followed by shadda (sun letter)
    if (u.ch === 'ل' && !marks.length && i > 0 && units[i - 1].ch === 'ا' && units[i - 1].marks.length === 0 && next && next.marks.includes(SHADDA)) { continue; }
    if (u.ch === 'و' && prevVowel === 'u' && !marks.length) { prevVowel = 'uu'; continue; }
    if (u.ch === 'ي' && prevVowel === 'i' && !marks.length) { prevVowel = 'ii'; continue; }
    if (!hasVowel && !hasSukun) {
      // shadda alone (no vowel) on the final letter is acceptable as a pausal form; a bare final ة is the Saudi convention
      const saudiTa = dialect === 'saudi' && u.ch === 'ة' && isLast;
      if (!(hasShadda && isLast) && !saudiTa) problems.push({ index: i, letter: u.ch, issue: 'لا حركة ولا سكون' });
    }
    prevVowel = marks.find(m => SHORT[m]) ? SHORT[marks.find(m => SHORT[m])] : null;
  }
  return problems;
}

/** Read one word. `atPause` applies waqf rules; `afterVowel` elides hamzat wasl. */
export function readWord(word, { atPause = false, afterVowel = false, scheme = 'latin', dialect = 'fusha' } = {}) {
  const saudi = dialect === 'saudi';
  let C = scheme === 'ipa' ? IPA : LATIN;
  const V = VOWELS[scheme] || VOWELS.latin;
  const units = segment(word);
  if (saudi) {
    const skeleton = units.map(u => u.ch).join('');
    const keepQ = QAF_KEEP.has(skeleton) || PREFIXES.some(p => skeleton.startsWith(p) && QAF_KEEP.has(skeleton.slice(p.length)));
    if (!keepQ) C = { ...C, 'ق': scheme === 'ipa' ? 'ɡ' : 'g' };
  }
  if (!units.some(u => ARABIC_LETTER.test(u.ch))) return { reading: word, elided: false, warnings: [] };
  restoreArticleAlif(units);
  applyExceptions(units);

  let out = '';
  let elided = false;
  const warnings = [];
  let prevVowel = null; // 'a' | 'u' | 'i' | 'aa' | 'uu' | 'ii' | null
  let emittedLetter = false;

  const lengthen = (v) => { // replace a just-emitted short vowel by its long form
    const short = V[v];
    if (out.endsWith(short)) out = out.slice(0, out.length - short.length);
    out += V[v + v];
    prevVowel = v + v;
  };
  const hamza = () => (scheme === 'latin' && !emittedLetter) ? '' : C['ء'];

  // Effective last letter: ignore a trailing bare alif / alif maqsura that only carries tanween fath (كِتَابًا، فَتًى)
  let lastLetterIndex = -1;
  for (let k = units.length - 1; k >= 0; k--) if (ARABIC_LETTER.test(units[k].ch)) { lastLetterIndex = k; break; }
  if (lastLetterIndex > 0) {
    const L = units[lastLetterIndex], P = units[lastLetterIndex - 1];
    if ((L.ch === 'ا' || L.ch === 'ى') && L.marks.length === 0 && P.marks.includes(FATHATAN)) lastLetterIndex -= 1;
  }

  // One-letter proclitic (وَ فَ بِ كَ لِ) before the article or a hamzat wasl: read it, then elide the alif
  let i = 0;
  let prefixOffset = 0;
  {
    // count proclitics: up to two (وَبِالْـ، فَلِلْـ), each a vowelled و ف ب ك ل, followed by a bare alif that opens
    // either the article (ا ل with bare/sukun/shadda lam) or a hamzat wasl (ا + letter with sukun)
    let k = 0;
    while (k < 2 && units[k] && 'وفبكل'.includes(units[k].ch) && units[k].marks.some(m => SHORT[m]) && units[k + 1]) {
      const a = units[k + 1];
      if ((a.ch === 'ا' || a.ch === 'ٱ') && a.marks.length === 0 && units[k + 2]) {
        const l = units[k + 2];
        const articleLike = l.ch === 'ل' && (l.marks.length === 0 || l.marks.includes(SUKUN) || l.marks.includes(SHADDA)) && units[k + 3];
        const waslLike = l.marks.includes(SUKUN) && units[k + 3];
        if (articleLike || waslLike) { k++; prefixOffset = k; }
        break;
      }
      if (k === 0 && 'بكل'.includes(a.ch) && a.marks.some(m => SHORT[m])) { k++; continue; }
      break;
    }
    for (let q = 0; q < prefixOffset; q++) {
      const pv = SHORT[units[q].marks.find(m => SHORT[m])];
      out += (C[units[q].ch] || units[q].ch) + V[pv] + '-';
    }
    if (prefixOffset) { afterVowel = true; emittedLetter = true; }
  }
  const first = units[prefixOffset];
  const second = units[prefixOffset + 1];
  const initialAlif = first && (first.ch === 'ا' || first.ch === 'ٱ') && !first.marks.some(m => TANWEEN[m]);
  const isArticle = initialAlif && second && second.ch === 'ل' && units.length > prefixOffset + 2
    && (second.marks.length === 0 || second.marks.includes(SUKUN) || second.marks.includes(SHADDA));
  const isWaslVerb = initialAlif && !isArticle && second && (second.marks.includes(SUKUN) || second.marks.length === 0) && units.length > prefixOffset + 2;

  if (isArticle) {
    if (!afterVowel) out += V.a; else if (!prefixOffset) elided = true;
    const lam = second, after = units[prefixOffset + 2];
    if (lam.marks.includes(SHADDA)) {
      // الَّذِي، اللَّهُ written with the shadda on the lam itself
      out += afterVowel ? 'l' : 'l-';
      lam.marks = lam.marks.filter(m => m !== SHADDA);
      i = prefixOffset + 1;
      emittedLetter = true;
    } else if (after && SUN.has(after.ch)) {
      // assimilation: the lam is replaced by a doubled sun letter
      out += (C[after.ch] || after.ch) + '-';
      after.marks = after.marks.filter(m => m !== SHADDA);
      i = prefixOffset + 2;
      emittedLetter = true;
    } else {
      out += 'l-';
      i = prefixOffset + 2;
      emittedLetter = false; // a stem-initial hamza after the article is not written in the Latin scheme (l-abu)
    }
    prevVowel = null;
  } else if (isWaslVerb) {
    if (!afterVowel) {
      const explicit = first.marks.find(m => SHORT[m]);
      let v = explicit ? SHORT[explicit] : 'i';
      // imperative of a triliteral verb whose third radical takes damma: اُكْتُبْ
      if (!explicit && units.length === 4 && units[2].marks.includes(DAMMA)) v = 'u';
      out += V[v];
      prevVowel = v;
    } else {
      elided = true;
      prevVowel = null;
    }
    emittedLetter = true;
    i = prefixOffset + 1;
  } else {
    i = prefixOffset;
  }

  for (; i < units.length; i++) {
    const u = units[i];
    const ch = u.ch;
    if (!ARABIC_LETTER.test(ch)) { out += ch; continue; }
    if (u.silent) { continue; }
    const marks = u.marks;
    const shadda = marks.includes(SHADDA);
    const sukun = marks.includes(SUKUN);
    const shortMark = marks.find(m => SHORT[m]);
    const tanweenMark = marks.find(m => TANWEEN[m]);
    const madda = marks.includes(MADDA);
    const dagger = marks.includes(DAGGER);
    const isLast = i === lastLetterIndex;
    const next = units[i + 1];

    // Vowel letters
    if (ch === 'ا' || ch === 'ٱ') {
      if (madda) { out += hamza() + V.aa; prevVowel = 'aa'; emittedLetter = true; continue; }
      if (prevVowel === 'a') { lengthen('a'); continue; }
      if (shortMark && prevVowel === null && i === 0) { out += V[SHORT[shortMark]]; prevVowel = SHORT[shortMark]; emittedLetter = true; continue; }
      continue; // alif fariqa after ū, alif of tanween fath, or otherwise silent
    }
    if (ch === 'آ') { out += hamza() + V.aa; prevVowel = 'aa'; emittedLetter = true; continue; }
    if (ch === 'ى') {
      if (prevVowel === 'a') { lengthen('a'); continue; }
      if (i > 0 && units[i - 1].marks.includes(FATHATAN)) { continue; }
      out += V.aa; prevVowel = 'aa'; emittedLetter = true; continue;
    }
    if (ch === 'و' && !marks.length && prevVowel === 'u') { lengthen('u'); continue; }
    if (ch === 'ي' && !marks.length && prevVowel === 'i') { lengthen('i'); continue; }
    if (ch === 'و' && !marks.length && prevVowel === 'uu' && isLast) { continue; } // عَمْرٌو style silent waw

    // Saudi white: diphthongs ـَيْ → ē and ـَوْ → ō
    if (saudi && (ch === 'و' || ch === 'ي') && sukun && !shadda && prevVowel === 'a' && out.endsWith(V.a)) {
      out = out.slice(0, out.length - V.a.length) + (ch === 'و' ? LONG_O[scheme] : LONG_E[scheme]);
      prevVowel = ch === 'و' ? 'oo' : 'ee';
      continue;
    }
    // Saudi white: a word-final hamza is not pronounced (سما، جا، شي)
    if (saudi && HAMZA_LETTERS.has(ch) && isLast) { prevVowel = null; continue; }

    // Consonants
    let base = C[ch] || ch;
    if (ch === 'ء' || ch === 'أ' || ch === 'إ' || ch === 'ؤ' || ch === 'ئ') base = hamza();
    if (saudi && ch === 'ئ' && prevVowel && shortMark) base = C['ي'];
    if (ch === 'ة') {
      if (saudi) base = (shortMark || sukun) ? 't' : '';   // مضافة → t، وإلا فالفتحة قبلها هي النطق
      else base = (atPause && isLast) ? 'h' : 't';
    }
    emittedLetter = true;

    if (isLast && atPause) {
      out += (shadda ? base : '') + base;
      if (ch !== 'ة' && tanweenMark === FATHATAN) { out += saudi ? V.a + 'n' : V.aa; prevVowel = saudi ? null : 'aa'; }
      else prevVowel = null;
      continue;
    }

    out += (shadda ? base : '') + base;
    if (dagger) { out += V.aa; prevVowel = 'aa'; }
    else if (shortMark) { out += V[SHORT[shortMark]]; prevVowel = SHORT[shortMark]; }
    else if (tanweenMark) { const t = TANWEEN[tanweenMark]; out += V[t[0]] + 'n'; prevVowel = null; }
    else if (sukun) { prevVowel = null; }
    else {
      if (!isLast) warnings.push(`حرف بلا حركة: ${ch} في «${word}»`);
      prevVowel = null;
    }
  }

  // Saudi white: a word-final ـِي / ـُو is short (تَبِي tabi، أَبُو abu); the alif fariqa form (رَاحُوا rāḥū) keeps its length
  if (saudi && lastLetterIndex >= 0) {
    const L = units[lastLetterIndex];
    if ((L.ch === 'ي' && out.endsWith(V.ii)) ) out = out.slice(0, out.length - V.ii.length) + V.i;
    else if (L.ch === 'و' && out.endsWith(V.uu)) out = out.slice(0, out.length - V.uu.length) + V.u;
    else if (L.ch === 'ى' && out.endsWith(V.aa)) out = out.slice(0, out.length - V.aa.length) + V.a;
  }
  return { reading: out, elided, warnings };
}

/** Read a full text. Pauses before punctuation and at the end when `pause` is true. */
export function readText(text, { pause = true, scheme = 'latin', dialect = 'fusha' } = {}) {
  const tokens = text.normalize('NFC').replace(/\s+/g, ' ').trim().split(' ');
  const parts = [];
  const warnings = [];
  let afterVowel = false;
  for (let t = 0; t < tokens.length; t++) {
    let tok = tokens[t];
    const m = tok.match(PUNCT_END);
    const punct = m ? m[0] : '';
    if (punct) tok = tok.slice(0, -punct.length);
    const lead = tok.match(/^[«"“(\[]+/);
    const leadStr = lead ? lead[0] : '';
    if (leadStr) tok = tok.slice(leadStr.length);
    if (!tok) { parts.push(leadStr + punct); afterVowel = false; continue; }
    const isLastTok = t === tokens.length - 1;
    const atPause = pause && (isLastTok || /[.!?؟،,;؛:…]/.test(punct));
    const r = readWord(tok, { atPause, afterVowel, scheme, dialect });
    warnings.push(...r.warnings);
    let piece = r.reading;
    if (r.elided && parts.length) {
      // join to the previous word: "fī l-madrasati"
      parts[parts.length - 1] = parts[parts.length - 1] + ' ' + piece;
      piece = null;
    }
    if (piece !== null) parts.push(leadStr + piece + punct); else parts[parts.length - 1] += punct;
    afterVowel = !atPause && /[aiuāīūēōː]$/.test(r.reading.replace(/[-'ʾʿ]+$/, ''));
  }
  // Fix doubled-consonant marker from sun-letter assimilation: "ṭ-ṭālibu" is desired, so nothing to do.
  return { reading: parts.join(' '), warnings };
}

/** Punctuation → pauses and sentence type. Returns segments the acoustic layer can time. */
const PAUSE_MS = { '،': 250, ',': 250, '؛': 400, ';': 400, ':': 400, '.': 600, '؟': 600, '?': 600, '!': 600, '…': 800, '—': 200 };
export function prosody(text) {
  const norm = text.normalize('NFC').replace(/\.{3}/g, '…').replace(/\s+/g, ' ').trim();
  const segments = [];
  const re = /([^،,؛;:.؟?!…—]+)([،,؛;:.؟?!…—]+)?/g;
  let m;
  while ((m = re.exec(norm)) !== null) {
    const body = m[1].trim();
    if (!body) continue;
    const punct = (m[2] || '').trim();
    const last = punct ? punct[punct.length - 1] : '';
    let type = 'continue';
    if (last === '؟' || last === '?') type = 'question';
    else if (last === '!') type = 'exclamation';
    else if (last === '.' || last === '…') type = 'statement';
    const pauseMs = punct ? Math.max(...[...punct].map(c => PAUSE_MS[c] || 0)) : 0;
    segments.push({ text: body, punct, pauseMs, type });
  }
  if (segments.length && !segments[segments.length - 1].punct) { segments[segments.length - 1].type = 'statement'; segments[segments.length - 1].pauseMs = PAUSE_MS['.']; }
  return segments;
}

/** Text ready for ElevenLabs. `family` 'v3' covers eleven_v3/eleven_v4 (punctuation only); 'v2' covers multilingual_v2/flash/turbo (<break> tags for long pauses). */
export function toTtsText(text, { family = 'v3' } = {}) {
  const segs = prosody(text);
  if (!segs.length) return '';
  const pieces = segs.map((sg, i) => {
    let p = sg.punct || (i === segs.length - 1 ? '.' : '');
    if (family === 'v2') {
      if (/…/.test(p)) p = p.replace(/…/g, '.') + ' <break time="0.8s" />';
      else if (/[؛;:]/.test(p)) p = p + ' <break time="0.4s" />';
    }
    return sg.text + p;
  });
  return pieces.join(' ').replace(/\s+/g, ' ').trim();
}

export function completenessReport(text, { dialect = 'fusha' } = {}) {
  const words = text.normalize('NFC').split(/\s+/).filter(Boolean);
  return words.map(w => ({ word: w, problems: checkCompleteness(w.replace(PUNCT_END, ''), { dialect }) })).filter(x => x.problems.length);
}

// CLI
const isMain = typeof process !== 'undefined' && process.argv && process.argv[1] && /reading\.mjs$/.test(process.argv[1]);
if (isMain) {
  const args = process.argv.slice(2);
  const scheme = args.includes('--ipa') ? 'ipa' : 'latin';
  const pause = !args.includes('--no-pause');
  const dialect = args.includes('--saudi') ? 'saudi' : 'fusha';
  const text = args.filter(a => !a.startsWith('--')).join(' ');
  if (!text) { console.error('usage: node reading.mjs [--ipa] [--no-pause] [--saudi] "نصّ مشكّل"'); process.exit(2); }
  const { reading, warnings } = readText(text, { pause, scheme, dialect });
  console.log(reading);
  const incomplete = completenessReport(text, { dialect });
  for (const w of warnings) console.error('تحذير: ' + w);
  for (const c of incomplete) console.error(`ناقص التشكيل: ${c.word} → ${c.problems.map(p => p.letter).join(' ')}`);
}
