#!/usr/bin/env bash
# End-to-end smoke test on CPU with synthetic media: ingest -> diacritizer -> aligner -> TTS -> synthesize.
# Proves the pipeline is wired; it does not produce good audio (tiny data, few steps).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
W=${SMOKE_DIR:-./smoke-out}
STEPS=${STEPS:-150}
rm -rf "$W"; mkdir -p "$W"
echo "== 1-2 synthetic media + subtitles, ingest"
$PY train/synth_data.py --out "$W/raw" --n ${N:-120}
$PY train/ingest.py --manifest "$W/raw/manifest.csv" --out "$W/data"
echo "== 3 diacritizer"
$PY train/diacritizer.py train --corpus "$W/raw/diacritized.txt" --out "$W/ckpt/diacritizer.pt" --steps $STEPS --log 50
$PY train/diacritizer.py eval --model "$W/ckpt/diacritizer.pt" --corpus "$W/raw/diacritized.txt"
$PY train/diacritizer.py apply --model "$W/ckpt/diacritizer.pt" --in "$W/data/metadata.jsonl" --out "$W/data/metadata.vocalized.jsonl"
echo "== 4 aligner (CTC) + forced alignment"
$PY train/aligner.py train --data "$W/data" --out "$W/ckpt/aligner.pt" --steps $STEPS --batch 8 --log 50 --save $STEPS
$PY train/aligner.py align --model "$W/ckpt/aligner.pt" --data "$W/data" --batch 8
head -c 300 "$W/data/alignments.jsonl"; echo
echo "== 5 TTS training"
$PY train/train_tts.py --data "$W/data" --out "$W/ckpt/tts" --steps $STEPS --batch 8 --log 50 --save $STEPS
echo "== 6 synthesize with a reference clip"
REF=$(ls "$W/data/clips" | head -1)
$PY train/synthesize.py --model "$W/ckpt/tts/latest.pt" --ref "$W/data/clips/$REF" --mode saudi --out "$W/out.wav" --gl-iters 20 "وِشْ رَايِكْ نْرُوحْ السُّوقْ بُكْرَة؟"
ls -la "$W/out.wav"
echo "smoke test passed"
