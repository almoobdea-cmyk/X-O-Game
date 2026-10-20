// Text → voice pipeline: Arabic text (fusha or Saudi white) → full tashkeel (Claude) → reading + pauses (engine) → ElevenLabs audio.
//
// usage:
//   node tts-pipeline.mjs [--mode auto|fusha|saudi] [--voice VOICE_ID] [--model eleven_v4] [--out out.mp3] [--vocalized] "النص"
//
// env: ANTHROPIC_API_KEY (or an `ant auth login` profile) for the tashkeel step; ELEVENLABS_API_KEY for audio.
// --vocalized: the text is already fully vocalized, skip the Claude step.
// Library voices must be added to your ElevenLabs workspace ("Add to my voices") before their IDs work through the API.

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import Anthropic from '@anthropic-ai/sdk';
import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';
import { readText, completenessReport, prosody, toTtsText } from './reading.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

// Dialect comes from the voice, not from a parameter: pick a voice whose accent label matches the mode.
export const DEFAULT_VOICES = {
  fusha: { id: 'rPNcQ53R703tTmtue1AT', name: 'Mazen Lawand', accent: 'ar-modern-standard' },
  saudi: { id: 'yXEnnEln9armDCyhkXcA', name: 'Jeddawi Echo', accent: 'ar-saudi' },
};

const SAUDI_MARKERS = ['وش', 'إيش', 'ايش', 'ليش', 'وين', 'الحين', 'أبغى', 'ابغى', 'أبي', 'تبي', 'تبغى', 'يبغى', 'مو', 'بس', 'مرة', 'اللي', 'هذي', 'هذول', 'بكرة', 'زين', 'خلاص', 'يلا', 'شوي', 'عشان', 'لين', 'راح', 'كذا', 'معليش', 'طيب'];
const FUSHA_MARKERS = ['إن', 'إنّ', 'سوف', 'لن', 'لم', 'ليس', 'الذي', 'التي', 'الذين', 'هذه', 'ماذا', 'لماذا', 'أين', 'كيف', 'حيث', 'إذ', 'قد', 'ثم', 'ثمّ'];

export function detectMode(text) {
  const words = text.replace(/[ً-ْٰ]/g, '').split(/\s+/).map(w => w.replace(/^[وف]/, '')).filter(Boolean);
  let s = 0, f = 0;
  for (const w of words) { if (SAUDI_MARKERS.includes(w)) s++; if (FUSHA_MARKERS.includes(w)) f++; }
  return s >= 1 && s >= f ? 'saudi' : 'fusha';
}

export function familyFor(modelId) {
  return /^eleven_v[34]/.test(modelId) ? 'v3' : 'v2';
}

/** Step 1: full tashkeel through Claude, using the skill's prompt for the mode. Returns the parsed JSON object. */
export async function diacritize(text, mode, { model = 'claude-opus-5-5' } = {}) {
  const promptFile = mode === 'saudi' ? 'prompt-saudi.md' : 'prompt.md';
  const instructions = readFileSync(join(root, 'assets', promptFile), 'utf8');
  const client = new Anthropic();
  const response = await client.messages.create({
    model,
    max_tokens: 16000,
    output_config: { effort: 'medium' },
    messages: [{ role: 'user', content: instructions + text }],
  });
  if (response.stop_reason === 'refusal') throw new Error('Claude declined this text: ' + (response.stop_details?.explanation ?? ''));
  const raw = response.content.filter(b => b.type === 'text').map(b => b.text).join('');
  const start = raw.indexOf('{'), end = raw.lastIndexOf('}');
  if (start < 0 || end < 0) throw new Error('No JSON object in the model reply:\n' + raw);
  const obj = JSON.parse(raw.slice(start, end + 1));
  if (typeof obj.tashkeel !== 'string') throw new Error('Reply has no "tashkeel" field');
  obj.mode = mode;
  return obj;
}

/** Step 2: deterministic reading, completeness check, pauses and the ElevenLabs-ready text. */
export function prepare(vocalized, mode, modelId) {
  const dialect = mode === 'saudi' ? 'saudi' : 'fusha';
  const { reading, warnings } = readText(vocalized, { pause: true, dialect });
  const incomplete = completenessReport(vocalized, { dialect });
  const segments = prosody(vocalized);
  const ttsText = toTtsText(vocalized, { family: familyFor(modelId) });
  return { reading, warnings, incomplete, segments, ttsText };
}

/** Step 3: audio from ElevenLabs. Returns a Buffer of MP3 bytes. */
export async function synthesize(ttsText, { voiceId, modelId = 'eleven_v4', outputFormat = 'mp3_44100_128', voiceSettings } = {}) {
  const client = new ElevenLabsClient({ apiKey: process.env.ELEVENLABS_API_KEY });
  const stream = await client.textToSpeech.convert(voiceId, {
    text: ttsText,
    modelId,
    languageCode: 'ar',            // enforce Arabic and Arabic normalizer rules (ignored by multilingual_v2)
    applyTextNormalization: 'off', // numbers and dates are already verbalized by the tashkeel step
    outputFormat,
    voiceSettings: voiceSettings ?? { stability: 0.5, similarityBoost: 0.8, style: 0, useSpeakerBoost: true, speed: 1.0 },
  });
  const chunks = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}

export async function textToVoice(text, { mode = 'auto', voiceId, modelId = 'eleven_v4', vocalized = false, claudeModel } = {}) {
  const resolvedMode = mode === 'auto' ? detectMode(text) : mode;
  const result = vocalized ? { tashkeel: text, words: [], mode: resolvedMode } : await diacritize(text, resolvedMode, { model: claudeModel });
  const prep = prepare(result.tashkeel, resolvedMode, modelId);
  const voice = voiceId || DEFAULT_VOICES[resolvedMode].id;
  const audio = await synthesize(prep.ttsText, { voiceId: voice, modelId });
  return { mode: resolvedMode, voiceId: voice, ...result, ...prep, audio };
}

const isMain = typeof process !== 'undefined' && process.argv[1] && /tts-pipeline\.mjs$/.test(process.argv[1]);
if (isMain) {
  const args = process.argv.slice(2);
  const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def; };
  const mode = opt('--mode', 'auto');
  const voiceId = opt('--voice');
  const modelId = opt('--model', 'eleven_v4');
  const out = opt('--out', 'out.mp3');
  const vocalized = args.includes('--vocalized');
  const text = args.filter((a, i) => !a.startsWith('--') && !['--mode', '--voice', '--model', '--out'].includes(args[i - 1])).join(' ').trim();
  if (!text) { console.error('usage: node tts-pipeline.mjs [--mode auto|fusha|saudi] [--voice ID] [--model eleven_v4] [--out out.mp3] [--vocalized] "النص"'); process.exit(2); }
  textToVoice(text, { mode, voiceId, modelId, vocalized }).then(r => {
    writeFileSync(out, r.audio);
    console.log(`mode: ${r.mode}  voice: ${r.voiceId}  model: ${modelId}`);
    console.log(`tashkeel: ${r.tashkeel}`);
    console.log(`reading:  ${r.reading}`);
    console.log(`tts text: ${r.ttsText}`);
    for (const sg of r.segments) console.log(`  ${sg.type.padEnd(11)} ${String(sg.pauseMs).padStart(4)}ms  ${sg.text}`);
    for (const w of r.warnings) console.error('warning: ' + w);
    for (const c of r.incomplete) console.error(`incomplete: ${c.word}`);
    console.log(`wrote ${out} (${(r.audio.length / 1024).toFixed(0)} KB)`);
  }).catch(e => { console.error(e?.message ?? e); process.exit(1); });
}
