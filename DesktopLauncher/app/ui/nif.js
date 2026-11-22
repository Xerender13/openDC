'use strict';
// Reader for the game's NIF files (Gamebryo 20.0.0.4, as the client's cars and garage): only the block types they use.
// parse(bytes) -> blocks; shapes(blocks, lod) -> the drawn shapes with their world matrix (row-major 4x4), vertices,
// normals, uv sets, triangles, vertex colours and the properties that decide how they look.
(function (root) {
  function Reader(u8) {
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    let i = 0;
    const r = {
      get i() { return i; }, set i(v) { i = v; },
      u8: () => u8[i++],
      u16: () => { const v = dv.getUint16(i, true); i += 2; return v; },
      u32: () => { const v = dv.getUint32(i, true); i += 4; return v; },
      i32: () => { const v = dv.getInt32(i, true); i += 4; return v; },
      f: () => { const v = dv.getFloat32(i, true); i += 4; return v; },
      fs: (n) => { if (i + n * 4 > u8.length) throw new RangeError('nif'); const a = new Array(n); for (let k = 0; k < n; k++) { a[k] = dv.getFloat32(i, true); i += 4; } return a; },
      f32: (n) => { if (i + n * 4 > u8.length) throw new RangeError('nif'); const a = new Float32Array(n); for (let k = 0; k < n; k++) { a[k] = dv.getFloat32(i, true); i += 4; } return a; },
      u16a: (n) => { if (i + n * 2 > u8.length) throw new RangeError('nif'); const a = new Uint16Array(n); for (let k = 0; k < n; k++) { a[k] = dv.getUint16(i, true); i += 2; } return a; },
      s: () => { const n = dv.getUint32(i, true); i += 4; if (n > 4096 || i + n > u8.length) throw new RangeError('nif'); let t = ''; for (let k = 0; k < n; k++) t += String.fromCharCode(u8[i + k]); i += n; return t; },
      refs: () => { const n = dv.getUint32(i, true); i += 4; if (n > 65536 || i + n * 4 > u8.length) throw new RangeError('nif'); const a = []; for (let k = 0; k < n; k++) { a.push(dv.getInt32(i, true)); i += 4; } return a; },
      bytes: (n) => { if (i + n > u8.length) throw new RangeError('nif'); const a = u8.subarray(i, i + n); i += n; return a; },
    };
    return r;
  }

  const net = (r, b) => { b.name = r.s(); b.extra = r.refs(); b.ctrl = r.i32(); };
  const av = (r, b) => { net(r, b); b.flags = r.u16(); b.t = r.fs(3); b.r = r.fs(9); b.s = r.f(); b.props = r.refs(); r.i32(); };
  const node = (r, b) => { av(r, b); b.children = r.refs(); r.refs(); };
  function keys(r, n, isByte) {
    const nk = r.u32(); if (!nk) return;
    const kt = r.u32();
    if (isByte) { r.i += nk * 5; return; }
    if (kt === 5) { r.i += nk * (4 + 4 * n); return; }
    const per = kt === 2 ? 3 : kt === 3 ? 4 : 1;
    r.i += nk * 4 * (1 + n * per);
  }
  // float keys -> [[time, value], ...]
  function keyList(r) {
    const nk = r.u32(); if (!nk) return [];
    const kt = r.u32();
    const per = kt === 2 ? 3 : kt === 3 ? 4 : 1;
    const out = [];
    for (let k = 0; k < nk; k++) { const v = r.fs(1 + per); out.push([v[0], v[1]]); }
    return out;
  }
  function texdesc(r) {
    const t = { src: r.i32(), clamp: r.u32(), filter: r.u32(), uv: r.u32() };
    if (r.u8()) { r.fs(5); r.u32(); r.fs(2); }
    return t;
  }

  function parse(u8) {
    let i = 0;
    while (u8[i] !== 10) i++;
    const r = Reader(u8); r.i = i + 1;
    const ver = r.u32(); r.u8(); r.u32(); const nb = r.u32();
    if (ver !== 0x14000004) throw new Error('NIF version ' + ver.toString(16));
    const nt = r.u16(); const types = []; for (let k = 0; k < nt; k++) types.push(r.s());
    const idx = r.u16a(nb); r.u32();
    const blocks = [];
    const KNOWN = new Set(['NiNode', 'NiLODNode', 'NiTriShape', 'NiTriStrips', 'NiTriShapeData', 'NiTriStripsData', 'NiTexturingProperty', 'NiSourceTexture', 'NiPixelData', 'NiMaterialProperty', 'NiAlphaProperty', 'NiSpecularProperty', 'NiShadeProperty', 'NiDitherProperty', 'NiWireframeProperty', 'NiZBufferProperty', 'NiVertexColorProperty', 'NiStencilProperty', 'NiStringExtraData', 'NiColorExtraData', 'NiIntegerExtraData', 'NiFloatExtraData', 'NiFloatsExtraData', 'NiRangeLODData', 'NiTransformController', 'NiAlphaController', 'NiVisController', 'NiMaterialColorController', 'NiTextureTransformController', 'NiFlipController', 'NiLookAtController', 'NiTransformInterpolator', 'NiFloatInterpolator', 'NiPoint3Interpolator', 'NiBoolInterpolator', 'NiLookAtInterpolator', 'NiBoolData', 'NiFloatData', 'NiPosData', 'NiTransformData', 'NiTextureEffect', 'NiDirectionalLight', 'NiPointLight', 'NiAmbientLight', 'NiSpotLight']);
    // a block this reader does not know (particles, billboards) has no size written in a 20.0.0.4 file: the reader
    // looks for the first later block from which every block is known, at the byte where reading all of them ends
    // exactly at the file's root list; the unknown blocks in between are left empty
    const resync = (k) => {
      let j = k; for (let q = k; q < nb; q++) if (!KNOWN.has(types[idx[q]])) j = q + 1;
      if (j >= nb) return null;
      for (let off = r.i; off < u8.length - 8; off++) {
        try {
          r.i = off; const got = [];
          for (let q = j; q < nb; q++) { const b = { type: types[idx[q]] }; one(r, b.type, b); got.push(b); }
          const nr = r.u32(); if (nr > 64 || r.i + nr * 4 !== u8.length) continue;
          return { j, got };
        } catch { /* not here */ }
      }
      return null;
    };
    for (let k = 0; k < nb; k++) {
      const t = types[idx[k]]; const b = { type: t };
      if (!KNOWN.has(t)) {
        const at = r.i, got = resync(k);
        if (!got) { r.i = at; blocks.partial = k + ' ' + t; return blocks; }
        for (let q = k; q < got.j; q++) blocks.push({ type: types[idx[q]], skipped: true });
        blocks.push(...got.got); blocks.skipped = k + ' ' + t;
        return blocks;
      }
      one(r, t, b);
      blocks.push(b);
    }
    return blocks;
  }

  function one(r, t, b) {
      switch (t) {
        case 'NiNode': node(r, b); break;
        case 'NiLODNode': node(r, b); r.u16(); r.u32(); b.lod = r.i32(); break;
        case 'NiTriShape': case 'NiTriStrips': av(r, b); b.data = r.i32(); r.i32(); if (r.u8()) { r.s(); r.i32(); } break;
        case 'NiTriShapeData': case 'NiTriStripsData': {
          r.i32(); const nv = r.u16(); r.u8(); r.u8();
          b.v = r.u8() ? r.f32(nv * 3) : null;
          const vf = r.u16();
          if (r.u8()) { b.n = r.f32(nv * 3); if (vf & 4096) r.i += nv * 24; } else b.n = null;
          r.fs(4);
          b.c = r.u8() ? r.f32(nv * 4) : null;
          b.uv = []; for (let u = 0; u < (vf & 63); u++) b.uv.push(r.f32(nv * 2));
          r.u16(); r.i32();
          const ntri = r.u16();
          if (t === 'NiTriStripsData') {
            const ns = r.u16(); const lens = r.u16a(ns); const tri = [];
            if (r.u8()) {
              for (const L of lens) {
                const st = r.u16a(L);
                for (let j = 0; j < L - 2; j++) {
                  const a = st[j], bb = st[j + 1], c = st[j + 2];
                  if (a !== bb && bb !== c && a !== c) { if (j % 2 === 0) tri.push(a, bb, c); else tri.push(a, c, bb); }
                }
              }
            }
            b.tri = new Uint16Array(tri);
          } else {
            r.u32();
            b.tri = r.u8() ? r.u16a(ntri * 3) : new Uint16Array(0);
            const nm = r.u16(); for (let m = 0; m < nm; m++) r.u16a(r.u16());
          }
          break;
        }
        case 'NiTexturingProperty': {
          net(r, b); b.apply = r.u32(); const n = r.u32(); b.tex = {};
          for (const name of ['base', 'dark', 'detail', 'gloss', 'glow']) if (r.u8()) b.tex[name] = texdesc(r);
          if (r.u8()) { b.tex.bump = texdesc(r); r.fs(6); }
          for (let j = 0; j < Math.max(0, n - 6); j++) if (r.u8()) b.tex['decal' + j] = texdesc(r);
          const ns = r.u32(); for (let j = 0; j < ns; j++) if (r.u8()) { texdesc(r); r.u32(); }
          break;
        }
        case 'NiSourceTexture': net(r, b); b.ext = r.u8(); b.file = r.s(); b.pix = r.i32(); r.u32(); r.u32(); r.u32(); r.u8(); r.u8(); break;
        case 'NiPixelData': {
          b.fmt = r.u32(); b.bpp = r.u8(); r.u32(); r.u32(); r.u8(); r.u32();
          for (let c = 0; c < 4; c++) { r.u32(); r.u32(); r.u8(); r.u8(); }
          r.i32();
          const nm = r.u32(); b.Bpp = r.u32(); b.mips = [];
          for (let m = 0; m < nm; m++) b.mips.push([r.u32(), r.u32(), r.u32()]);
          const n = r.u32(), nf = r.u32(); b.data = r.bytes(n * nf);
          break;
        }
        case 'NiMaterialProperty': net(r, b); b.amb = r.fs(3); b.dif = r.fs(3); b.spec = r.fs(3); b.emit = r.fs(3); b.gloss = r.f(); b.alpha = r.f(); break;
        case 'NiAlphaProperty': net(r, b); b.flags = r.u16(); b.thr = r.u8(); break;
        case 'NiSpecularProperty': case 'NiShadeProperty': case 'NiDitherProperty': case 'NiWireframeProperty': net(r, b); b.flags = r.u16(); break;
        case 'NiZBufferProperty': net(r, b); b.flags = r.u16(); r.u32(); break;
        case 'NiVertexColorProperty': net(r, b); r.u16(); b.vmode = r.u32(); b.lmode = r.u32(); break;
        case 'NiStencilProperty': net(r, b); r.u8(); r.u32(); r.u32(); r.u32(); r.u32(); r.u32(); r.u32(); b.draw = r.u32(); break;
        case 'NiStringExtraData': b.name = r.s(); b.str = r.s(); break;
        case 'NiColorExtraData': b.name = r.s(); r.fs(4); break;
        case 'NiIntegerExtraData': b.name = r.s(); r.u32(); break;
        case 'NiFloatExtraData': b.name = r.s(); r.f(); break;
        case 'NiFloatsExtraData': { b.name = r.s(); const n = r.u32(); r.i += 4 * n; break; }
        case 'NiRangeLODData': r.fs(3); { const n = r.u32(); b.ranges = []; for (let m = 0; m < n; m++) b.ranges.push(r.fs(2)); } break;
        case 'NiTransformController': case 'NiAlphaController': case 'NiVisController': case 'NiMaterialColorController':
        case 'NiTextureTransformController': case 'NiFlipController':
          r.i32(); r.u16(); r.f(); r.f(); b.start = r.f(); b.stop = r.f(); r.i32(); b.interp = r.i32();
          if (t === 'NiMaterialColorController') r.u16();
          else if (t === 'NiTextureTransformController') { r.u8(); b.slot = r.u32(); b.op = r.u32(); }
          else if (t === 'NiFlipController') { r.u32(); r.refs(); }
          break;
        case 'NiLookAtController': r.i32(); r.u16(); r.fs(4); r.i32(); r.u16(); r.i32(); break;
        case 'NiTransformInterpolator': r.fs(8); b.data = r.i32(); break;
        case 'NiFloatInterpolator': r.f(); b.data = r.i32(); break;
        case 'NiPoint3Interpolator': r.fs(3); r.i32(); break;
        case 'NiBoolInterpolator': r.u8(); r.i32(); break;
        case 'NiLookAtInterpolator': r.u16(); r.i32(); r.s(); r.fs(8); r.i32(); r.i32(); r.i32(); break;
        case 'NiBoolData': keys(r, 1, true); break;
        case 'NiFloatData': b.keys = keyList(r); break;
        case 'NiPosData': keys(r, 3); break;
        case 'NiTransformData': {
          const nr = r.u32();
          if (nr) { const kt = r.u32(); if (kt === 4) b.euler = [keyList(r), keyList(r), keyList(r)]; else r.i += nr * 4 * (kt === 3 ? 8 : 5); }
          keys(r, 3); keys(r, 1);
          break;
        }
        case 'NiTextureEffect': av(r, b); r.u8(); r.refs(); r.fs(12); r.u32(); r.u32(); r.u32(); r.u32(); r.i32(); r.u8(); r.fs(4); break;
        case 'NiDirectionalLight': case 'NiPointLight': case 'NiAmbientLight': case 'NiSpotLight':
          av(r, b); r.u8(); r.refs(); r.f(); r.fs(9);
          if (t === 'NiPointLight' || t === 'NiSpotLight') r.fs(3);
          if (t === 'NiSpotLight') r.fs(2);
          break;
        default: throw new Error('nif block ' + t);
      }
  }

  function mul(A, B) {
    const C = new Array(16).fill(0);
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { let s = 0; for (let k = 0; k < 4; k++) s += A[i * 4 + k] * B[k * 4 + j]; C[i * 4 + j] = s; }
    return C;
  }
  function local(b) {
    const R = b.r, s = b.s, t = b.t;
    return [R[0] * s, R[1] * s, R[2] * s, t[0], R[3] * s, R[4] * s, R[5] * s, t[1], R[6] * s, R[7] * s, R[8] * s, t[2], 0, 0, 0, 1];
  }
  const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

  // -> [{name, M, v, n, uvs, c, tri, base: {file, pix}|null, dark, dif, emit, alpha, blend, srcBlend, dstBlend, test, twoSided, vcol}]
  function shapes(blocks, lod) {
    const out = [];
    // a node turned by a NiTransformController with Euler keys (the garage's fans): its world matrix, the axis that
    // changes and how much per loop; the shapes below it get spin = {N, axis, delta, period, R (node -> shape)}
    const spinOf = (b, W) => {
      const c = b.ctrl >= 0 ? blocks[b.ctrl] : null;
      if (!c || c.type !== 'NiTransformController') return null;
      const ip = c.interp >= 0 ? blocks[c.interp] : null;
      const d = ip && ip.data >= 0 ? blocks[ip.data] : null;
      if (!d || !d.euler) return null;
      for (let a = 0; a < 3; a++) {
        const ks = d.euler[a];
        if (ks.length > 1 && Math.abs(ks[ks.length - 1][1] - ks[0][1]) > 1e-3) {
          return { N: W, axis: a, delta: ks[ks.length - 1][1] - ks[0][1], period: (c.stop - c.start) || (ks[ks.length - 1][0] - ks[0][0]) || 1 };
        }
      }
      return null;
    };
    const walk = (k, M, props, path, spin) => {
      const b = blocks[k];
      if (!b || !b.r) return;                 // past where a partly read file stops, or not a node
      const W = mul(M, local(b));
      const pr = props.concat(b.props || []);
      path = path.concat(b.name || '');
      if (!spin) { const sp = spinOf(b, W); if (sp) spin = Object.assign(sp, { Ninv: null }); }
      if (b.type === 'NiTriShape' || b.type === 'NiTriStrips') {
        if (b.flags & 1) return;
        const d = blocks[b.data];
        if (!d || !d.v || !d.tri.length) return;
        const sh = { name: b.name, path, M: W, v: d.v, n: d.n, uvs: d.uv, c: d.c, tri: d.tri, base: null, dark: null,
          dif: [1, 1, 1], emit: [0, 0, 0], alpha: 1, blend: false, test: false, twoSided: false, vcol: 0, spin: spin || null, uvAnim: null };
        for (const p of pr) {
          const q = p >= 0 ? blocks[p] : null; if (!q) continue;
          if (q.type === 'NiTexturingProperty') {
            const src = (td) => (td && td.src >= 0 && blocks[td.src] ? { file: blocks[td.src].file, pix: blocks[td.src].pix >= 0 ? blocks[blocks[td.src].pix] || null : null, uv: td.uv } : null);
            sh.base = src(q.tex.base); sh.dark = src(q.tex.dark);
            // a NiTextureTransformController on it: the texture slides (op 0 = U, 1 = V) through its float keys
            const c = q.ctrl >= 0 ? blocks[q.ctrl] : null;
            if (c && c.type === 'NiTextureTransformController') {
              const ip = c.interp >= 0 ? blocks[c.interp] : null;
              const fd = ip && ip.data >= 0 ? blocks[ip.data] : null;
              if (fd && fd.keys && fd.keys.length > 1) {
                const ks = fd.keys;
                sh.uvAnim = { op: c.op, from: ks[0][1], to: ks[ks.length - 1][1], period: (c.stop - c.start) || (ks[ks.length - 1][0] - ks[0][0]) || 1 };
              }
            }
          } else if (q.type === 'NiMaterialProperty') { sh.dif = q.dif; sh.emit = q.emit; sh.alpha = q.alpha; }
          else if (q.type === 'NiAlphaProperty') {
            sh.blend = !!(q.flags & 1); sh.srcBlend = (q.flags >> 1) & 15; sh.dstBlend = (q.flags >> 5) & 15;
            sh.test = !!(q.flags & 512); sh.thr = q.thr;
          } else if (q.type === 'NiStencilProperty') sh.twoSided = q.draw === 3;
          else if (q.type === 'NiVertexColorProperty') sh.vcol = q.vmode;
        }
        out.push(sh);
        return;
      }
      let kids = b.children || [];
      if (b.type === 'NiLODNode' && kids.length) {
        let pick = kids.length - 1;
        const ld = blocks[b.lod];
        if (ld && ld.ranges) { let best = Infinity; ld.ranges.forEach((rg, j) => { if (rg[0] < best) { best = rg[0]; pick = j; } }); }
        if (lod != null) pick = Math.min(lod, kids.length - 1);
        kids = [kids[pick]];
      }
      for (const c of kids) if (c >= 0) walk(c, W, pr, path, spin);
    };
    walk(0, I, [], [], null);
    return out;
  }

  // the named nodes with their world matrix (the car's _dm.nif: wheels/01..04, spoiler, num_front ...)
  function nodes(blocks) {
    const out = {};
    const walk = (k, M, pre) => {
      const b = blocks[k];
      if (!b || !b.r) return;
      const W = mul(M, local(b));
      const nm = pre ? pre + '/' + b.name : b.name;
      out[nm] = W;
      for (const c of b.children || []) if (c >= 0) walk(c, W, nm);
    };
    walk(0, I, '');
    return out;
  }

  const api = { parse, shapes, nodes, mul };
  if (typeof module !== 'undefined') module.exports = api; else root.NIF = api;
})(this);
