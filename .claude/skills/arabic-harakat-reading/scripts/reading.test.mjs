import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { readText, readWord, checkCompleteness, completenessReport } from './reading.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const testset = JSON.parse(readFileSync(join(here, '..', 'assets', 'testset.json'), 'utf8'));

const cases = [
  // [input, expected reading with pause at end]
  ['كَتَبَ', 'katab'],
  ['كِتَابٌ', 'kitāb'],
  ['كِتَابًا', 'kitābā'],
  ['مَدْرَسَةٌ', 'madrasah'],
  ['مُعَلِّمٌ', 'muʿallim'],
  ['الشَّمْسُ', 'ash-shams'],
  ['الْقَمَرُ', 'al-qamar'],
  ['يَوْمٌ', 'yawm'],
  ['بَيْتٌ', 'bayt'],
  ['يَقُولُ', 'yaqūl'],
  ['كَبِيرٌ', 'kabīr'],
  ['كَتَبُوا', 'katabū'],
  ['آمَنَ', 'āman'],
  ['مُؤْمِنٌ', 'muʾmin'],
  ['سَأَلَ', 'saʾal'],
  ['فَتًى', 'fatā'],
  ['سَمَاءً', 'samāʾā'],
  ['الَّذِينَ', 'al-ladhīn'],
  ['هَـٰذَا', 'hādhā'],
  ['مُحَمَّدٌ', 'muḥammad'],
  ['الْحَقُّ', 'al-ḥaqq'],
];

for (const [input, expected] of cases) {
  test(`reads ${input}`, () => {
    const { reading } = readText(input, { pause: true });
    assert.equal(reading, expected);
  });
}

test('no-pause keeps case endings and tanween', () => {
  assert.equal(readText('كِتَابٌ', { pause: false }).reading, 'kitābun');
  assert.equal(readText('كِتَابًا', { pause: false }).reading, 'kitāban');
  assert.equal(readText('مَدْرَسَةٌ', { pause: false }).reading, 'madrasatun');
  assert.equal(readText('ذَهَبَ', { pause: false }).reading, 'dhahaba');
});

test('article elides after a vowel and assimilates before sun letters', () => {
  assert.equal(readText('فِي الْمَدْرَسَةِ', { pause: false }).reading, 'fī l-madrasati');
  assert.equal(readText('ذَهَبَ الطَّالِبُ', { pause: false }).reading, 'dhahaba ṭ-ṭālibu');
  assert.equal(readText('مِنَ الْبَيْتِ', { pause: false }).reading, 'mina l-bayti');
});

test('hamzat wasl in verbs elides after a vowel and gets kasra at start', () => {
  assert.equal(readText('اجْتَهِدْ', { pause: true }).reading, 'ijtahid');
  assert.equal(readText('الَّذِينَ اجْتَهَدُوا', { pause: true }).reading, 'al-ladhīna jtahadū');
  assert.equal(readText('اكْتُبْ', { pause: true }).reading, 'uktub');
});

test('IPA scheme', () => {
  assert.equal(readText('الشَّمْسُ', { pause: false, scheme: 'ipa' }).reading, 'aʃ-ʃamsu');
  assert.equal(readText('ثَلَاثَةُ', { pause: false, scheme: 'ipa' }).reading, 'θalaːθatu');
});

test('gold test set readings at pause', () => {
  for (const item of testset.items) {
    const { reading, warnings } = readText(item.gold, { pause: true });
    assert.equal(reading, item.reading_pause, `item ${item.id}`);
    assert.deepEqual(warnings, [], `item ${item.id} warnings`);
  }
});

test('completeness check flags bare consonants and accepts full vocalization', () => {
  assert.deepEqual(checkCompleteness('كَتَبَ'), []);
  assert.deepEqual(checkCompleteness('الْمَدْرَسَةِ'), []);
  assert.deepEqual(checkCompleteness('الطَّالِبُ'), []);
  assert.deepEqual(checkCompleteness('كَتَبُوا'), []);
  assert.equal(checkCompleteness('كتب').length, 3);
  assert.equal(checkCompleteness('كَتب').length, 2);
  assert.equal(completenessReport('ذَهَبَ الطالب').length, 1);
  for (const item of testset.items) {
    assert.deepEqual(completenessReport(item.gold), [], `gold item ${item.id} must be complete`);
  }
});

test('readWord reports elision flag', () => {
  assert.equal(readWord('الْبَيْتِ', { afterVowel: true }).elided, true);
  assert.equal(readWord('الْبَيْتِ', { afterVowel: false }).elided, false);
});

import { prosody, toTtsText } from './reading.mjs';
const testsetSaudi = JSON.parse(readFileSync(join(here, '..', 'assets', 'testset-saudi.json'), 'utf8'));

test('Saudi white readings at pause', () => {
  for (const item of testsetSaudi.items) {
    const { reading, warnings } = readText(item.gold, { pause: true, dialect: 'saudi' });
    assert.equal(reading, item.reading_pause, `saudi item ${item.id}`);
    assert.deepEqual(warnings, [], `saudi item ${item.id} warnings`);
    assert.deepEqual(completenessReport(item.gold, { dialect: 'saudi' }), [], `saudi gold ${item.id} must be complete`);
  }
});

test('Saudi white keeps q in religious and legal words, drops final hamza, reads ta marbuta as a', () => {
  assert.equal(readText('الْقُرْآنْ', { dialect: 'saudi' }).reading, 'al-qurʾān');
  assert.equal(readText('قَالْ', { dialect: 'saudi' }).reading, 'gāl');
  assert.equal(readText('سَمَاءْ', { dialect: 'saudi' }).reading, 'samā');
  assert.equal(readText('مَدْرَسَةْ الْبَنَاتْ', { dialect: 'saudi' }).reading, 'madrasat al-banāt');
  assert.equal(readText('أَبَدًا', { dialect: 'saudi' }).reading, 'abadan');
  assert.equal(readText('يَوْمْ', { dialect: 'saudi', scheme: 'ipa' }).reading, 'joːm');
});

test('prosody segments and pause timing', () => {
  const segs = prosody('ذَهَبَ الطَّالِبُ، ثُمَّ رَجَعَ. هَلْ رَأَيْتَهُ؟ نَعَمْ...');
  assert.equal(segs.length, 4);
  assert.equal(segs[0].pauseMs, 250); assert.equal(segs[0].type, 'continue');
  assert.equal(segs[1].pauseMs, 600); assert.equal(segs[1].type, 'statement');
  assert.equal(segs[2].type, 'question');
  assert.equal(segs[3].pauseMs, 800);
  assert.equal(prosody('بلا ترقيم')[0].type, 'statement');
});

test('ElevenLabs-ready text per model family', () => {
  const t = 'أَهْلًا؛ كَيْفَ حَالُكَ؟ بِخَيْرٍ...';
  assert.equal(toTtsText(t, { family: 'v3' }), 'أَهْلًا؛ كَيْفَ حَالُكَ؟ بِخَيْرٍ…');
  assert.equal(toTtsText(t, { family: 'v2' }), 'أَهْلًا؛ <break time="0.4s" /> كَيْفَ حَالُكَ؟ بِخَيْرٍ. <break time="0.8s" />');
  assert.equal(toTtsText('بلا ترقيم'), 'بلا ترقيم.');
});
