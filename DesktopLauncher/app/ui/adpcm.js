'use strict';
// The client's sound effects are IMA ADPCM WAV files (format 17), which Chromium does not play: toPcmWav(bytes) turns
// one into a 16-bit PCM WAV (other WAVs come back as they are).
(function (root) {
  const STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97,
    107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963,
    1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484,
    7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767];
  const IDX = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8];

  function toPcmWav(input) {
    const b = input instanceof Uint8Array ? input : new Uint8Array(input);
    const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    const tag = (o) => String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3]);
    if (b.length < 12 || tag(0) !== 'RIFF' || tag(8) !== 'WAVE') return b;
    let fmt = null, data = null;
    for (let p = 12; p + 8 <= b.length;) {
      const id = tag(p), n = dv.getUint32(p + 4, true);
      if (id === 'fmt ') fmt = { tag: dv.getUint16(p + 8, true), ch: dv.getUint16(p + 10, true), rate: dv.getUint32(p + 12, true), align: dv.getUint16(p + 20, true) };
      else if (id === 'data') data = b.subarray(p + 8, Math.min(b.length, p + 8 + n));
      p += 8 + n + (n & 1);
    }
    if (!fmt || !data || fmt.tag !== 17) return b;
    const ch = fmt.ch, align = fmt.align;
    const perBlock = ((align - 4 * ch) * 8) / (4 * ch) + 1;
    const blocks = Math.floor(data.length / align);
    const out = new Int16Array(blocks * perBlock * ch);
    let o = 0;
    for (let k = 0; k < blocks; k++) {
      const base = k * align;
      const pred = [], idx = [];
      for (let c = 0; c < ch; c++) {
        let v = data[base + c * 4] | (data[base + c * 4 + 1] << 8);
        if (v & 0x8000) v -= 0x10000;
        pred[c] = v; idx[c] = Math.min(88, data[base + c * 4 + 2]);
        out[o + c] = v;
      }
      const frame = new Int16Array(perBlock * ch);
      for (let c = 0; c < ch; c++) frame[c] = pred[c];
      // then, per channel, groups of 4 bytes = 8 samples, the channels taking turns
      let p = base + 4 * ch;
      const n = [];
      for (let c = 0; c < ch; c++) n[c] = 1;
      while (p + 4 * ch <= base + align) {
        for (let c = 0; c < ch; c++) {
          for (let j = 0; j < 4; j++) {
            const byte = data[p + j];
            for (const nib of [byte & 15, byte >> 4]) {
              const step = STEP[idx[c]];
              let diff = step >> 3;
              if (nib & 4) diff += step;
              if (nib & 2) diff += step >> 1;
              if (nib & 1) diff += step >> 2;
              pred[c] += nib & 8 ? -diff : diff;
              if (pred[c] > 32767) pred[c] = 32767; else if (pred[c] < -32768) pred[c] = -32768;
              idx[c] += IDX[nib];
              if (idx[c] < 0) idx[c] = 0; else if (idx[c] > 88) idx[c] = 88;
              if (n[c] < perBlock) frame[n[c] * ch + c] = pred[c];
              n[c]++;
            }
          }
          p += 4;
        }
      }
      out.set(frame, o);
      o += perBlock * ch;
    }
    const pcm = new Uint8Array(44 + out.length * 2);
    const w = new DataView(pcm.buffer);
    const put = (off, s) => { for (let i = 0; i < 4; i++) pcm[off + i] = s.charCodeAt(i); };
    put(0, 'RIFF'); w.setUint32(4, 36 + out.length * 2, true); put(8, 'WAVE');
    put(12, 'fmt '); w.setUint32(16, 16, true); w.setUint16(20, 1, true); w.setUint16(22, ch, true);
    w.setUint32(24, fmt.rate, true); w.setUint32(28, fmt.rate * ch * 2, true); w.setUint16(32, ch * 2, true); w.setUint16(34, 16, true);
    put(36, 'data'); w.setUint32(40, out.length * 2, true);
    new Int16Array(pcm.buffer, 44).set(out);
    return pcm;
  }
  const api = { toPcmWav };
  if (typeof module !== 'undefined') module.exports = api; else root.ADPCM = api;
})(this);
