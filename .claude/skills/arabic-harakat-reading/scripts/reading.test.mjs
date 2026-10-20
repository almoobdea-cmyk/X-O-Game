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
