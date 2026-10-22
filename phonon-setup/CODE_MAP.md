# Phonon (xn-ptts) code map

How this was produced: the REA skill's own routing rule says that a complete source
repository is analysed with ordinary repository tools, and that its readiness and provider
commands are not run for that case. No REA MCP server is registered in this session either,
and registering one writes client configuration, which needs approval. So this map comes
from reading the source at `/home/user/phonon/xn-ptts` (commit of 2026-10-22, v0.4.1),
with REA's discipline kept: every statement below is marked as **observed** (read in the
source) or **inferred** (a conclusion drawn from it). Nothing here observed execution with
real weights, because the model could not be downloaded in this environment. The one REA
route that does apply to Phonon is its shipped binary: `inspect_rust_binary` on
`~/.cargo/bin/ptts` would list its cargo-auditable dependency tree, and
`inspect_binary_layout` its ELF sections and mitigations. Both need the REA server.

## 1. What the program is (observed)

Text -> normalization -> tokenizer -> flow-matching transformer that emits Mimi codec
latents, one 80 ms frame at a time -> Mimi decoder -> 24 kHz mono f32 PCM. Streaming
end to end: frames are decoded as they are produced. Rust on the `xn` tensor runtime; no
PyTorch at inference (`ptts/src/lib.rs` header, `README.md`).

Workspace (`Cargo.toml`, `CLAUDE.md`): `ptts` (library + CLI behind the `cli` feature),
`ptts-pyo3` (Python wheel), `ptts-wasm` (npm `phonon-tts`), `ptts-ws-server` and
`ptts-openai-server` (HTTP/WebSocket servers), `ptts-coreml` and `ptts-ffi` (Apple Neural
Engine and the C ABI for iOS/Android), `qnn/` (Snapdragon NPU).

## 2. Layer by layer, bottom up

| Layer | Files | Role (observed) |
|---|---|---|
| Tensor runtime | external crate `xn` | CPU kernels (AVX/NEON/wasm SIMD, optional KleidiAI), CUDA/Vulkan/Metal/WebGPU backends, GGUF q8_0/q4k quantized linears. |
| Codec | `mimi.rs`, `seanet.rs`, `conv.rs`, `resample.rs`, `transformer.rs`, `dummy_quantizer.rs` | Mimi: SEANet conv encoder/decoder around a small transformer, 12.5 Hz frames, 24 kHz audio. The decoder is what synthesis uses; the encoder only embeds a voice prompt from ~10 s of audio. The vector quantizer is replaced by a pass-through (`dummy_quantizer.rs`) because the LM predicts continuous latents. |
| Flow LM | `flow_lm.rs`, `transformer.rs`, `rope.rs`, `mlp.rs`, `layer_scale.rs`, `conditioners.rs` | A causal transformer (`d_model` 1024, 6 layers in the 31m/Pocket shape) over text tokens + voice embedding, plus `SimpleMLPAdaLN` flow head that denoises a 32-dim latent per frame in `lsd_decode_steps` (1) solver steps. Optional `conditioners` (`lut` or `continuous`, e.g. `duration_delta`) are summed into every frame input. |
| Orchestrator | `tts_model.rs` (`TTSModel<Q>`) | Owns `flow_lm` and `mimi`. Primitives: `init_flow_lm_state`, `prompt_text`, `prompt_audio`, step-decode a frame, `MimiDecoderState`. `MAX_TOKENS_PER_CHUNK = 50`. Generic over `Q: BackendQ` (weight format + device). |
| Planning | `plan.rs` | `chunks()`: normalize the whole text, group whole sentences into chunks of at most 50 tokens, split on `.`, `!`, `?` (line 265). `fit()` cuts oversized chunks at sentence/comma/word boundaries. Also the EOS policy and KV/frame budgets. |
| One-call API | `synth.rs` (`Synth`, `SynthBuilder`, `SynthApi`, `Session`) | Loads a checkpoint, picks device and quant, registers voices, and runs the flow LM and the Mimi decoder on two threads with a channel between them. `say()` collects, `stream()` yields PCM chunks. `Q` is erased behind `Box<dyn SynthApi>` so a CLI flag picks the weight format. Not built on wasm (no threads). |
| Text front end | `preprocess.rs`, `preprocess/rewrite.rs`, `preprocess/rewrite/*` | `Normalize::For(Lang)` or `Off`, a required argument everywhere. Character pass (accent folding, symbols) then per-word rewrite rules (numbers, currency, emails, URLs, abbreviations...). `Lang` is exactly `En, Fr, De, Es, Pt` (line 92). |
| Tokenizer | `tok.rs` | Thin wrapper over Hugging Face `tokenizers`; each checkpoint ships its own `tokenizer.json`, nothing is bundled or guessed. |
| Weights and voices | `loader.rs` | safetensors/GGUF loading; `remap_key` renames Pocket TTS keys (`flow_lm.backbone.*` -> `flow_lm.transformer.*`, speaker projection, conditioner) and drops VQ keys. Voices: `voices/*.safetensors`, `embeddings/*.safetensors`, `default-voice.safetensors`; a voice file holds an `emb` tensor or raw `speaker_wavs` latents that go through the speaker projection. |
| Checkpoint resolution | `checkpoint.rs`, `hub.rs`, `voice_catalog.rs` | One string names a model: a folder, a `config.json`, or `hf://owner/name[@commit]`. `DEFAULT_MODEL` is `gradium/phonon-31m-en` pinned to a commit. Weight candidates by quant: `model.q8.gguf` then `model.safetensors`. The voice catalog (`voices.jsonl`, default `gradium/phonon-voices`) is consulted only for a name the checkpoint lacks, and downloads just that one file. |
| CLI | `src/bin/ptts/main.rs` | clap over all of the above. `VoiceArg` parses `--voice` as a name, a `.safetensors` path, or an audio file to clone (needs the speaker encoder in f32 weights). |
| Examples | `examples/say.rs`, `bench.rs`, `quantize.rs`, `create_voice.rs`, `export_coreml.rs` | Minimal call; RTF/TTFB benchmark; safetensors -> GGUF (only the four transformer linears per layer are quantized); audio -> voice file; Core ML export. |

