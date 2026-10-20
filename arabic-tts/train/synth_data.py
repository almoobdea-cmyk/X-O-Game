"""Synthetic 'media + subtitles' corpus for the smoke test: sentences spoken by the formant engine as two synthetic
speakers, concatenated into media files with SRT cues. Proves the pipeline; carries no real speech.

  python synth_data.py --out raw/ --n 240
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audio import save_wav, read_wav, SR  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
SKILL = os.path.join(ROOT, '..', '.claude', 'skills', 'arabic-harakat-reading', 'assets')


def sentences():
    out = []
    for name, mode in (('testset.json', 'fusha'), ('testset-saudi.json', 'saudi')):
        for it in json.load(open(os.path.join(SKILL, name), encoding='utf-8'))['items']:
            out.append((it['gold'], mode))
    words = [it for it in json.load(open(os.path.join(ROOT, 'assets', 'enroll-script.json'), encoding='utf-8'))['items']]
    for _ in range(60):
        k = random.randint(2, 4); mode = random.choice(['fusha', 'saudi'])
        pool = [w['text'] for w in words if w['mode'] == mode] or [w['text'] for w in words]
        out.append((' '.join(random.choice(pool) for _ in range(k)), mode))
    return out


def srt_time(s):
    ms = int(round(s * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--n', type=int, default=240); ap.add_argument('--per-file', type=int, default=20)
    args = ap.parse_args()
    random.seed(1); os.makedirs(args.out, exist_ok=True)
    speakers = [('spk_a', 112, 1.0), ('spk_b', 178, 0.92)]
    sents = sentences()
    utts = [(random.choice(sents), random.choice(speakers)) for _ in range(args.n)]
    manifest = []
    tmp = os.path.join(args.out, '_tmp.wav')
    for fi in range(0, len(utts), args.per_file):
        chunk = utts[fi:fi + args.per_file]
        pieces, cues, t = [], [], 0.3
        pieces.append(np.zeros(int(0.3 * SR), dtype=np.float32))
        spk = chunk[0][1]
        for (text, mode), _ in chunk:
            subprocess.run(['node', os.path.join(ROOT, 'cli.mjs'), 'say', text, '--mode', mode, '--f0', str(spk[1]), '--rate', str(spk[2]), '--out', tmp], check=True, capture_output=True)
            x = read_wav(tmp); dur = len(x) / SR
            cues.append((t, t + dur, text)); pieces.append(x); pieces.append(np.zeros(int(0.5 * SR), dtype=np.float32)); t += dur + 0.5
        media = os.path.join(args.out, f'media_{fi // args.per_file:03d}.wav'); subs = media.replace('.wav', '.srt')
        save_wav(media, np.concatenate(pieces))
        with open(subs, 'w', encoding='utf-8') as f:
            for i, (a, b, text) in enumerate(cues, 1):
                f.write(f'{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n\n')
        manifest.append((media, subs, spk[0], 'auto'))
    os.remove(tmp)
    with open(os.path.join(args.out, 'manifest.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['media_path', 'subtitle_path', 'speaker_id', 'mode']); w.writerows(manifest)
    with open(os.path.join(args.out, 'diacritized.txt'), 'w', encoding='utf-8') as f:
        for text, _ in sents:
            f.write(text + '\n')
    print(f'{len(utts)} utterances in {len(manifest)} media files -> {args.out}/manifest.csv')


if __name__ == '__main__':
    main()
