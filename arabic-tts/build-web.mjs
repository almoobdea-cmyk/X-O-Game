// Bundle the engine into the demo page: concatenates the ESM modules (imports and exports stripped) into one inline script.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const out = process.argv[2] || join(here, 'web', 'nataq.html');
const skillReader = join(here, '..', '.claude', 'skills', 'arabic-harakat-reading', 'scripts', 'reading.mjs');
const order = [skillReader, 'src/wav.mjs', 'src/dsp.mjs', 'src/phonemize.mjs', 'src/formant.mjs', 'src/mode.mjs', 'src/voice.mjs', 'src/concat.mjs', 'src/index.mjs'];

let bundle = '';
for (const f of order) {
  let src = readFileSync(f.startsWith('/') ? f : join(here, f), 'utf8');
  if (f.endsWith('reading.mjs')) src = src.slice(0, src.indexOf('// CLI'));
  src = src.replace(/^import[^\n]*\n/gm, '').replace(/^export \{[^}]*\};?\s*$/gm, '').replace(/^export (const|function|let|class) /gm, '$1 ');
  bundle += `\n// ---- ${f.replace(/^.*\//, '')} ----\n` + src;
}
const script = JSON.parse(readFileSync(join(here, 'assets', 'enroll-script.json'), 'utf8')).items;
const template = readFileSync(join(here, 'web', 'template.html'), 'utf8');
const html = template.replace('/*__ENGINE__*/', () => bundle).replace('"__SCRIPT__"', () => JSON.stringify(script));
if (/__(ENGINE|SCRIPT)__/.test(html)) { console.error('placeholder left'); process.exit(1); }
writeFileSync(out, html);
console.log(`wrote ${out} (${(Buffer.byteLength(html) / 1024).toFixed(0)} KB)`);
