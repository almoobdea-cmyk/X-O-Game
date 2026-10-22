#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Package a Pocket TTS training run as a Phonon checkpoint folder.

Phonon's Rust runtime (`ptts/src/checkpoint.rs`) reads a flat `config.json`
(`ptts::tts_model::TTSConfig`), a Hugging Face `tokenizer.json`, `model.safetensors` /
`model.q8.gguf`, and voices under `voices/`. Pocket TTS training writes a nested YAML
config, a sentencepiece `.model` and an EMA `model.safetensors`. This script does the
config half and tells you the exact commands for the other two (they need the pocket-tts
venv for the tokenizer and a cargo build of xn-ptts for quantization and voices).

    uv run to_phonon.py --pocket-tts ~/pocket-tts --model-config pocket_tts/config/english.yaml \
        --override flow_lm.lookup_table.tokenizer_path=data/sada/tokenizer.model \
        --run runs/arabic_sada_student --out ~/models/phonon-ar

The flat<-nested key mapping was read off `ptts/tests/fixtures/config.json` (Phonon) against
`pocket_tts/config/english.yaml` (Pocket TTS): both describe the same 6-layer model.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import yaml


def set_path(d: dict, dotted: str, value) -> None:
    keys = dotted.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = yaml.safe_load(value) if isinstance(value, str) else value


def phonon_config(y: dict, languages: list[str]) -> dict:
    fl, mimi = y["flow_lm"], y["mimi"]
    tr, lut, flow = fl["transformer"], fl["lookup_table"], fl["flow"]
    sea, mtr, q = mimi["seanet"], mimi["transformer"], mimi["quantizer"]
    return {
        "flow_lm": {
            "d_model": tr["d_model"],
            "num_heads": tr["num_heads"],
            "num_layers": tr["num_layers"],
            "dim_feedforward": tr.get("dim_feedforward", tr["d_model"] * tr.get("hidden_scale", 4)),
            "max_period": float(tr.get("max_period", 10000)),
            "n_bins": lut["n_bins"],
            "lut_dim": lut["dim"],
            "flow_dim": flow["dim"],
            "flow_depth": flow["depth"],
            "ldim": mimi.get("inner_dim", q["dimension"]),
        },
        "mimi": {
            "channels": mimi.get("channels", 1),
            "sample_rate": mimi["sample_rate"],
            "frame_rate": mimi["frame_rate"],
            "dimension": sea["dimension"],
            "quantizer_dimension": q["dimension"],
            "quantizer_output_dimension": q["output_dimension"],
            "n_filters": sea["n_filters"],
            "n_residual_layers": sea["n_residual_layers"],
            "ratios": sea["ratios"],
            "kernel_size": sea["kernel_size"],
            "last_kernel_size": sea["last_kernel_size"],
            "residual_kernel_size": sea["residual_kernel_size"],
            "dilation_base": sea["dilation_base"],
            "compress": sea["compress"],
            "transformer_d_model": mtr["d_model"],
            "transformer_num_heads": mtr["num_heads"],
            "transformer_num_layers": mtr["num_layers"],
            "transformer_layer_scale": mtr["layer_scale"],
            "transformer_context": mtr["context"],
            "transformer_max_period": float(mtr.get("max_period", 10000)),
            "transformer_dim_feedforward": mtr["dim_feedforward"],
            "downsample_channel_wise": False,
        },
        "lsd_decode_steps": 1,          # pocket_tts DEFAULT_SAMPLER_DECODE_STEPS
        "eos_threshold": -4.0,          # pocket_tts DEFAULT_EOS_THRESHOLD; sweep -2..-6 on your model
        "model_id": None,               # null = Pocket TTS conventions (tanh GELU, rms_var time norm)
        "audio_prompt_min_duration": 10.0,
        "audio_prompt_max_duration": 10.0,
        "cfg_null_audio_empty": False,
        "speaker_mimi": None,
        "conditioners": [],
        "fuser": None,
        "voices": [],
        "languages": languages,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pocket-tts", type=Path, required=True, help="pocket-tts checkout")
    ap.add_argument("--model-config", default="pocket_tts/config/english.yaml", help="model_config of the training YAML, relative to --pocket-tts")
    ap.add_argument("--override", action="append", default=[], help="model_overrides as key.path=value (repeatable)")
    ap.add_argument("--run", type=Path, required=True, help="run_dir holding model.safetensors (EMA weights)")
    ap.add_argument("--out", type=Path, required=True, help="Phonon checkpoint folder to create")
    ap.add_argument("--tokenizer-model", type=Path, default=None, help="sentencepiece .model (default: the override's tokenizer_path)")
    ap.add_argument("--languages", default="ar")
    args = ap.parse_args()

    y = yaml.safe_load((args.pocket_tts / args.model_config).read_text())
    for ov in args.override:
        k, v = ov.split("=", 1)
        set_path(y, k, v)
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = phonon_config(y, [l for l in args.languages.split(",") if l])
    (args.out / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"wrote {args.out / 'config.json'}")

    weights = args.run / "model.safetensors"
    if weights.exists():
        shutil.copy2(weights, args.out / "model.safetensors")
        print(f"copied {weights} -> {args.out / 'model.safetensors'}")
    else:
        print(f"!! {weights} not found: training writes it as the EMA checkpoint; copy it in by hand")

    spm = args.tokenizer_model or Path(str(y["flow_lm"]["lookup_table"].get("tokenizer_path", "")))
    print(
        "\nNext, from the pocket-tts checkout (exact conversion, checked against sentencepiece):\n"
        f"  uv run -m training.scripts.convert_tokenizer {spm} --out {args.out / 'tokenizer.json'} --texts data/sada/valid.jsonl\n"
        "Then, from the xn-ptts checkout:\n"
        f"  cargo run --release -p ptts --example quantize -- {args.out / 'model.safetensors'} {args.out / 'model.q8.gguf'} --quant q8_0\n"
        f"  mkdir -p {args.out / 'voices'}\n"
        f"  cargo run --release -p ptts --example create_voice --features audio -- --model {args.out} --input speaker.wav --output {args.out / 'voices' / 'NAME.safetensors'}\n"
        f"  cp {args.out / 'voices' / 'NAME.safetensors'} {args.out / 'default-voice.safetensors'}\n"
        "Test:\n"
        f"  ptts --model {args.out} --lang none --quant q8 --voice NAME \"مرحبا بالعالم\" -o out.wav\n"
        "(--lang none: Phonon has no Arabic normalizer; apply prepare_sada.normalize_text to the input yourself.)"
    )


if __name__ == "__main__":
    main()
