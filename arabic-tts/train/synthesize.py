"""Step 6: speak. Vocalized text + a reference clip of the speaker -> WAV, with the trained model only.

  python synthesize.py --model ckpt/tts/latest.pt --ref voice.wav --mode saudi --out out.wav "النصّ المشكّل"
"""
import argparse
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audio import load_audio, log_mel, griffin_lim, save_wav  # noqa: E402
from text import phonemize, encode  # noqa: E402
from tts_model import NataqTTS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('text'); ap.add_argument('--model', required=True); ap.add_argument('--ref', required=True)
    ap.add_argument('--mode', default='auto'); ap.add_argument('--out', default='out.wav'); ap.add_argument('--rate', type=float, default=1.0)
    ap.add_argument('--gl-iters', type=int, default=60)
    args = ap.parse_args()
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = NataqTTS().to(dev); model.load_state_dict(torch.load(args.model, map_location=dev)['model']); model.eval()
    ph = phonemize(args.text, args.mode)
    ids = encode(ph['phones'])
    ref = log_mel(load_audio(args.ref))[:400]
    phones = torch.tensor([ids], dtype=torch.long, device=dev); plen = torch.tensor([len(ids)], device=dev)
    refm = torch.from_numpy(ref).unsqueeze(0).to(dev); rlen = torch.tensor([ref.shape[0]], device=dev)
    mel, d, lens = model.infer(phones, plen, refm, rlen, rate=args.rate)
    mel = mel[0, :int(lens[0])].cpu().numpy()
    wav = griffin_lim(mel, n_iter=args.gl_iters)
    save_wav(args.out, wav)
    print(f"mode={ph['mode']} phones={len(ids)} frames={mel.shape[0]} ({mel.shape[0] * 12.5 / 1000:.2f}s) -> {args.out}")
    print(' '.join(f'{p}:{int(x)}' for p, x in zip(ph['phones'], d[0].tolist())))


if __name__ == '__main__':
    main()
