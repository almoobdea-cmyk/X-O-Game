#!/usr/bin/env bash
# SADA Najdi recipe: download -> Najdi subset -> seed tashkeel -> diacritizer -> aligner -> TTS. One command, resumable.
#   KAGGLE_USERNAME=... KAGGLE_KEY=... ANTHROPIC_API_KEY=... bash arabic-tts/train/run_najdi.sh
# Scale knobs (defaults are for one GPU): HOURS (subset size), STEPS_ALIGN, STEPS_TTS, BATCH. For a CPU trial use
#   HOURS=2 STEPS_ALIGN=3000 STEPS_TTS=6000 BATCH=8
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
SADA=${SADA_ROOT:-./sada}
DATA=${DATA_DIR:-./data-najdi}
CK=${CKPT_DIR:-./ckpt-najdi}
HOURS=${HOURS:-40}
STEPS_ALIGN=${STEPS_ALIGN:-20000}
STEPS_TTS=${STEPS_TTS:-300000}
BATCH=${BATCH:-32}
mkdir -p "$CK"

if [ ! -d "$SADA" ] || [ -z "$(find "$SADA" -name '*.csv' | head -1)" ]; then
  echo "== download SADA (Kaggle; accept the dataset terms on its page first)"
  $PY train/sada.py download --dest "$SADA"
fi
echo "== inspect"
$PY train/sada.py inspect --root "$SADA" --dialect Najdi | tee "$CK/sada-inspect.txt"
if [ ! -f "$DATA/metadata.jsonl" ]; then
  echo "== build Najdi subset ($HOURS h)"
  $PY train/sada.py build --root "$SADA" --out "$DATA" --dialect Najdi --max-hours "$HOURS" --min-speaker-minutes 10
fi
if [ ! -f "$DATA/metadata.vocalized.jsonl" ]; then
  echo "== seed tashkeel with the skill prompt (data prep only)"
  $PY train/seed_tashkeel.py --in "$DATA/metadata.jsonl" --out "$DATA/metadata.vocalized.jsonl" --corpus "$DATA/diacritized.txt" --mode saudi
fi
if [ ! -f "$CK/diacritizer.pt" ]; then
  echo "== train the self-contained diacritizer"
  $PY train/diacritizer.py train --corpus "$DATA/diacritized.txt" --out "$CK/diacritizer.pt" --steps 20000 --log 500
  $PY train/diacritizer.py eval --model "$CK/diacritizer.pt" --corpus "$DATA/diacritized.txt"
fi
if [ ! -f "$CK/aligner.pt" ]; then
  echo "== CTC aligner"
  $PY train/aligner.py train --data "$DATA" --out "$CK/aligner.pt" --steps "$STEPS_ALIGN" --batch "$BATCH" --log 200 --save 2000
fi
if [ ! -f "$DATA/alignments.jsonl" ]; then
  $PY train/aligner.py align --model "$CK/aligner.pt" --data "$DATA" --batch "$BATCH"
fi
echo "== TTS (resumable)"
$PY train/train_tts.py --data "$DATA" --out "$CK/tts" --steps "$STEPS_TTS" --batch "$BATCH" --log 200 --save 2000 --resume
REF=$(ls "$DATA/clips" | head -1)
$PY train/synthesize.py --model "$CK/tts/latest.pt" --ref "$DATA/clips/$REF" --mode saudi --out "$CK/sample.wav" "وِشْ رَايِكْ نْرُوحْ السُّوقْ بُكْرَة؟ بَسْ خَلَاصْ، لَا تِزْعَلْ."
echo "sample at $CK/sample.wav"
