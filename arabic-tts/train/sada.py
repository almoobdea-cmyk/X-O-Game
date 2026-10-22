"""SADA (SDAIA) -> Nataq training data, Najdi subset.

SADA: ~668 h of Saudi broadcast speech with segment-level transcripts and dialect/speaker/gender labels.
License CC BY-NC-SA 4.0 (non-commercial; a commercial product needs an agreement with SDAIA).

  python sada.py download --dest sada/                      # Kaggle API (needs KAGGLE_USERNAME / KAGGLE_KEY)
  python sada.py inspect  --root sada/                      # column names, dialect counts, hours per speaker
  python sada.py build    --root sada/ --out data-najdi/ --dialect Najdi [--max-hours 30] [--min-speaker-minutes 10]

`build` writes the same layout ingest.py produces (clips/ + metadata.jsonl, mode=saudi), so the rest of the pipeline
(diacritizer -> aligner -> train_tts) runs unchanged. Column names in SADA's CSVs have varied between releases, so they are
matched by keyword; run `inspect` first and pass --col-* overrides if the guess is wrong.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audio import load_audio, save_wav, SR  # noqa: E402
from ingest import clean_text  # noqa: E402

KAGGLE_SLUG = 'sdaiancai/sada2022'   # verify on kaggle.com; the dataset page lists the exact slug


def download(args):
    os.makedirs(args.dest, exist_ok=True)
    if not (os.environ.get('KAGGLE_USERNAME') and os.environ.get('KAGGLE_KEY')) and not os.path.exists(os.path.expanduser('~/.kaggle/kaggle.json')):
        sys.exit('Kaggle credentials missing: set KAGGLE_USERNAME and KAGGLE_KEY (kaggle.com -> Settings -> API -> Create token). You must also accept the dataset terms on its Kaggle page once.')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', 'kaggle'], check=True)
    subprocess.run(['kaggle', 'datasets', 'download', '-d', args.slug, '-p', args.dest, '--unzip'], check=True)
    print(f'downloaded {args.slug} into {args.dest}')


def find_csvs(root):
    out = []
    for dp, _, fns in os.walk(root):
        for f in fns:
            if f.lower().endswith('.csv'):
                out.append(os.path.join(dp, f))
    return sorted(out)


def guess_columns(header, overrides):
    h = {c.lower(): c for c in header}
    def pick(key, *patterns):
        if overrides.get(key):
            return overrides[key]
        for p in patterns:
            for lc, orig in h.items():
                if re.search(p, lc):
                    return orig
        return None
    cols = {
        'file': pick('file', r'^filename$', r'file.?name', r'^file$', r'audio'),
        'start': pick('start', r'segment.?start', r'^start'),
        'end': pick('end', r'segment.?end', r'^end'),
        'text': pick('text', r'processed.?text', r'ground.?truth.?text', r'^text$', r'transcript'),
        'speaker': pick('speaker', r'speaker.?id', r'^speaker$'),
        'dialect': pick('dialect', r'dialect'),
        'gender': pick('gender', r'gender'),
    }
    return cols


def rows(root, overrides):
    for path in find_csvs(root):
        with open(path, encoding='utf-8-sig', newline='') as f:
            r = csv.DictReader(f)
            if not r.fieldnames:
                continue
            cols = guess_columns(r.fieldnames, overrides)
            if not (cols['file'] and cols['text'] and cols['start'] and cols['end']):
                continue
            for row in r:
                yield path, cols, row


def resolve_audio(root, name):
    if os.path.isabs(name) and os.path.exists(name):
        return name
    cands = [name, name + '.wav', os.path.basename(name), os.path.basename(name) + '.wav']
    for dp, _, fns in os.walk(root):
        s = set(fns)
        for c in cands:
            if c in s:
                return os.path.join(dp, c)
    return None


def inspect(args):
    dialects, speakers, files = Counter(), defaultdict(float), 0
    cols_seen = None
    for path, cols, row in rows(args.root, vars(args)):
        cols_seen = cols_seen or (path, cols)
        try:
            dur = float(row[cols['end']]) - float(row[cols['start']])
        except Exception:
            continue
        d = (row.get(cols['dialect']) or 'unknown').strip() if cols['dialect'] else 'unknown'
        dialects[d] += dur / 3600
        spk = (row.get(cols['speaker']) or 'unknown').strip() if cols['speaker'] else 'unknown'
        speakers[(d, spk)] += dur / 60
        files += 1
    print('columns guessed from', cols_seen[0] if cols_seen else 'no csv found', json.dumps(cols_seen[1] if cols_seen else {}, ensure_ascii=False))
    print(f'{files} segments')
    for d, h in dialects.most_common():
        print(f'  {d:20s} {h:8.1f} h')
    naj = sorted([(m, s) for (d, s), m in speakers.items() if d.lower().startswith(args.dialect.lower())], reverse=True)
    print(f'{args.dialect}: {len(naj)} speakers; top 15 by minutes:')
    for m, s in naj[:15]:
        print(f'  {s:30s} {m:7.1f} min')


ARABIC_RE = re.compile(r'[؀-ۿ]')


def build(args):
    clips_dir = os.path.join(args.out, 'clips'); os.makedirs(clips_dir, exist_ok=True)
    # pass 1: collect segments for the dialect, per speaker minutes
    segs, per_spk = [], defaultdict(float)
    for path, cols, row in rows(args.root, vars(args)):
        d = (row.get(cols['dialect']) or '').strip() if cols['dialect'] else ''
        if not d.lower().startswith(args.dialect.lower()):
            continue
        try:
            start, end = float(row[cols['start']]), float(row[cols['end']])
        except Exception:
            continue
        dur = end - start
        text = clean_text(row[cols['text']] or '')
        if not (0.8 <= dur <= 14.0) or len(ARABIC_RE.findall(text)) < 4:
            continue
        spk = (row.get(cols['speaker']) or 'unknown').strip() if cols['speaker'] else 'unknown'
        gender = (row.get(cols['gender']) or '').strip() if cols['gender'] else ''
        segs.append((row[cols['file']], start, end, text, spk, gender))
        per_spk[spk] += dur / 60
    keep_spk = {s for s, m in per_spk.items() if m >= args.min_speaker_minutes}
    segs = [s for s in segs if s[4] in keep_spk]
    segs.sort(key=lambda s: (-per_spk[s[4]], s[0], s[1]))
    print(f'{args.dialect}: {len(segs)} usable segments from {len(keep_spk)} speakers with >= {args.min_speaker_minutes} min')
    budget = args.max_hours * 3600 if args.max_hours else None
    total, n, missing = 0.0, 0, set()
    cache = {}
    with open(os.path.join(args.out, 'metadata.jsonl'), 'w', encoding='utf-8') as mf:
        for fname, start, end, text, spk, gender in segs:
            if budget and total >= budget:
                break
            if fname not in cache:
                cache[fname] = resolve_audio(args.root, fname)
            path = cache[fname]
            if not path:
                missing.add(fname); continue
            x = load_audio(path, max(0.0, start - 0.05), end + 0.05)
            if len(x) < SR * 0.5 or float(np.max(np.abs(x))) < 0.01:
                continue
            clip = f'{re.sub(r"[^A-Za-z0-9_-]", "_", os.path.splitext(os.path.basename(fname))[0])}_{int(start * 1000):09d}.wav'
            save_wav(os.path.join(clips_dir, clip), x)
            mf.write(json.dumps({'clip': clip, 'text': text, 'speaker': f'sada_{spk}', 'gender': gender, 'mode': 'saudi', 'dialect': args.dialect, 'source': fname, 'start': round(start, 3), 'end': round(end, 3), 'dur': round(len(x) / SR, 3)}, ensure_ascii=False) + '\n')
            total += len(x) / SR; n += 1
    print(f'wrote {n} clips, {total / 3600:.2f} h -> {args.out}; {len(missing)} source files not found')
    with open(os.path.join(args.out, 'speakers.json'), 'w', encoding='utf-8') as f:
        json.dump({s: round(m, 1) for s, m in per_spk.items() if s in keep_spk}, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('download'); d.add_argument('--dest', required=True); d.add_argument('--slug', default=KAGGLE_SLUG)
    for name in ('inspect', 'build'):
        p = sub.add_parser(name); p.add_argument('--root', required=True); p.add_argument('--dialect', default='Najdi')
        for c in ('file', 'start', 'end', 'text', 'speaker', 'dialect', 'gender'):
            p.add_argument(f'--col-{c}', dest=c, default=None, help=f'override the {c} column name')
        if name == 'build':
            p.add_argument('--out', required=True); p.add_argument('--max-hours', type=float, default=None); p.add_argument('--min-speaker-minutes', type=float, default=10)
    args = ap.parse_args()
    {'download': download, 'inspect': inspect, 'build': build}[args.cmd](args)
