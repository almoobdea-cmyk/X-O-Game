"""Step 1-2: media + subtitles -> utterance clips + metadata.jsonl.

manifest.csv columns: media_path,subtitle_path,speaker_id,mode   (mode: fusha | saudi | auto)
Subtitles: SRT or WebVTT. Each cue becomes one clip if it passes the quality gate.
"""
import argparse
import csv
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audio import load_audio, save_wav, SR  # noqa: E402

TIME_RE = re.compile(r'(\d+):(\d+):(\d+)[.,](\d+)')
TAG_RE = re.compile(r'<[^>]+>|\{[^}]+\}')


def _ts(s):
    h, m, sec, ms = TIME_RE.match(s.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms.ljust(3, '0')[:3]) / 1000


def parse_subtitles(path):
    """Yield (start, end, text) from SRT or VTT."""
    text = open(path, encoding='utf-8-sig').read()
    blocks = re.split(r'\n\s*\n', text.strip())
    for b in blocks:
        lines = [l for l in b.strip().split('\n') if l.strip()]
        if not lines:
            continue
        if lines[0].strip().upper().startswith('WEBVTT') or lines[0].startswith('NOTE'):
            continue
        tl = next((l for l in lines if '-->' in l), None)
        if not tl:
            continue
        a, b2 = tl.split('-->')[:2]
        try:
            start, end = _ts(a), _ts(b2.split()[0])
        except Exception:
            continue
        body = [l for l in lines[lines.index(tl) + 1:]]
        t = TAG_RE.sub('', ' '.join(body)).strip()
        if t:
            yield start, end, t


ARABIC_RE = re.compile(r'[؀-ۿ]')
LATIN_RE = re.compile(r'[A-Za-z]')


def clean_text(t):
    t = re.sub(r'[‎‏‪-‮]', '', t)
    t = re.sub(r'\[[^\]]*\]|\([^)]*\)', ' ', t)      # [موسيقى] (ضحك)
    t = re.sub(r'\s+', ' ', t).strip(' -–—')
    return t.strip()


def quality_ok(t, dur):
    if not t or dur < 0.6 or dur > 15.0:
        return False
    ar = len(ARABIC_RE.findall(t)); la = len(LATIN_RE.findall(t))
    if ar < 3 or la > ar * 0.2:
        return False
    cps = len(t) / dur
    return 3 <= cps <= 30     # characters per second: catches mistimed cues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pad', type=float, default=0.05, help='seconds added around each cue')
    args = ap.parse_args()
    clips_dir = os.path.join(args.out, 'clips'); os.makedirs(clips_dir, exist_ok=True)
    meta_path = os.path.join(args.out, 'metadata.jsonl')
    kept = dropped = 0
    with open(args.manifest, encoding='utf-8') as f, open(meta_path, 'w', encoding='utf-8') as mf:
        for row in csv.DictReader(f):
            media, subs = row['media_path'], row['subtitle_path']
            speaker = row.get('speaker_id') or os.path.splitext(os.path.basename(media))[0]
            mode = row.get('mode') or 'auto'
            base = re.sub(r'[^A-Za-z0-9_-]', '_', os.path.splitext(os.path.basename(media))[0])
            for i, (start, end, raw) in enumerate(parse_subtitles(subs)):
                t = clean_text(raw); dur = end - start
                if not quality_ok(t, dur):
                    dropped += 1; continue
                x = load_audio(media, max(0.0, start - args.pad), end + args.pad)
                if len(x) < SR * 0.4 or float(np.max(np.abs(x))) < 0.01:
                    dropped += 1; continue
                name = f'{base}_{i:05d}.wav'
                save_wav(os.path.join(clips_dir, name), x)
                mf.write(json.dumps({'clip': name, 'text': t, 'speaker': speaker, 'mode': mode, 'source': media, 'start': round(start, 3), 'end': round(end, 3), 'dur': round(len(x) / SR, 3)}, ensure_ascii=False) + '\n')
                kept += 1
    print(f'kept {kept} clips, dropped {dropped}; metadata at {meta_path}')


if __name__ == '__main__':
    main()
