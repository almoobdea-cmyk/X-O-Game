"""Step 5: train the TTS model. Resumable.

  python train_tts.py --data data/ --out ckpt/tts --steps 500000 --batch 32 [--resume]
"""
import argparse
import os
import sys
import time

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataset import ClipDataset, collate  # noqa: E402
from tts_model import NataqTTS, tts_loss  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--steps', type=int, default=500000); ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--lr', type=float, default=5e-4); ap.add_argument('--log', type=int, default=100); ap.add_argument('--save', type=int, default=2000)
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    ds = ClipDataset(args.data, need_durations=True)
    if not len(ds):
        sys.exit('no aligned clips: run aligner.py align first')
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True, collate_fn=collate, num_workers=0, drop_last=True)
    model = NataqTTS().to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(0.9, 0.98), weight_decay=0.01)
    step = 0; latest = os.path.join(args.out, 'latest.pt')
    if args.resume and os.path.exists(latest):
        ck = torch.load(latest, map_location=dev); model.load_state_dict(ck['model']); opt.load_state_dict(ck['opt']); step = ck['step']
        print(f'resumed at step {step}')
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 4000) * max(0.1, 0.5 ** (s / 200000)))
    print(f'tts: {len(ds)} clips, {len(ds.speakers)} speakers, {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M params, device {dev}')
    t0 = time.time(); model.train()
    while step < args.steps:
        for batch in dl:
            batch = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in batch.items()}
            mel, mel_post, log_d = model(batch['phones'], batch['plen'], batch['ref'], batch['rlen'], batch['durations'], batch['mlen'])
            loss, parts = tts_loss(mel, mel_post, log_d, batch)
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step()
            step += 1
            if step % args.log == 0 or step == 1:
                print(f"step {step} loss {loss.item():.3f} mel {parts['mel']:.3f} post {parts['post']:.3f} dur {parts['dur']:.3f} lr {sched.get_last_lr()[0]:.2e} ({time.time() - t0:.0f}s)")
            if step % args.save == 0 or step >= args.steps:
                torch.save({'model': model.state_dict(), 'opt': opt.state_dict(), 'step': step}, latest)
                if step % (args.save * 10) == 0:
                    torch.save({'model': model.state_dict(), 'step': step}, os.path.join(args.out, f'step{step}.pt'))
            if step >= args.steps:
                break
    print(f'done at step {step}; checkpoint {latest}')


if __name__ == '__main__':
    main()
