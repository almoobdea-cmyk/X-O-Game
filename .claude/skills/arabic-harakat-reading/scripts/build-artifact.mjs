// Build the demo page: inlines the reading engine, the prompt and the test set into the HTML template.
// usage: node build-artifact.mjs <output.html>
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const out = process.argv[2];
if (!out) { console.error('usage: node build-artifact.mjs <output.html>'); process.exit(2); }

let engine = readFileSync(join(here, 'reading.mjs'), 'utf8');
engine = engine.slice(0, engine.indexOf('// CLI')); // drop the CLI block
engine = engine.replace(/^export function /gm, 'function ');
let scorer = readFileSync(join(here, 'score.mjs'), 'utf8');
scorer = scorer.slice(scorer.indexOf('const MARK_RE'), scorer.indexOf('const isMain'));
scorer = scorer.replace(/^export function /gm, 'function ');

const prompt = readFileSync(join(root, 'assets', 'prompt.md'), 'utf8');
const promptSaudi = readFileSync(join(root, 'assets', 'prompt-saudi.md'), 'utf8');
const testset = JSON.parse(readFileSync(join(root, 'assets', 'testset.json'), 'utf8'));
const testsetSaudi = JSON.parse(readFileSync(join(root, 'assets', 'testset-saudi.json'), 'utf8'));
const template = readFileSync(join(root, 'assets', 'demo-template.html'), 'utf8');

const html = template
  .replace('/*__ENGINE__*/', () => engine)
  .replace('/*__SCORER__*/', () => scorer)
  .replace('"__PROMPT__"', () => JSON.stringify(prompt))
  .replace('"__PROMPT_SAUDI__"', () => JSON.stringify(promptSaudi))
  .replace('"__TESTSET__"', () => JSON.stringify(testset.items))
  .replace('"__TESTSET_SAUDI__"', () => JSON.stringify(testsetSaudi.items));

if (/__(ENGINE|PROMPT|PROMPT_SAUDI|TESTSET|TESTSET_SAUDI|SCORER)__/.test(html)) {
  console.error('placeholder left unreplaced'); process.exit(1);
}
writeFileSync(out, html);
console.log(`wrote ${out} (${(Buffer.byteLength(html) / 1024).toFixed(0)} KB)`);