## 3. Request flow, `ptts --model DIR --lang en --quant q8 --voice Freya "Hello world"` (observed, traced through the source)

1. `main.rs` builds a `VoiceCatalog` (lazy, no network yet) and calls
   `Checkpoint::locate(model, ResolveOptions{quant: Q80, ..})`.
2. `checkpoint.rs::resolve` canonicalizes the folder, reads `config.json` into `TTSConfig`,
   picks `model.q8.gguf`, notes `tokenizer.json`, and lists voice files.
3. `checkpoint.builder(Lang::En)` -> `SynthBuilder` -> `build()` loads weights through
   `loader.rs` into `TTSModel<Q8>` on the chosen device, emits a `tracing` warning if
   `config.languages` lacks `en`.
4. `checkpoint.register_voices(&mut tts)` registers bundled voices. If `Freya` is not among
   them, `VoiceCatalog::register` downloads `voices.jsonl` and `Freya`'s file from the Hub.
   The voice embedding is computed once per `Synth`.
5. `tts.say(text)`: `plan::chunks` normalizes and splits; for each chunk the flow-LM thread
   prompts text + voice, then step-decodes latents until the EOS head crosses
   `eos_threshold` (-4.0) or the frame budget; the Mimi thread decodes queued frames.
6. `wav::write_wav_file` writes 16-bit mono 24 kHz WAV.

## 4. Inferences that matter for the Arabic work

- **Inferred:** nothing in the runtime is language-specific except `preprocess.rs` and the
  sentence splitter's punctuation list. An Arabic model therefore runs with `--lang none`
  (text handed to the tokenizer as written) and a tokenizer trained on Arabic text.
  Adding `Lang::Ar` would mean a new `SpecialChars` table, `fold` rules and rewrite rules,
  and ideally `؟` and `،` in `plan.rs`'s splitter.
- **Inferred:** checkpoint compatibility with Pocket TTS is deliberate and maintained:
  `remap_key` exists for Pocket TTS key names, `model_id: null` selects Pocket TTS's
  GELU and time-norm variants, and the test fixture `tests/fixtures/config.json` is
  Pocket TTS's `english.yaml` flattened. A model trained with Kyutai's `training/` code
  should load after packaging (see `arabic/to_phonon.py`).
- **Inferred:** quality knobs at inference are `--temperature` (0.3), `--cfg-coef`,
  `--condition duration_delta=`, `eos_threshold` in the config, and the voice file; the
  model itself is fixed.

## 5. Build and verification done here (observed)

- `cargo install --path ptts --locked --features cli` succeeded: `ptts 0.4.1` at
  `~/.cargo/bin/ptts`, built with `target-cpu=native` (not portable).
- `ptts --model $MODEL_DIR ...` fails with "cannot read config .../config.json" because the
  model folder is empty; `ptts` without `--model` fails with "cannot fetch config.json from
  hf://gradium/phonon-31m-en@8c64b55e..." because this environment's network policy denies
  `huggingface.co`. No `out.wav` was produced.
- The crate's unit tests (no weights needed) were run as a stand-in check; result in the
  session report.
