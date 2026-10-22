#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Turn SDAIA's SADA corpus (Saudi Audio Dataset for Arabic, Kaggle `sdaiancai/sada2022`,
CC BY-NC-SA 4.0) into Pocket TTS training manifests.

Output: <out>/train.jsonl and <out>/valid.jsonl, one JSON object per line in the format
`training/dataloader/loader.py` of kyutai-labs/pocket-tts reads:

    {"path": "/abs/batch_1/episode.wav", "start": 12.34, "duration": 4.21,
     "transcript": "...", "speaker": "SpeakerID", "dialect": "Najdi"}

Nothing is cut or re-encoded: each line points at the whole episode WAV with a
start/duration window, exactly like Pocket TTS's own prepare_data.py.

SADA columns (from the IEEE DataPort description and the Hugging Face mirrors; verify
against the header of your train.csv and override with --col-* if they differ):
  FileName, SegmentStart, SegmentEnd, SpeakerID, SpeakerGender, SpeakerAge,
  SpeakerDialect, Environment, GroundTruthText, ProcessedText

Next steps after this script (run from a pocket-tts checkout, see ARABIC_TRAINING.md):
  uv run -m training.scripts.align_data data/sada/train.jsonl data/sada/train_aligned.jsonl \
      --model jonatasgrosman/wav2vec2-large-xlsr-53-arabic
  uv run -m training.scripts.train_tokenizer data/sada/tokenizer data/sada/train.jsonl \
      --character-coverage 1.0
  uv run training/train.py finetune_arabic.yaml
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
import wave
from collections import Counter, defaultdict
from pathlib import Path

ARABIC_LETTER = re.compile(r"[ء-يٱ-ۓ]")
DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
TATWEEL = "ـ"
# Western and Arabic-Indic digits. Pocket TTS splits digits into single tokens, but a
# TTS trained on broadcast transcripts rarely sees them; prefer spelling numbers out.
DIGITS = re.compile(r"[0-9٠-٩۰-۹]")
MULTI_SPEAKER = {"more than 1 speaker", "morethan1speaker", "unknown", "notapplicable"}


