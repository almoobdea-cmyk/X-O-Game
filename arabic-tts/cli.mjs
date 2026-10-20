#!/usr/bin/env node
// ناطق: command line.
//   node cli.mjs say "نَصٌّ مُشَكَّلٌ" [--mode auto|fusha|saudi] [--voice voice.json] [--out out.wav] [--f0 120] [--rate 1.0]
//   node cli.mjs script                      print the enrollment script
//   node cli.mjs enroll --dir recordings/ [--out voice.json] [--name "اسم"]   files 01.wav..48.wav, or all.wav split on silence
//   node cli.mjs demo [--voice voice.json] [--out out/]   synthesize the skill's gold sentences
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { synthesize, enrollItem, buildVoice, serializeVoice, deserializeVoice, splitRecording, decodeWav, encodeWav } from './src/index.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const cmd = args[0];
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def; };
const positional = args.slice(1).filter((a, i, arr) => !a.startsWith('--') && !(arr[i - 1] || '').startsWith('--'));
const script = JSON.parse(readFileSync(join(here, 'assets', 'enroll-script.json'), 'utf8')).items;

function loadVoice(path) { return path ? deserializeVoice(readFileSync(path, 'utf8')) : null; }

if (cmd === 'say') {
  const text = positional.join(' ');
  if (!text) { console.error('usage: cli.mjs say "نصّ مشكّل" [--mode] [--voice] [--out]'); process.exit(2); }
  const voice = loadVoice(opt('--voice'));
  const profile = {}; if (opt('--f0')) profile.f0Base = Number(opt('--f0')); if (opt('--rate')) profile.rate = Number(opt('--rate'));
  const r = synthesize(text, { mode: opt('--mode', 'auto'), voice, profile });
  const out = opt('--out', 'out.wav');
  writeFileSync(out, encodeWav(r.samples));
  console.log(`mode=${r.mode} engine=${r.engine} ${JSON.stringify(r.stats)}`);
  console.log(r.plan.phones.map(p => p.p === '_' ? `[${p.dur}ms]` : p.p + (p.geminate ? 'ː' : '')).join(' '));
  console.log(`wrote ${out}`);
} else if (cmd === 'script') {
  for (const it of script) console.log(`${String(it.id).padStart(2, '0')}  ${it.mode === 'saudi' ? 'سعودي' : 'فصحى '}  ${it.text}`);
} else if (cmd === 'enroll') {
  const dir = opt('--dir'); if (!dir) { console.error('--dir required'); process.exit(2); }
  let items = [];
  const all = ['all.wav', 'script.wav'].map(f => join(dir, f)).find(existsSync);
  if (all) {
    const { samples } = decodeWav(readFileSync(all));
    const r = splitRecording(samples, script);
    if (!r.ok) { console.error(`found ${r.found} chunks, expected ${r.expected}; record each word separately as 01.wav … ${script.length}.wav`); process.exit(1); }
    items = r.items;
  } else {
    const files = readdirSync(dir).filter(f => /\.wav$/i.test(f)).sort();
    for (const f of files) { const id = parseInt(f, 10); const it = script.find(s => s.id === id); if (!it) continue; items.push({ ...it, samples: decodeWav(readFileSync(join(dir, f))).samples }); }
  }
  if (!items.length) { console.error('no recordings found'); process.exit(1); }
  const enrolled = items.map(it => { const r = enrollItem(it); console.log(`${it.id}\t${it.text}\t${r.alignment.map(a => `${a.p}:${(a.end - a.start) * 10}ms`).join(' ')}`); return r; });
  const voice = buildVoice(enrolled, { name: opt('--name', 'صوتي') });
  writeFileSync(opt('--out', 'voice.json'), serializeVoice(voice));
  console.log(JSON.stringify(voice.profile, null, 1));
} else if (cmd === 'demo') {
  const voice = loadVoice(opt('--voice'));
  const outDir = opt('--out', 'out'); mkdirSync(outDir, { recursive: true });
  const skill = join(here, '..', '.claude', 'skills', 'arabic-harakat-reading', 'assets');
  const sets = [['fusha', JSON.parse(readFileSync(join(skill, 'testset.json'), 'utf8')).items], ['saudi', JSON.parse(readFileSync(join(skill, 'testset-saudi.json'), 'utf8')).items]];
  for (const [mode, items] of sets) for (const it of items.slice(0, Number(opt('--n', 6)))) {
    const r = synthesize(it.gold + '.', { mode, voice });
    const f = join(outDir, `${mode}-${String(it.id).padStart(2, '0')}.wav`);
    writeFileSync(f, encodeWav(r.samples));
    console.log(`${f}\t${r.engine}\t${r.stats.durationMs}ms\t${it.gold}`);
  }
} else {
  console.log('commands: say | script | enroll | demo');
}
