"""Step 5 model: FastSpeech-style non-autoregressive TTS with a reference encoder for speaker tone.

phones -> encoder -> (+ reference embedding) -> duration predictor -> length regulator -> decoder -> log-mel
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from text import PHONES, PAD


def sinusoid(T, d, device):
    pos = torch.arange(T, device=device).unsqueeze(1)
    div = torch.exp(torch.arange(0, d, 2, device=device) * (-math.log(10000.0) / d))
    pe = torch.zeros(T, d, device=device); pe[:, 0::2] = torch.sin(pos * div); pe[:, 1::2] = torch.cos(pos * div)
    return pe


class FFTBlock(nn.Module):
    def __init__(self, d, heads=2, k=9, ff=1024, drop=0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(d, heads, dropout=drop, batch_first=True)
        self.ln1 = nn.LayerNorm(d); self.ln2 = nn.LayerNorm(d)
        self.ff = nn.Sequential(nn.Conv1d(d, ff, k, padding=k // 2), nn.ReLU(), nn.Dropout(drop), nn.Conv1d(ff, d, 1))
        self.drop = nn.Dropout(drop)

    def forward(self, x, pad_mask):
        a, _ = self.attn(x, x, x, key_padding_mask=pad_mask)
        x = self.ln1(x + self.drop(a))
        y = self.ff(x.transpose(1, 2)).transpose(1, 2)
        x = self.ln2(x + self.drop(y))
        return x.masked_fill(pad_mask.unsqueeze(-1), 0.0)


class ReferenceEncoder(nn.Module):
    """Mel segment of any speaker -> 256-d tone embedding."""
    def __init__(self, d=256):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(80, 128, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv1d(128, 128, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv1d(128, 128, 5, stride=2, padding=2), nn.ReLU())
        self.gru = nn.GRU(128, 128, batch_first=True)
        self.out = nn.Linear(128, d)

    def forward(self, ref, rlen):
        x = self.conv(ref.transpose(1, 2)).transpose(1, 2)
        lens = torch.clamp((rlen + 7) // 8, min=1)
        packed = nn.utils.rnn.pack_padded_sequence(x, lens.cpu(), batch_first=True, enforce_sorted=False)
        _, h = self.gru(packed)
        return torch.tanh(self.out(h[-1]))


class DurationPredictor(nn.Module):
    def __init__(self, d, k=3, drop=0.1):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(d, d, k, padding=k // 2), nn.ReLU(), nn.LayerNorm(d) if False else nn.Identity(), nn.Dropout(drop),
                                 nn.Conv1d(d, d, k, padding=k // 2), nn.ReLU(), nn.Dropout(drop))
        self.out = nn.Linear(d, 1)

    def forward(self, x):
        return self.out(self.net(x.transpose(1, 2)).transpose(1, 2)).squeeze(-1)   # log(duration + 1)


def length_regulate(x, durations, max_len=None):
    """Expand (B,N,d) by integer durations (B,N) -> (B,T,d) padded."""
    B, N, d = x.shape
    lens = durations.sum(1)
    T = int(max_len or lens.max().item())
    out = torch.zeros(B, T, d, device=x.device)
    for b in range(B):
        idx = torch.repeat_interleave(torch.arange(N, device=x.device), durations[b])[:T]
        out[b, :idx.shape[0]] = x[b, idx]
    return out, lens.clamp(max=T)


class NataqTTS(nn.Module):
    def __init__(self, d=256, n_enc=4, n_dec=4, vocab=len(PHONES)):
        super().__init__()
        self.emb = nn.Embedding(vocab, d, padding_idx=PAD)
        self.enc = nn.ModuleList([FFTBlock(d) for _ in range(n_enc)])
        self.ref = ReferenceEncoder(d)
        self.dur = DurationPredictor(d)
        self.dec = nn.ModuleList([FFTBlock(d) for _ in range(n_dec)])
        self.mel_out = nn.Linear(d, 80)
        self.post = nn.Sequential(nn.Conv1d(80, 256, 5, padding=2), nn.Tanh(), nn.Conv1d(256, 256, 5, padding=2), nn.Tanh(), nn.Conv1d(256, 80, 5, padding=2))
        self.d = d

    def encode(self, phones, plen, ref, rlen):
        pad = phones == PAD
        x = self.emb(phones) * math.sqrt(self.d) + sinusoid(phones.shape[1], self.d, phones.device)
        for blk in self.enc:
            x = blk(x, pad)
        tone = self.ref(ref, rlen)
        x = x + tone.unsqueeze(1)
        return x, pad

    def decode(self, x, durations, mlen=None):
        y, lens = length_regulate(x, durations, mlen)
        T = y.shape[1]
        pad = torch.arange(T, device=y.device).unsqueeze(0) >= lens.unsqueeze(1)
        y = y + sinusoid(T, self.d, y.device)
        for blk in self.dec:
            y = blk(y, pad)
        mel = self.mel_out(y)
        mel_post = mel + self.post(mel.transpose(1, 2)).transpose(1, 2)
        return mel, mel_post, lens

    def forward(self, phones, plen, ref, rlen, durations, mlen):
        x, pad = self.encode(phones, plen, ref, rlen)
        log_d = self.dur(x.detach()).masked_fill(pad, 0.0)
        mel, mel_post, lens = self.decode(x, durations, int(mlen.max().item()))
        return mel, mel_post, log_d

    @torch.no_grad()
    def infer(self, phones, plen, ref, rlen, rate=1.0):
        x, pad = self.encode(phones, plen, ref, rlen)
        d = torch.clamp(torch.round((torch.exp(self.dur(x)) - 1) / rate), min=1).long().masked_fill(pad, 0)
        _, mel_post, lens = self.decode(x, d)
        return mel_post, d, lens


def tts_loss(mel, mel_post, log_d, batch):
    target = batch['mel']; T = target.shape[1]
    mask = (torch.arange(T, device=target.device).unsqueeze(0) < batch['mlen'].unsqueeze(1)).unsqueeze(-1)
    l_mel = (F.l1_loss(mel, target, reduction='none') * mask).sum() / mask.sum() / 80
    l_post = (F.l1_loss(mel_post, target, reduction='none') * mask).sum() / mask.sum() / 80
    pmask = batch['phones'] != PAD
    l_dur = (F.mse_loss(log_d, torch.log(batch['durations'].float() + 1), reduction='none') * pmask).sum() / pmask.sum()
    return l_mel + l_post + l_dur, {'mel': l_mel.item(), 'post': l_post.item(), 'dur': l_dur.item()}
