"""Dataset: clips + metadata -> cached log-mel, phone ids, (optional) durations from the aligner."""
import json
import os
import random

import numpy as np
import torch
from torch.utils.data import Dataset

from audio import read_wav, log_mel
from text import phonemize_lines, encode, PAD


def load_meta(data_dir, vocalized=True):
    name = 'metadata.vocalized.jsonl' if vocalized and os.path.exists(os.path.join(data_dir, 'metadata.vocalized.jsonl')) else 'metadata.jsonl'
    with open(os.path.join(data_dir, name), encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def ensure_features(data_dir, items):
    """Compute and cache mel + phone ids for every item (idempotent)."""
    mel_dir = os.path.join(data_dir, 'mel'); os.makedirs(mel_dir, exist_ok=True)
    todo = [it for it in items if not os.path.exists(os.path.join(mel_dir, it['clip'] + '.npy'))]
    for it in todo:
        x = read_wav(os.path.join(data_dir, 'clips', it['clip']))
        np.save(os.path.join(mel_dir, it['clip'] + '.npy'), log_mel(x))
    ph_path = os.path.join(data_dir, 'phones.jsonl')
    have = {}
    if os.path.exists(ph_path):
        with open(ph_path, encoding='utf-8') as f:
            for l in f:
                d = json.loads(l); have[d['clip']] = d
    missing = [it for it in items if it['clip'] not in have]
    if missing:
        by_mode = {}
        for it in missing:
            by_mode.setdefault(it.get('mode', 'auto'), []).append(it)
        with open(ph_path, 'a', encoding='utf-8') as f:
            for mode, group in by_mode.items():
                for chunk_start in range(0, len(group), 200):
                    chunk = group[chunk_start:chunk_start + 200]
                    res = phonemize_lines([it['text'] for it in chunk], mode)
                    for it, r in zip(chunk, res):
                        d = {'clip': it['clip'], 'phones': r['phones'], 'mode': r['mode']}
                        have[it['clip']] = d
                        f.write(json.dumps(d, ensure_ascii=False) + '\n')
    return have


def load_alignments(data_dir):
    p = os.path.join(data_dir, 'alignments.jsonl')
    if not os.path.exists(p):
        return {}
    out = {}
    with open(p, encoding='utf-8') as f:
        for l in f:
            d = json.loads(l); out[d['clip']] = d['durations']
    return out


class ClipDataset(Dataset):
    def __init__(self, data_dir, need_durations=False, max_frames=1200):
        self.data_dir = data_dir
        self.items = load_meta(data_dir)
        self.phones = ensure_features(data_dir, self.items)
        self.align = load_alignments(data_dir) if need_durations else {}
        self.speakers = sorted({it['speaker'] for it in self.items})
        self.spk_id = {s: i for i, s in enumerate(self.speakers)}
        keep = []
        for it in self.items:
            ids = encode(self.phones[it['clip']]['phones'])
            if len(ids) < 2:
                continue
            if need_durations and it['clip'] not in self.align:
                continue
            keep.append(it)
        self.items = keep
        self.max_frames = max_frames

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        it = self.items[i]
        mel = np.load(os.path.join(self.data_dir, 'mel', it['clip'] + '.npy'))[:self.max_frames]
        ids = encode(self.phones[it['clip']]['phones'])
        d = self.align.get(it['clip'])
        sample = {'mel': torch.from_numpy(mel), 'phones': torch.tensor(ids, dtype=torch.long), 'speaker': self.spk_id[it['speaker']], 'clip': it['clip']}
        if d is not None:
            d = list(d)[:len(ids)]
            total = mel.shape[0]
            if sum(d) != total:   # rescale durations to the (possibly cropped) mel length
                s = total / max(1, sum(d)); d = [max(1, int(round(v * s))) for v in d]
                d[-1] += total - sum(d)
            sample['durations'] = torch.tensor(d, dtype=torch.long)
        # reference segment for the speaker encoder: a random crop of the same clip (<= 2 s)
        T = mel.shape[0]; L = min(T, 160)
        s = random.randint(0, T - L)
        sample['ref'] = torch.from_numpy(mel[s:s + L])
        return sample


def collate(batch):
    B = len(batch)
    n = max(b['phones'].shape[0] for b in batch); T = max(b['mel'].shape[0] for b in batch); R = max(b['ref'].shape[0] for b in batch)
    phones = torch.full((B, n), PAD, dtype=torch.long); mel = torch.zeros(B, T, 80); ref = torch.zeros(B, R, 80)
    plen = torch.zeros(B, dtype=torch.long); mlen = torch.zeros(B, dtype=torch.long); rlen = torch.zeros(B, dtype=torch.long)
    durs = torch.zeros(B, n, dtype=torch.long) if 'durations' in batch[0] else None
    spk = torch.tensor([b['speaker'] for b in batch], dtype=torch.long)
    for i, b in enumerate(batch):
        phones[i, :b['phones'].shape[0]] = b['phones']; plen[i] = b['phones'].shape[0]
        mel[i, :b['mel'].shape[0]] = b['mel']; mlen[i] = b['mel'].shape[0]
        ref[i, :b['ref'].shape[0]] = b['ref']; rlen[i] = b['ref'].shape[0]
        if durs is not None:
            durs[i, :b['durations'].shape[0]] = b['durations']
    out = {'phones': phones, 'plen': plen, 'mel': mel, 'mlen': mlen, 'ref': ref, 'rlen': rlen, 'speaker': spk, 'clips': [b['clip'] for b in batch]}
    if durs is not None:
        out['durations'] = durs
    return out
