"""Step 3: a self-contained neural diacritizer (character BiLSTM tagger).

  python diacritizer.py train --corpus diacritized.txt --out ckpt/diacritizer.pt --steps 20000
  python diacritizer.py apply --model ckpt/diacritizer.pt --in data/metadata.jsonl --out data/metadata.vocalized.jsonl
  python diacritizer.py eval  --model ckpt/diacritizer.pt --corpus gold.txt

Training text: one vocalized sentence per line (Tashkeela for MSA; for the Saudi convention, sentences labelled once with the
tashkeel skill and reviewed). The tagger learns, for every letter, which mark(s) follow it.
"""
import argparse
import json
import os
import random
import re
import sys
import unicodedata

import torch
import torch.nn as nn
import torch.nn.functional as F

MARKS = set('ًٌٍَُِّْٰ')
SHADDA = 'ّ'
CLASSES = ['', 'َ', 'ُ', 'ِ', 'ْ', 'ً', 'ٌ', 'ٍ', SHADDA,
           SHADDA + 'َ', SHADDA + 'ُ', SHADDA + 'ِ', SHADDA + 'ً', SHADDA + 'ٌ', SHADDA + 'ٍ', 'ٰ']
CLS_ID = {c: i for i, c in enumerate(CLASSES)}


def split_marks(text):
    """Vocalized text -> (letters, labels). Marks attach to the preceding character; label = optional shadda + at most one vowel/tanween."""
    text = unicodedata.normalize('NFC', text).replace('\u0640', '')
    letters, labels = [], []
    for ch in text:
        if ch in MARKS:
            if not letters:
                continue
            has_sh = SHADDA in labels[-1] or ch == SHADDA
            rest = labels[-1].replace(SHADDA, '')
            if ch != SHADDA:
                rest = ch
            labels[-1] = (SHADDA if has_sh else '') + rest
        else:
            letters.append(ch); labels.append('')
    return letters, [CLS_ID.get(l, 0) for l in labels]


def join_marks(letters, label_ids):
    return ''.join(ch + CLASSES[i] for ch, i in zip(letters, label_ids))


class CharVocab:
    def __init__(self, texts=None, chars=None):
        self.chars = chars or sorted({c for t in texts for c in split_marks(t)[0]} | {' '})
        self.idx = {c: i + 2 for i, c in enumerate(self.chars)}   # 0 pad, 1 unk

    def encode(self, letters):
        return [self.idx.get(c, 1) for c in letters]


class Tagger(nn.Module):
    def __init__(self, vocab_size, d=96, h=192):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, d, padding_idx=0)
        self.rnn = nn.LSTM(d, h, num_layers=2, bidirectional=True, batch_first=True, dropout=0.2)
        self.out = nn.Linear(h * 2, len(CLASSES))

    def forward(self, x):
        y, _ = self.rnn(self.emb(x))
        return self.out(y)


def batches(pairs, vocab, bs, dev, shuffle=True):
    order = list(range(len(pairs)))
    if shuffle:
        random.shuffle(order)
    for i in range(0, len(order), bs):
        chunk = [pairs[j] for j in order[i:i + bs]]
        L = max(len(p[0]) for p in chunk)
        x = torch.zeros(len(chunk), L, dtype=torch.long); y = torch.full((len(chunk), L), -100, dtype=torch.long)
        for k, (letters, labels) in enumerate(chunk):
            x[k, :len(letters)] = torch.tensor(vocab.encode(letters)); y[k, :len(labels)] = torch.tensor(labels)
        yield x.to(dev), y.to(dev)


def load_corpus(path):
    with open(path, encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    return [l for l in lines if any(c in MARKS for c in l)]


def train(args):
    lines = load_corpus(args.corpus)
    random.seed(0); random.shuffle(lines)
    n_val = max(1, len(lines) // 20); val, tr = lines[:n_val], lines[n_val:]
    vocab = CharVocab(lines)
    pairs = [split_marks(l) for l in tr]; vpairs = [split_marks(l) for l in val]
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = Tagger(len(vocab.chars) + 2).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    step = 0
    print(f'diacritizer: {len(tr)} train / {len(val)} val sentences, {len(vocab.chars)} chars')
    while step < args.steps:
        for x, y in batches(pairs, vocab, args.batch, dev):
            loss = F.cross_entropy(model(x).reshape(-1, len(CLASSES)), y.reshape(-1), ignore_index=-100)
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); step += 1
            if step % args.log == 0 or step == 1:
                print(f'step {step} loss {loss.item():.3f} val-acc {evaluate(model, vpairs, vocab, dev):.3f}')
            if step >= args.steps:
                break
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    torch.save({'model': model.state_dict(), 'chars': vocab.chars}, args.out)
    print(f'saved {args.out}; val char-accuracy {evaluate(model, vpairs, vocab, dev):.3f}')


@torch.no_grad()
def evaluate(model, pairs, vocab, dev):
    model.eval(); correct = total = 0
    for x, y in batches(pairs, vocab, 64, dev, shuffle=False):
        pred = model(x).argmax(-1); m = y != -100
        correct += int((pred[m] == y[m]).sum()); total += int(m.sum())
    model.train()
    return correct / max(1, total)


def load_model(path, dev):
    ck = torch.load(path, map_location=dev)
    vocab = CharVocab(chars=ck['chars']); model = Tagger(len(vocab.chars) + 2).to(dev); model.load_state_dict(ck['model']); model.eval()
    return model, vocab


@torch.no_grad()
def vocalize(model, vocab, text, dev):
    letters, _ = split_marks(text)
    x = torch.tensor([vocab.encode(letters)], dtype=torch.long, device=dev)
    pred = model(x).argmax(-1)[0].tolist()
    # keep marks the writer already supplied
    _, given = split_marks(text)
    pred = [g if g else p for g, p in zip(given, pred)]
    return join_marks(letters, pred)


def apply(args):
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model, vocab = load_model(args.model, dev)
    n = 0
    with open(args.inp, encoding='utf-8') as f, open(args.out, 'w', encoding='utf-8') as g:
        for l in f:
            if not l.strip():
                continue
            d = json.loads(l); d['text_raw'] = d['text']; d['text'] = vocalize(model, vocab, d['text'], dev)
            g.write(json.dumps(d, ensure_ascii=False) + '\n'); n += 1
    print(f'vocalized {n} lines -> {args.out}')


def eval_cmd(args):
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model, vocab = load_model(args.model, dev)
    lines = load_corpus(args.corpus); correct = total = 0
    for l in lines:
        letters, gold = split_marks(l)
        bare = ''.join(letters)
        _, pred = split_marks(vocalize(model, vocab, bare, dev))
        correct += sum(int(a == b) for a, b in zip(gold, pred)); total += len(gold)
    print(f'char-level diacritic accuracy on {len(lines)} lines: {correct / max(1, total):.3f}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('train'); t.add_argument('--corpus', required=True); t.add_argument('--out', required=True); t.add_argument('--steps', type=int, default=20000)
    t.add_argument('--batch', type=int, default=32); t.add_argument('--lr', type=float, default=2e-3); t.add_argument('--log', type=int, default=100)
    a = sub.add_parser('apply'); a.add_argument('--model', required=True); a.add_argument('--in', dest='inp', required=True); a.add_argument('--out', required=True)
    e = sub.add_parser('eval'); e.add_argument('--model', required=True); e.add_argument('--corpus', required=True)
    args = ap.parse_args()
    {'train': train, 'apply': apply, 'eval': eval_cmd}[args.cmd](args)
