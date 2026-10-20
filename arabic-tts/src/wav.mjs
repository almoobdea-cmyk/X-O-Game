// WAV decode/encode and resampling. No dependencies.
export const SR = 16000;

export function decodeWav(buf) {
  const dv = new DataView(buf.buffer ? buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) : buf);
  const tag = (o) => String.fromCharCode(dv.getUint8(o), dv.getUint8(o + 1), dv.getUint8(o + 2), dv.getUint8(o + 3));
  if (tag(0) !== 'RIFF' || tag(8) !== 'WAVE') throw new Error('not a WAV file');
  let p = 12, fmt = null, data = null;
  while (p + 8 <= dv.byteLength) {
    const id = tag(p), size = dv.getUint32(p + 4, true);
    if (id === 'fmt ') fmt = { format: dv.getUint16(p + 8, true), channels: dv.getUint16(p + 10, true), rate: dv.getUint32(p + 12, true), bits: dv.getUint16(p + 22, true) };
    else if (id === 'data') data = { off: p + 8, size: Math.min(size, dv.byteLength - p - 8) };
    p += 8 + size + (size & 1);
  }
  if (!fmt || !data) throw new Error('WAV missing fmt or data chunk');
  const { channels, rate, bits, format } = fmt;
  const bytes = bits / 8, frames = Math.floor(data.size / (bytes * channels));
  const out = new Float32Array(frames);
  for (let i = 0; i < frames; i++) {
    let acc = 0;
    for (let c = 0; c < channels; c++) {
      const o = data.off + (i * channels + c) * bytes;
      let v;
      if (format === 3) v = bits === 32 ? dv.getFloat32(o, true) : dv.getFloat64(o, true);
      else if (bits === 16) v = dv.getInt16(o, true) / 32768;
      else if (bits === 24) { const b0 = dv.getUint8(o), b1 = dv.getUint8(o + 1), b2 = dv.getInt8(o + 2); v = ((b2 << 16) | (b1 << 8) | b0) / 8388608; }
      else if (bits === 32) v = dv.getInt32(o, true) / 2147483648;
      else if (bits === 8) v = (dv.getUint8(o) - 128) / 128;
      else throw new Error('unsupported WAV bit depth ' + bits);
      acc += v;
    }
    out[i] = acc / channels;
  }
  return { samples: rate === SR ? out : resample(out, rate, SR), rate: SR, originalRate: rate };
}

export function encodeWav(samples, rate = SR) {
  const n = samples.length;
  const buf = new ArrayBuffer(44 + n * 2);
  const dv = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
  w(0, 'RIFF'); dv.setUint32(4, 36 + n * 2, true); w(8, 'WAVE'); w(12, 'fmt ');
  dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true);
  dv.setUint32(24, rate, true); dv.setUint32(28, rate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true);
  w(36, 'data'); dv.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) { const v = Math.max(-1, Math.min(1, samples[i])); dv.setInt16(44 + i * 2, v < 0 ? v * 32768 : v * 32767, true); }
  return new Uint8Array(buf);
}

/** Linear-interpolation resampler with a simple anti-alias average when downsampling. */
export function resample(x, from, to) {
  if (from === to) return x;
  const ratio = from / to;
  const n = Math.floor(x.length / ratio);
  const out = new Float32Array(n);
  if (ratio > 1) {
    const win = Math.ceil(ratio);
    for (let i = 0; i < n; i++) {
      const c = i * ratio; let acc = 0, cnt = 0;
      for (let k = Math.floor(c - win / 2); k <= Math.floor(c + win / 2); k++) { if (k >= 0 && k < x.length) { acc += x[k]; cnt++; } }
      out[i] = cnt ? acc / cnt : 0;
    }
  } else {
    for (let i = 0; i < n; i++) { const c = i * ratio, k = Math.floor(c), f = c - k; out[i] = (x[k] ?? 0) * (1 - f) + (x[k + 1] ?? 0) * f; }
  }
  return out;
}

export function normalize(x, peak = 0.7) {
  let m = 0; for (let i = 0; i < x.length; i++) m = Math.max(m, Math.abs(x[i]));
  if (m < 1e-6) return x;
  const g = peak / m; const out = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) out[i] = x[i] * g;
  return out;
}
