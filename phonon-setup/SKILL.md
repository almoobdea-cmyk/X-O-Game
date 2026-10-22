---
name: phonon-tts
description: Install and run Phonon, Gradium's on-device text-to-speech (the `ptts` Rust CLI from github.com/gradium-ai/xn-ptts). Use when the user asks to set up Phonon/ptts, synthesize speech to a WAV, pick or change a voice, point ptts at a local model folder, or embed Phonon in Rust/Python.
---

# Phonon (ptts) skill

Phonon is a Rust TTS runtime: text -> tokenizer -> flow-matching LM -> Mimi codec
latents -> 24 kHz mono PCM. No PyTorch at inference. Read the repo README first and
follow it over anything you assume: https://github.com/gradium-ai/xn-ptts

## 1. Install the CLI (from source)

```sh
git clone https://github.com/gradium-ai/xn-ptts.git
cd xn-ptts
cargo install --path ptts --locked --features cli   # installs ~/.cargo/bin/ptts
ptts --version
```

- `--features cli` is required: without it there is no `ptts` command to install.
- `.cargo/config.toml` pins `target-cpu=native`; the binary is not portable to other CPUs.
- Prebuilt binaries: GitHub Releases, or `brew install gradium-ai/tap/ptts`.
- Rust library instead: `cargo add ptts --features hf,hub`. Python: `pip install ptts`.

## 2. Model folder (MODEL_DIR)

A checkpoint is one folder:

```
MODEL_DIR/
  config.json          # TTSConfig: flow_lm, mimi, eos_threshold, languages, ...
  tokenizer.json       # Hugging Face tokenizers JSON (never bundled or guessed)
  model.q8.gguf        # q8_0 weights (CPU, fastest)   -- use with --quant q8
  model.safetensors    # f32 weights (CPU/GPU; also carries the speaker encoder)
  voices/NAME.safetensors   # voice embeddings ("emb" or "speaker_wavs" tensors)
  default-voice.safetensors # optional: the voice used when --voice is omitted
```

Get the default model from Hugging Face (`gradium/phonon-31m-en`, Apache 2.0) with
`hf download gradium/phonon-31m-en --local-dir MODEL_DIR`, or let `ptts` download and
cache it by passing no `--model` (needs network to huggingface.co). Phonon 40m models
(`gradium/phonon-40m-{en,fr,de,es,pt,multilingual}`) are gated: accept the terms on the
model page and set `HF_TOKEN`.

```sh
export MODEL_DIR=/path/to/phonon-31m-en
```

## 3. Synthesize

```sh
ptts --model "$MODEL_DIR" --lang en --quant q8 --voice Freya "Hello world" -o out.wav
```

Flags that matter:

| Flag | Meaning |
|---|---|
| `--model` | local folder, `config.json`, or `hf://OWNER/MODEL[@COMMIT]` (default: Phonon 31m) |
| `--lang en|fr|de|es|pt|none` | required; selects text normalization, `none` passes text as written |
| `--quant q8` | load `model.q8.gguf` (CPU only); omit for f32 `model.safetensors` |
| `--voice NAME` | checkpoint voice, voice-catalog voice, `.safetensors` voice file, or ~10 s audio to clone (needs a speaker encoder; Phonon models on HF have none) |
| `--weights FILE` | pick a weights file inside the model folder |
| `--condition duration_delta=-0.3` | faster speech; `0.3` slower; 0 default |
| `--device auto|cpu|cuda|vulkan|metal` | backend; quantized weights always run on CPU |
| `--threads N` | CPU tuning |
| `--list-voices` | list the voice catalog with each voice's language |

Verify the output: `file out.wav` should report "RIFF ... WAVE audio, mono 24000 Hz";
`python3 -c "import wave; w=wave.open('out.wav'); print(w.getnframes()/w.getframerate(), 's')"`
should print a positive duration. Play with `aplay out.wav`, `afplay out.wav` (Mac), or `ffplay`.

## 4. Change the voice

1. Bundled voice of the checkpoint: `--voice NAME` where NAME is a file in `MODEL_DIR/voices/`
   or `MODEL_DIR/embeddings/` without the `.safetensors` suffix. Omit `--voice` for `default`.
2. Catalog voice: any name from `ptts --list-voices` (catalog `gradium/phonon-voices` on
   Hugging Face). Names match case- and accent-insensitively, or by voice ID. Only that one
   voice file is downloaded, on first use. Pick a voice in the language of the text.
3. Voice file: `--voice /path/to/voice.safetensors` (downloaded from Gradium Studio, or
   from `scripts/download-voice.py` / `scripts/clone-voice.py` with a Gradium API key).
   To use it by name later, copy it to `MODEL_DIR/voices/NAME.safetensors`.
4. Offline catalog: `--voice-catalog /folder/with/voices.jsonl` (one `{"name","filename"}`
   JSON object per line).

## 5. Troubleshooting

- `no voice 'X'`: the model has no such voice and the catalog lookup failed (offline?). Use a
  name from `MODEL_DIR/voices/` or a `.safetensors` path.
- `no weights in ...`: with `--quant q8` the folder needs `model.q8.gguf`; without it,
  `model.safetensors`. Or pass `--weights`.
- "text is normalized as X, but the model was trained for Y": `--lang` disagrees with
  `config.json`'s `languages`; it is a warning, not an error.
- Network blocked: everything works from a local folder; only `hf://` sources and the voice
  catalog need huggingface.co.

## 6. Library and server quick refs

Rust:
```rust
let checkpoint = ptts::checkpoint::Checkpoint::locate(model_dir, ResolveOptions { quant: Quant::Q80, weights: None })?;
let mut tts = checkpoint.builder(Lang::En).device(DeviceKind::Cpu).build()?;
checkpoint.register_voices(&mut tts);
let pcm = tts.say("Hello world")?;
ptts::wav::write_wav_file("out.wav", &pcm, tts.sample_rate())?;
```
Python: `tts = ptts.TTS(model_dir, lang="en"); tts.save("out.wav", "Hello world")`.
Server: `docker run -p 127.0.0.1:8880:8880 -e PTTS_LANG=en -e PTTS_QUANT=q8 ghcr.io/gradium-ai/ptts-openai-server:latest`
then POST `/v1/audio/speech`.
