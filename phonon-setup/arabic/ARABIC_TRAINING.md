# Training Phonon on Arabic with SDAIA's SADA corpus

Status of this folder: a complete, runnable recipe plus the two scripts that are specific
to SADA and to Phonon. No training was run here: the cloud session has 4 CPU cores, no
GPU, and its network policy denies huggingface.co and kaggle.com, so neither the data nor
the base weights can be fetched from it. Everything below is written to be run on a
machine with an NVIDIA GPU.

## Facts this plan rests on

- Phonon's repository (`gradium-ai/xn-ptts`) is an inference runtime only. It contains no
  training code. Its README says it "builds heavily on" Kyutai's Pocket TTS and that
  Pocket TTS checkpoints load when they supply their own config, tokenizer JSON, weights
  and voices. The config structs (`ptts/src/tts_model.rs`), the weight-key remapping
  (`ptts/src/loader.rs`, `remap_key`, which renames `flow_lm.backbone.*` to
  `flow_lm.transformer.*` and so on) and the test fixture `ptts/tests/fixtures/config.json`
  all match Pocket TTS's `english.yaml` architecture.
- Kyutai published the full Pocket TTS training stack (`kyutai-labs/pocket-tts`,
  `training/`): data prep, CTC forced alignment, tokenizer training, a 24-layer teacher,
  depth distillation to a 6-layer student, and WER/speaker-similarity/UTMOS evaluation.
  It has a config made for exactly this case, `finetune_language.yaml`: start from the
  English teacher with a fresh text embedding for a new tokenizer. On Czech it matched a
  from-scratch run's WER about 2.5x sooner.
- SDAIA's SADA (Saudi Audio Dataset for Arabic) is an ASR corpus from the Saudi
  Broadcasting Authority: about 667 h of 16 kHz mono WAV in 4,563 episode files, with
  `train.csv` (about 418 h), `valid.csv` and `test.csv` (about 10 h each) giving
  `FileName, SegmentStart, SegmentEnd, SpeakerID, SpeakerGender, SpeakerAge,
  SpeakerDialect, Environment, GroundTruthText, ProcessedText`. Mostly Saudi dialects
  (Najdi, Hijazi, Khaliji, ...) with some MSA, Egyptian, Levantine and Yemeni. License
  CC BY-NC-SA 4.0: research and non-commercial use only, and derived models should carry
  the same terms. Hosted on Kaggle (`sdaiancai/sada2022`) and IEEE DataPort.
- SDAIA has not published an open Arabic TTS model or a TTS-grade corpus. SawtArabi
  (SDAIA with HUMAIN, Interspeech 2025) is a 4 h single-speaker evaluation set. So "train
  on SDAIA open source" means SADA, an ASR corpus, which is noisier and more
  multi-speaker than a TTS corpus. Expect a model that speaks Saudi-dialect Arabic in
  broadcast quality, not studio quality, unless you add cleaner data (ClArTTS, 12 h of
  classical Arabic, one speaker; Common Voice Arabic; your own recordings).

## Hardware and time

| Stage | Compute | Wall time |
|---|---|---|
| Latent precompute | any GPU | ~50 min per 2000 h on one H100 |
| Teacher fine-tune (24 layers, 250k steps, batch 64) | 1 x H100 80 GB, or 1 x 24 GB GPU at batch 16 x 4 accumulation | ~11 h on 1 H100, ~5 h on 8 |
| Distillation (6 layers, 200k steps) | 1 x H100 | ~5 h |
| Alignment of 418 h with wav2vec2 | 1 GPU | 1 to 3 h |

Disk: about 60 GB per 1000 h of prepared audio plus the SADA download itself.

## Steps

### 1. Get the data and the base model

```sh
git clone https://github.com/kyutai-labs/pocket-tts.git && cd pocket-tts
uv sync                                   # training deps live in the dev group
kaggle datasets download -d sdaiancai/sada2022 -p data/sada_raw --unzip
export HF_TOKEN=...                       # Kyutai's weights and the aligner come from HF
```

### 2. Build manifests with `prepare_sada.py`

```sh
cp /path/to/phonon-setup/arabic/*.py /path/to/phonon-setup/arabic/*.yaml .
uv run prepare_sada.py data/sada_raw --out data/sada --strip-diacritics
```

What it does, and why:
- Keeps `train.csv` and `valid.csv` rows as `{path, start, duration, transcript,
  speaker, dialect}` lines, the Pocket TTS manifest format. Audio is referenced in
  place, never cut.
- Drops segments shorter than 1.5 s or longer than 30 s (`max_duration_sec`), rows
  whose dialect is "More than 1 speaker" or "Unknown", rows with digits (nobody has an
  Arabic number verbalizer in this pipeline; add `num2words(lang="ar")` to
  `normalize_text` if you want to keep them), rows with no Arabic letters, and rows whose
  WAV is missing or whose window runs past the end of the file.
- Normalizes text: NFC, tatweel removed, Unicode quotes and dashes unified,
  diacritics optionally stripped. Phonon has no Arabic normalizer (`ptts/src/preprocess.rs`
  only knows en, fr, de, es, pt), so inference will use `--lang none` and you must apply
  this same normalization to input text yourself.
- Reports hours kept per dialect and counts per drop reason. Use `--environments Clean`
  and `--dialects Najdi,Hijazi,ModernStandardArabic` to trade hours for quality.
- Column names are matched case-insensitively against the header; if your copy of SADA
  spells them differently pass `--col-filename`, `--col-segmentstart`, and so on.

