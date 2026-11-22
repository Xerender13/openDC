'use strict';
// DDS (DXT1 / DXT3 / DXT5, as the client's UI pieces) -> RGBA pixels, for the game's item and car pictures.
(function (root) {
  function c565(c) { return [((c >> 11) & 31) * 255 / 31 | 0, ((c >> 5) & 63) * 255 / 63 | 0, (c & 31) * 255 / 31 | 0]; }
  function decode(buf) {
    const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
    const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    if (dv.getUint32(0, true) !== 0x20534444) throw new Error('not a DDS');
    const h = dv.getUint32(12, true), w = dv.getUint32(16, true);
    const four = String.fromCharCode(b[84], b[85], b[86], b[87]);
    const out = new Uint8ClampedArray(w * h * 4);
    let p = 128;
    const bs = four === 'DXT1' ? 8 : 16;
    // uncompressed (neon glow, some lamps): pixels by their colour masks, 16 / 24 / 32 bits
    if (!/^DXT[135]$/.test(four) && (dv.getUint32(80, true) & 0x40)) {
      const bpp = dv.getUint32(88, true) >> 3, flags = dv.getUint32(80, true);
      const masks = [92, 96, 100, 104].map((o) => dv.getUint32(o, true));
      const sh = masks.map((m) => { let k = 0; if (!m) return [0, 0]; while (!((m >> k) & 1)) k++; let n = 0; while ((m >> (k + n)) & 1) n++; return [k, n]; });
      for (let i = 0; i < w * h; i++) {
        const o = p + i * bpp; if (o + bpp > b.length) break;
        let v = 0; for (let k = 0; k < bpp; k++) v += b[o + k] * 2 ** (8 * k);
        for (let c = 0; c < 4; c++) {
          const [k, n] = sh[c];
          out[i * 4 + c] = c === 3 && (!(flags & 1) || !masks[3]) ? 255 : n ? Math.round((Math.floor(v / 2 ** k) % 2 ** n) * 255 / (2 ** n - 1)) : 0;
        }
      }
      return { w, h, data: out };
    }
    if (!/^DXT[135]$/.test(four)) throw new Error('DDS ' + four);
    for (let by = 0; by < Math.max(1, h / 4); by++) {
      for (let bx = 0; bx < Math.max(1, w / 4); bx++) {
        const alpha = new Array(16).fill(255);
        let q = p;
        if (four === 'DXT3') {
          for (let i = 0; i < 8; i++) { const v = b[q + i]; alpha[i * 2] = (v & 15) * 17; alpha[i * 2 + 1] = (v >> 4) * 17; }
          q += 8;
        } else if (four === 'DXT5') {
          const a0 = b[q], a1 = b[q + 1];
          const t = [a0, a1];
          if (a0 > a1) for (let i = 1; i < 7; i++) t.push(((7 - i) * a0 + i * a1) / 7 | 0);
          else { for (let i = 1; i < 5; i++) t.push(((5 - i) * a0 + i * a1) / 5 | 0); t.push(0, 255); }
          const lo = b[q + 2] | (b[q + 3] << 8) | (b[q + 4] << 16), hi = b[q + 5] | (b[q + 6] << 8) | (b[q + 7] << 16);
          for (let i = 0; i < 8; i++) { alpha[i] = t[(lo >> (3 * i)) & 7]; alpha[i + 8] = t[(hi >> (3 * i)) & 7]; }
          q += 8;
        }
        const c0 = b[q] | (b[q + 1] << 8), c1 = b[q + 2] | (b[q + 3] << 8);
        const k0 = c565(c0), k1 = c565(c1);
        const pal = [k0, k1];
        if (c0 > c1 || four !== 'DXT1') {
          pal.push(k0.map((x, i) => (2 * x + k1[i]) / 3 | 0), k0.map((x, i) => (x + 2 * k1[i]) / 3 | 0));
        } else {
          pal.push(k0.map((x, i) => (x + k1[i]) / 2 | 0), [0, 0, 0]);
        }
        const idx = b[q + 4] | (b[q + 5] << 8) | (b[q + 6] << 16) | (b[q + 7] << 24);
        for (let i = 0; i < 16; i++) {
          const x = bx * 4 + (i & 3), y = by * 4 + (i >> 2);
          if (x >= w || y >= h) continue;
          const ci = (idx >>> (2 * i)) & 3;
          const o = (y * w + x) * 4;
          out[o] = pal[ci][0]; out[o + 1] = pal[ci][1]; out[o + 2] = pal[ci][2];
          out[o + 3] = four === 'DXT1' ? (c0 <= c1 && ci === 3 ? 0 : 255) : alpha[i];
        }
        p += bs;
      }
    }
    return { w, h, data: out };
  }
  if (typeof module !== 'undefined') module.exports = { decode }; else root.DDS = { decode };
})(this);
