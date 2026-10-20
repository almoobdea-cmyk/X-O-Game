#!/usr/bin/env bash
# One-shot setup on a fresh GPU server (Ubuntu 22.04/24.04, NVIDIA driver installed). Run from the repo root.
#   bash arabic-tts/train/server-setup.sh
set -euo pipefail
sudo apt-get update -y && sudo apt-get install -y ffmpeg nodejs npm python3-venv git
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
# CUDA build of PyTorch (pick the CUDA tag that matches `nvidia-smi`; cu124 works on most 2024+ drivers)
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install numpy soundfile tqdm
cd arabic-tts && npm test && cd ..
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
# smoke test on the GPU (two minutes): proves ffmpeg + node + torch are wired before the long run
PYTHON=python STEPS=300 N=240 bash arabic-tts/train/smoke_test.sh
echo "ready: fill manifest.csv (media_path,subtitle_path,speaker_id,mode) and follow arabic-tts/train/README.md"