Expect roughly 150 to 300 usable hours after filtering. That is above Kyutai's 100 h
minimum and below the 1000 h they recommend for a strong model.

### 3. Forced alignment (required, not optional, for SADA)

The loader cuts each utterance between two aligned words: audio before the cut is the
voice prompt, audio after it is the target. Without `words`, the voice prompt is a random
window of the same file, and in SADA the same episode file holds many speakers, so the
model would learn to ignore the voice prompt. Align with an Arabic character-level CTC
model:

```sh
uv run -m training.scripts.align_data data/sada/train.jsonl data/sada/train_aligned.jsonl \
    --model jonatasgrosman/wav2vec2-large-xlsr-53-arabic --device cuda
uv run -m training.scripts.align_data data/sada/valid.jsonl data/sada/valid_aligned.jsonl \
    --model jonatasgrosman/wav2vec2-large-xlsr-53-arabic --device cuda
```

`align_data.py` folds the transcript to the CTC model's vocabulary; check its log for the
share of unaligned words. If it is high, strip diacritics (the XLSR Arabic vocabularies
are undiacritized) and consider `elgeish/wav2vec2-large-xlsr-53-arabic` as an alternative.

### 4. Tokenizer

```sh
uv run -m training.scripts.train_tokenizer data/sada/tokenizer data/sada/train.jsonl \
    --character-coverage 1.0
```

Unigram, vocab 4000 (equals `lookup_table.n_bins`, so no config change), byte fallback,
identity normalization. Coverage 1.0 keeps every Arabic letter as a piece instead of
falling back to bytes.

### 5. Train the teacher, then distil

```sh
uv run training/train.py finetune_arabic.yaml                      # 24-layer teacher
uv run training/train.py depth_distill_arabic.yaml                 # 6-layer student
```

Both YAMLs are in this folder and point at `data/sada/*` and `runs/arabic_sada_*`. For
multiple GPUs: `uv run torchrun --nproc-per-node 8 training/train.py finetune_arabic.yaml`
with `batch_size: 8`. Watch `progress.jsonl`: flow_loss near 0.35 to 0.4 by 2k steps,
intelligibility improving from about 15k steps.

Listen to `runs/.../samples/` as training goes; also generate with the Python runtime:

```sh
uv run pocket-tts generate --config pocket_tts/config/english_2026-04_24l.yaml \
    --checkpoint runs/arabic_sada_teacher/checkpoint_00050000.pt \
    --voice speaker.wav --text "مرحبا بكم في البرنامج"
```

(The config only supplies the architecture and Mimi weights; override
`flow_lm.lookup_table.tokenizer_path` to `data/sada/tokenizer.model` the same way the
training YAML does, for example by copying the YAML and editing it.)

### 6. Evaluate

WER with an Arabic ASR (`openai/whisper-large-v3` with `language="ar"`, or
`nvidia/parakeet` Arabic variants; compare after the same normalization), speaker
similarity (WavLM, language-independent) and UTMOS (less calibrated for Arabic). Use
SADA's `test.csv` transcripts as prompts and a held-out speaker as the voice.

### 7. Package for Phonon with `to_phonon.py`

```sh
uv run to_phonon.py --pocket-tts . --model-config pocket_tts/config/english.yaml \
    --override flow_lm.lookup_table.tokenizer_path=data/sada/tokenizer.model \
    --run runs/arabic_sada_student --out ~/models/phonon-ar --languages ar
```

It writes `config.json` in Phonon's flat schema (checked here: on Kyutai's `english.yaml`
it reproduces `ptts/tests/fixtures/config.json` field for field), copies the EMA
`model.safetensors`, and prints the remaining commands:

- `training/scripts/convert_tokenizer.py` for `tokenizer.json` (exact conversion, verified
  against sentencepiece; `xn-ptts/scripts/convert-tokenizer.py` is the Phonon-side
  equivalent).
- `cargo run --release -p ptts --example quantize -- model.safetensors model.q8.gguf --quant q8_0`
  for the fast CPU weights.
- `cargo run --release -p ptts --example create_voice --features audio -- --model DIR --input speaker.wav --output DIR/voices/NAME.safetensors`
  to make voice files from about 10 s of a SADA speaker (needs the f32 weights, which
  carry the Mimi encoder). Clone only speakers you have consent for; SADA's license is
  non-commercial.

Then:

```sh
ptts --model ~/models/phonon-ar --lang none --quant q8 --voice NAME "مرحبا بكم" -o out.wav
```

### 8. Things to verify on the first real run

- That Phonon loads the student with no "unused tensor" error (`loader::remap_key` covers
  the released Pocket TTS layout; a newer training run could add a key). If it fails, the
  Python runtime still works, and `ptts-pyo3` is not needed for that.
- `eos_threshold` in `config.json`: -4.0 is Pocket TTS's default; sweep -2 to -6 if
  output truncates or runs on.
- Phonon's text chunker (`ptts/src/plan.rs`) splits on sentence punctuation; Arabic
  question mark and comma (؟ ،) may not be in its list, so long inputs may form one big
  chunk capped at 50 tokens. Check `plan::chunks` and add them if needed.
- Right-to-left text is irrelevant to the model (it sees code points in logical order),
  but keep inputs free of bidi control characters.

## Lighter alternatives if 418 h of broadcast audio is too much

- Fine-tune a released multilingual-ish teacher on ClArTTS alone (12 h, one speaker):
  intelligible single-voice MSA, no dialects, no cloning diversity.
- Use SADA only for the clean, single-speaker subset (`--environments Clean`) plus
  ClArTTS, then distil. Fewer hours, better acoustic quality.