def normalize_text(text: str, strip_diacritics: bool) -> str:
    """Light, reversible-in-spirit cleanup. Phonon has no Arabic normalizer (`--lang none`
    at inference), so whatever convention is chosen here must be applied to inference
    text too. Keep it minimal and document it."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace(TATWEEL, "")
    if strip_diacritics:
        text = DIACRITICS.sub("", text)
    # Unify quote/dash variants the tokenizer would otherwise see as byte-fallback noise.
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_col(header: list[str], wanted: str, override: str | None) -> str:
    if override:
        if override not in header:
            sys.exit(f"column {override!r} not in header {header}")
        return override
    folded = {h.lower().replace("_", "").replace(" ", ""): h for h in header}
    key = wanted.lower().replace("_", "")
    if key in folded:
        return folded[key]
    sys.exit(f"cannot find column {wanted!r} in header {header}; pass --col-{wanted.lower()}")


def wav_duration(path: Path, cache: dict[Path, float]) -> float:
    if path not in cache:
        with wave.open(str(path), "rb") as w:
            cache[path] = w.getnframes() / w.getframerate()
    return cache[path]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sada_root", type=Path, help="folder holding train.csv, valid.csv, test.csv and the audio batches")
    ap.add_argument("--out", type=Path, default=Path("data/sada"))
    ap.add_argument("--audio-root", type=Path, default=None, help="folder FileName is relative to (default: sada_root)")
    ap.add_argument("--min-sec", type=float, default=1.5)
    ap.add_argument("--max-sec", type=float, default=30.0, help="match data.max_duration_sec in the training YAML")
    ap.add_argument("--min-chars", type=int, default=3)
    ap.add_argument("--strip-diacritics", action="store_true", help="remove harakat; SADA is mostly undiacritized anyway")
    ap.add_argument("--keep-digits", action="store_true", help="keep segments whose text contains digits (default: drop)")
    ap.add_argument("--keep-multi-speaker", action="store_true", help="keep SpeakerDialect 'More than 1 speaker'/'Unknown'")
    ap.add_argument("--environments", default="", help="comma-separated Environment values to keep (default: all), e.g. Clean")
    ap.add_argument("--dialects", default="", help="comma-separated SpeakerDialect values to keep (default: all)")
    ap.add_argument("--max-hours", type=float, default=None, help="cap on training hours, taken in CSV order")
    ap.add_argument("--no-check-files", action="store_true", help="do not open each WAV to check it exists and bound the window")
    ap.add_argument("--text-source", choices=["ProcessedText", "GroundTruthText"], default="ProcessedText")
    for c in ("filename", "segmentstart", "segmentend", "speakerid", "speakerdialect", "environment",
              "processedtext", "groundtruthtext"):
        ap.add_argument(f"--col-{c}", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    audio_root = (args.audio_root or args.sada_root).resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    keep_env = {e.strip().lower() for e in args.environments.split(",") if e.strip()}
    keep_dia = {d.strip().lower() for d in args.dialects.split(",") if d.strip()}
    dur_cache: dict[Path, float] = {}

    for split, csv_name in (("train", "train.csv"), ("valid", "valid.csv")):
        src = args.sada_root / csv_name
        if not src.exists():
            print(f"skip {split}: {src} not found", file=sys.stderr)
            continue
        dropped: Counter[str] = Counter()
        hours = 0.0
        per_dialect: defaultdict[str, float] = defaultdict(float)
        n = 0
        with open(src, newline="", encoding="utf-8") as f, open(args.out / f"{split}.jsonl", "w", encoding="utf-8") as w:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            col = {
                "file": find_col(header, "FileName", args.col_filename),
                "start": find_col(header, "SegmentStart", args.col_segmentstart),
                "end": find_col(header, "SegmentEnd", args.col_segmentend),
                "text": find_col(header, args.text_source, getattr(args, f"col_{args.text_source.lower()}")),
            }
            opt = {}
            for name, override in (("SpeakerID", args.col_speakerid), ("SpeakerDialect", args.col_speakerdialect),
                                   ("Environment", args.col_environment)):
                try:
                    opt[name] = find_col(header, name, override)
                except SystemExit:
                    opt[name] = None
            for row in reader:
                try:
                    start, end = float(row[col["start"]]), float(row[col["end"]])
                except ValueError:
                    dropped["bad times"] += 1
                    continue
                duration = end - start
                if not (args.min_sec <= duration <= args.max_sec):
                    dropped["duration"] += 1
                    continue
                dialect = (row.get(opt["SpeakerDialect"]) or "").strip() if opt["SpeakerDialect"] else ""
                if not args.keep_multi_speaker and dialect.lower().replace(" ", "") in {m.replace(" ", "") for m in MULTI_SPEAKER}:
                    dropped["multi-speaker/unknown"] += 1
                    continue
                if keep_dia and dialect.lower() not in keep_dia:
                    dropped["dialect filter"] += 1
                    continue
                env = (row.get(opt["Environment"]) or "").strip() if opt["Environment"] else ""
                if keep_env and env.lower() not in keep_env:
                    dropped["environment filter"] += 1
                    continue
                text = normalize_text(row[col["text"]] or "", args.strip_diacritics)
                if len(text) < args.min_chars or not ARABIC_LETTER.search(text):
                    dropped["empty/non-arabic text"] += 1
                    continue
                if not args.keep_digits and DIGITS.search(text):
                    dropped["digits"] += 1
                    continue
                path = audio_root / row[col["file"]]
                if not args.no_check_files:
                    if not path.is_file():
                        dropped["missing wav"] += 1
                        continue
                    total = wav_duration(path, dur_cache)
                    if end > total + 0.05:
                        dropped["window past end of file"] += 1
                        continue
                rec = {
                    "path": str(path),
                    "start": round(start, 3),
                    "duration": round(duration, 3),
                    "transcript": text,
                    "speaker": (row.get(opt["SpeakerID"]) or "").strip() if opt["SpeakerID"] else "",
                    "dialect": dialect,
                }
                w.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
                hours += duration / 3600
                per_dialect[dialect or "?"] += duration / 3600
                if split == "train" and args.max_hours and hours >= args.max_hours:
                    break
        print(f"{split}: {n} segments, {hours:.1f} h -> {args.out / (split + '.jsonl')}")
        for k, v in sorted(per_dialect.items(), key=lambda kv: -kv[1])[:12]:
            print(f"   {k:28s} {v:7.1f} h")
        for k, v in dropped.most_common():
            print(f"   dropped {v:7d}  {k}")
    print("normalization: NFC, tatweel removed, quotes/dashes unified"
          + (", diacritics stripped" if args.strip_diacritics else ", diacritics kept")
          + ". Apply the same to inference text (Phonon: --lang none).")


if __name__ == "__main__":
    main()
