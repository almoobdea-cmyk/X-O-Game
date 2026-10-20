"""Audio I/O and mel features (numpy only, so ingestion runs without torch)."""
import subprocess
import wave
import numpy as np

SR = 16000
N_FFT = 1024
HOP = 200          # 12.5 ms
WIN = 800          # 50 ms
N_MELS = 80
FMIN, FMAX = 40.0, 7600.0


def load_audio(path, start=None, end=None):
    """Decode any media file with ffmpeg to 16 kHz mono float32; optional [start, end] seconds."""
    cmd = ['ffmpeg', '-v', 'error', '-nostdin']
    if start is not None:
        cmd += ['-ss', f'{start:.3f}']
    cmd += ['-i', path]
    if end is not None and start is not None:
        cmd += ['-t', f'{max(0.0, end - start):.3f}']
    cmd += ['-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def save_wav(path, x, sr=SR):
    x = np.clip(np.asarray(x, dtype=np.float32), -1, 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767).astype('<i2').tobytes())


def read_wav(path):
    with wave.open(path, 'rb') as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == SR, 'expected 16 kHz mono PCM16'
        return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32) / 32767


def _hz_to_mel(f): return 2595.0 * np.log10(1.0 + f / 700.0)
def _mel_to_hz(m): return 700.0 * (10 ** (m / 2595.0) - 1.0)


def mel_filterbank(n_fft=N_FFT, n_mels=N_MELS, sr=SR, fmin=FMIN, fmax=FMAX):
    mels = np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    hz = _mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(n_mels):
        lo, c, hi = bins[m], bins[m + 1], bins[m + 2]
        if c == lo: c += 1
        if hi == c: hi += 1
        fb[m, lo:c] = (np.arange(lo, c) - lo) / (c - lo)
        fb[m, c:hi] = (hi - np.arange(c, hi)) / (hi - c)
    return fb


_FB = None


def log_mel(x):
    """(T, 80) log-mel spectrogram, frames every 12.5 ms."""
    global _FB
    if _FB is None:
        _FB = mel_filterbank()
    pad = (N_FFT - HOP) // 2
    xp = np.pad(x, (pad, pad), mode='reflect')
    n_frames = 1 + (len(xp) - N_FFT) // HOP
    win = np.hanning(WIN + 1)[:-1].astype(np.float32)
    frames = np.lib.stride_tricks.as_strided(xp, shape=(n_frames, N_FFT), strides=(xp.strides[0] * HOP, xp.strides[0])).copy()
    frames[:, :WIN] *= win; frames[:, WIN:] = 0
    spec = np.abs(np.fft.rfft(frames, n=N_FFT, axis=1)) ** 2
    mel = spec @ _FB.T
    return np.log(np.maximum(mel, 1e-5)).astype(np.float32)


def griffin_lim(mel, n_iter=40):
    """Rough inverse: log-mel -> waveform via pseudo-inverse of the filterbank and Griffin-Lim phase recovery."""
    global _FB
    if _FB is None:
        _FB = mel_filterbank()
    power = np.exp(mel) @ np.linalg.pinv(_FB.T)
    mag = np.sqrt(np.maximum(power, 1e-8)).astype(np.float32)   # (T, n_fft/2+1)
    T = mag.shape[0]
    win = np.hanning(WIN + 1)[:-1].astype(np.float32)
    angles = np.exp(2j * np.pi * np.random.rand(*mag.shape))
    def istft(S):
        frames = np.fft.irfft(S, n=N_FFT, axis=1)[:, :WIN] * win
        out = np.zeros(HOP * (T - 1) + WIN, dtype=np.float32); norm = np.zeros_like(out)
        for t in range(T):
            out[t * HOP:t * HOP + WIN] += frames[t]; norm[t * HOP:t * HOP + WIN] += win ** 2
        return out / np.maximum(norm, 1e-6)
    def stft(x):
        n = 1 + (len(x) - WIN) // HOP
        fr = np.lib.stride_tricks.as_strided(x, shape=(n, WIN), strides=(x.strides[0] * HOP, x.strides[0])).copy() * win
        return np.fft.rfft(fr, n=N_FFT, axis=1)
    S = mag * angles
    for _ in range(n_iter):
        x = istft(S)
        P = stft(x)
        P = P[:T] if P.shape[0] >= T else np.pad(P, ((0, T - P.shape[0]), (0, 0)))
        S = mag * np.exp(1j * np.angle(P))
    x = istft(S)
    m = np.max(np.abs(x)) or 1.0
    return (x / m * 0.7).astype(np.float32)
