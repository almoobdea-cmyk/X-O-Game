#!/usr/bin/env bash
# One-shot Phonon setup for Mac or Linux: installs the `ptts` command, fetches the default
# model on first run, synthesizes a test sentence and plays it.
#
#   bash setup.sh                      # "Hello world" with the Freya voice -> out.wav
#   bash setup.sh "Some text" Zoey     # other text / voice
#   MODEL_DIR=~/models/phonon-31m-en bash setup.sh   # use a local model folder instead of the Hub
#
# Needs network access to github.com (binary), crates.io (if building with cargo) and
# huggingface.co (model + voice). Nothing needs sudo.
set -euo pipefail

TEXT="${1:-Hello world}"
VOICE="${2:-Freya}"
OUT="${OUT:-out.wav}"
VERSION="${PTTS_VERSION:-0.4.1}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"

say() { printf '\n==> %s\n' "$*"; }

target() {
  local os arch
  os="$(uname -s)"; arch="$(uname -m)"
  case "$os-$arch" in
    Darwin-arm64)            echo aarch64-apple-darwin ;;
    Darwin-x86_64)           echo x86_64-apple-darwin ;;
    Linux-x86_64)            echo x86_64-unknown-linux-gnu ;;
    Linux-aarch64|Linux-arm64) echo aarch64-unknown-linux-gnu ;;
    *) echo "unsupported platform $os $arch; build from source: cargo install ptts --locked --features cli" >&2; exit 1 ;;
  esac
}

install_ptts() {
  if command -v ptts >/dev/null 2>&1 && ptts --version 2>/dev/null | grep -q '^ptts '; then
    say "ptts already installed: $(ptts --version)"; return
  fi
  if command -v cargo >/dev/null 2>&1; then
    say "building ptts $VERSION with cargo (a few minutes)"
    cargo install ptts --version "$VERSION" --locked --features cli
    export PATH="$HOME/.cargo/bin:$PATH"; return
  fi
  if [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null 2>&1; then
    say "installing ptts from Gradium's Homebrew tap"
    brew install gradium-ai/tap/ptts; return
  fi
  local t name url
  t="$(target)"; name="ptts-$VERSION-$t"
  url="https://github.com/gradium-ai/xn-ptts/releases/download/v$VERSION/$name.tar.gz"
  say "downloading prebuilt $name"
  mkdir -p "$BIN_DIR"
  tmp="$(mktemp -d)"
  curl -fsSL "$url" -o "$tmp/$name.tar.gz"
  curl -fsSL "https://github.com/gradium-ai/xn-ptts/releases/download/v$VERSION/SHA256SUMS" -o "$tmp/SHA256SUMS" || true
  if [ -s "$tmp/SHA256SUMS" ]; then
    (cd "$tmp" && { sha256sum --ignore-missing -c SHA256SUMS 2>/dev/null || shasum -a 256 --ignore-missing -c SHA256SUMS; })
  fi
  tar -xzf "$tmp/$name.tar.gz" -C "$tmp"
  install -m 755 "$tmp/$name/ptts" "$BIN_DIR/ptts"
  rm -rf "$tmp"
  export PATH="$BIN_DIR:$PATH"
  case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "add $BIN_DIR to your PATH" ;; esac
}

synthesize() {
  local model_args=()
  if [ -n "${MODEL_DIR:-}" ]; then
    [ -f "$MODEL_DIR/config.json" ] || { echo "MODEL_DIR=$MODEL_DIR has no config.json" >&2; exit 1; }
    model_args=(--model "$MODEL_DIR")
  else
    say "no MODEL_DIR set: ptts downloads gradium/phonon-31m-en from Hugging Face on first run and caches it"
  fi
  say "synthesizing \"$TEXT\" with voice $VOICE -> $OUT"
  ptts "${model_args[@]}" --lang en --quant q8 --voice "$VOICE" "$TEXT" -o "$OUT"
}

verify_and_play() {
  say "checking $OUT"
  command -v file >/dev/null 2>&1 && file "$OUT"
  python3 - "$OUT" <<'PY' 2>/dev/null || true
import sys, wave
w = wave.open(sys.argv[1]); print(f"{w.getnframes()/w.getframerate():.2f} s, {w.getnchannels()} ch, {w.getframerate()} Hz")
PY
  say "playing"
  if command -v afplay >/dev/null 2>&1; then afplay "$OUT"
  elif command -v aplay >/dev/null 2>&1; then aplay -q "$OUT"
  elif command -v paplay >/dev/null 2>&1; then paplay "$OUT"
  elif command -v ffplay >/dev/null 2>&1; then ffplay -nodisp -autoexit -loglevel quiet "$OUT"
  else echo "no player found; open $OUT in any audio player"; fi
}

install_ptts
synthesize
verify_and_play
say "done. Change the voice with: ptts --lang en --quant q8 --voice Zoey \"$TEXT\" -o $OUT   (ptts --list-voices shows them all)"
