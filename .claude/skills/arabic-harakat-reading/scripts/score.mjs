// Score predicted tashkeel against the gold test set, word by word.
// usage: node score.mjs predictions.json   (file: {"predictions": ["...", "..."]} in testset order)
//        or import { scoreAll } and call programmatically.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const MARK_RE = /[ً-ْٰٓ]/g;

export function normalizeWord(w) {
  return w.normalize('NFC').replace(/ـ/g, '').replace(/[.!?؟،,;؛:…«»"”“()\[\]]/g, '')
    // canonical mark order: shadda first, then vowel/tanween
    .replace(/([ً-ِ])ّ/g, 'ّ$1');
}

export function stripMarks(w) { return w.replace(MARK_RE, ''); }

/** Compare one sentence. Returns {total, correct, mismatches:[{gold, pred}]}. */
export function scoreSentence(gold, pred) {
  const g = gold.trim().split(/\s+/).map(normalizeWord);
  const p = (pred || '').trim().split(/\s+/).map(normalizeWord);
  const mismatches = [];
  let correct = 0;
  const n = Math.max(g.length, p.length);
  for (let i = 0; i < n; i++) {
    const gw = g[i] ?? '', pw = p[i] ?? '';
    if (gw === pw) correct++;
    else mismatches.push({ index: i, gold: gw, pred: pw, lettersMatch: stripMarks(gw) === stripMarks(pw) });
  }
  return { total: g.length, correct, mismatches };
}

export function scoreAll(items, predictions) {
  let total = 0, correct = 0;
  const rows = items.map((item, i) => {
    const r = scoreSentence(item.gold, predictions[i]);
    total += r.total; correct += r.correct;
    return { id: item.id, ...r };
  });
  return { total, correct, accuracy: total ? correct / total : 0, rows };
}

const isMain = typeof process !== 'undefined' && process.argv[1] && /score\.mjs$/.test(process.argv[1]);
if (isMain) {
  const here = dirname(fileURLToPath(import.meta.url));
  const testset = JSON.parse(readFileSync(join(here, '..', 'assets', 'testset.json'), 'utf8'));
  const file = process.argv[2];
  if (!file) { console.error('usage: node score.mjs predictions.json'); process.exit(2); }
  const { predictions } = JSON.parse(readFileSync(file, 'utf8'));
  const res = scoreAll(testset.items, predictions);
  console.log(`word accuracy: ${res.correct}/${res.total} = ${(res.accuracy * 100).toFixed(1)}%`);
  for (const row of res.rows) {
    if (!row.mismatches.length) continue;
    console.log(`\n#${row.id}: ${row.correct}/${row.total}`);
    for (const m of row.mismatches) console.log(`  ${m.lettersMatch ? 'حركات' : 'حروف '}  gold=${m.gold}  pred=${m.pred}`);
  }
}
