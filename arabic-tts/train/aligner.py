"""Step 4: link sound to letters. A CTC acoustic model trained on the clips, then forced alignment -> per-phone durations.

  python aligner.py train --data data/ --out ckpt/aligner.pt --steps 20000
  python aligner.py align --model ckpt/aligner.pt --data data/
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataset import ClipDataset, collate  # noqa: E402
from text import PHONES, BLANK, PAD  # noqa: E402


class CTCAligner(nn.Module):
    """Mel (T,80) -> log-probs over phones at half frame rate (25 ms)."""
    def __init__(self, n_mels=80, hidden=256, vocab=len(PHONES)):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(n_mels, hidden, 5, padding=2), nn.GELU(),
            nn.Conv1d(hidden, hidden, 5, stride=2, padding=2), nn.GELU(),
            nn.Conv1d(hidden, hidden, 5, padding=2), nn.GELU())
        self.rnn = nn.GRU(hidden, hidden, num_layers=2, bidirectional=True, batch_first=True, dropout=0.1)
        self.out = nn.Linear(hidden * 2, vocab)

    def forward(self, mel, mlen):
        x = self.conv(mel.transpose(1, 2)).transpose(1, 2)       # (B, T/2, H)
        lens = (mlen + 1) // 2
        packed = nn.utils.rnn.pack_padded_sequence(x, lens.cpu(), batch_first=True, enforce_sorted=False)
        y, _ = self.rnn(packed)
        y, _ = nn.utils.rnn.pad_packed_sequence(y, batch_first=True, total_length=x.shape[1])
        return F.log_softmax(self.out(y), dim=-1), lens


def train(args):
    ds = ClipDataset(args.data)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True, collate_fn=collate, num_workers=0, drop_last=False)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = CTCAligner().to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    ctc = nn.CTCLoss(blank=BLANK, zero_infinity=True)
    step, t0 = 0, time.time()
    print(f'aligner: {len(ds)} clips, {len(PHONES)} phones, device {dev}')
    while step < args.steps:
        for batch in dl:
            mel, mlen, ph, plen = batch['mel'].to(dev), batch['mlen'].to(dev), batch['phones'].to(dev), batch['plen'].to(dev)
            logp, lens = model(mel, mlen)
            targets = torch.cat([ph[i, :plen[i]] for i in range(ph.shape[0])])
            loss = ctc(logp.transpose(0, 1), targets, lens, plen)
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
            step += 1
            if step % args.log == 0 or step == 1:
                print(f'step {step} ctc {loss.item():.3f} ({time.time() - t0:.0f}s)')
            if step % args.save == 0 or step >= args.steps:
                os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
                torch.save({'model': model.state_dict(), 'step': step}, args.out)
            if step >= args.steps:
                break
    print(f'saved {args.out}')


def forced_align(logp, targets):
    """CTC Viterbi over the extended label sequence (blank, l1, blank, l2, ..., blank).
    logp: (T, V) numpy log-probs; targets: list of label ids. Returns frame count per target label (blanks folded into the preceding label)."""
    T = logp.shape[0]; N = len(targets)
    ext = [BLANK]
    for t in targets:
        ext += [t, BLANK]
    S = len(ext)
    NEG = -1e30
    dp = np.full((T, S), NEG, dtype=np.float64); bp = np.zeros((T, S), dtype=np.int32)
    dp[0, 0] = logp[0, ext[0]]
    if S > 1:
        dp[0, 1] = logp[0, ext[1]]
    for t in range(1, T):
        for s in range(S):
            best, arg = dp[t - 1, s], s
            if s >= 1 and dp[t - 1, s - 1] > best:
                best, arg = dp[t - 1, s - 1], s - 1
            if s >= 2 and ext[s] != BLANK and ext[s] != ext[s - 2] and dp[t - 1, s - 2] > best:
                best, arg = dp[t - 1, s - 2], s - 2
            dp[t, s] = best + logp[t, ext[s]]; bp[t, s] = arg
    s = S - 1 if S == 1 or dp[T - 1, S - 1] >= dp[T - 1, S - 2] else S - 2
    path = np.zeros(T, dtype=np.int32)
    for t in range(T - 1, -1, -1):
        path[t] = s; s = bp[t, s]
    # frames per label: label i owns ext index 2i+1; blanks after it belong to it, leading blanks to the first label
    counts = np.zeros(N, dtype=np.int64); cur = 0
    for t in range(T):
        idx = path[t]
        if idx % 2 == 1:
            cur = (idx - 1) // 2
        counts[cur] += 1
    return counts


def align(args):
    ds = ClipDataset(args.data)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = CTCAligner().to(dev); model.load_state_dict(torch.load(args.model, map_location=dev)['model']); model.eval()
    dl = DataLoader(ds, batch_size=args.batch, shuffle=False, collate_fn=collate)
    out_path = os.path.join(args.data, 'alignments.jsonl'); n = 0
    with open(out_path, 'w', encoding='utf-8') as f, torch.no_grad():
        for batch in dl:
            logp, lens = model(batch['mel'].to(dev), batch['mlen'].to(dev))
            logp = logp.cpu().numpy()
            for i, clip in enumerate(batch['clips']):
                L = int(lens[i]); ids = batch['phones'][i, :batch['plen'][i]].tolist()
                counts = forced_align(logp[i, :L], ids) * 2          # back to 12.5 ms mel frames
                total = int(batch['mlen'][i]); diff = total - int(counts.sum())
                counts[-1] += diff                                   # absorb the odd frame
                f.write(json.dumps({'clip': clip, 'durations': [int(c) for c in counts]}) + '\n'); n += 1
    print(f'aligned {n} clips -> {out_path}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('train'); t.add_argument('--data', required=True); t.add_argument('--out', required=True); t.add_argument('--steps', type=int, default=20000)
    t.add_argument('--batch', type=int, default=16); t.add_argument('--lr', type=float, default=1e-3); t.add_argument('--log', type=int, default=50); t.add_argument('--save', type=int, default=1000)
    a = sub.add_parser('align'); a.add_argument('--data', required=True); a.add_argument('--model', required=True); a.add_argument('--batch', type=int, default=16)
    args = ap.parse_args()
    train(args) if args.cmd == 'train' else align(args)
