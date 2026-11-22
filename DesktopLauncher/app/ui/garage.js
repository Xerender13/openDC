'use strict';
/* The Garage window: the game's own garage (Data/World/garage.agt) and the character's cars (Data/vehicles.agt) in 3D,
   eight cars a floor on the turntable's spots (port1..port8 in garage.nif), the camera in front of the chosen car.
   ← / → change the car, Enter opens the details (and there uses the car), Esc goes back / closes.
   The garage music (Data/audio/bgm/DriftCity_garage.mp3) plays with a mute button; the choice is remembered. */
(function () {
  const THREE = window.THREE;
  // the car's colours: Data/effects.agt effects\VehicleColor.nxt (ColorID 1..32 -> R:G:B), read by the helper; this
  // copy is used when it can't be read. SKID_CAR_TB COLOR: 0x8X RRGGBB is RGB, otherwise ColorID = the top byte (0 = 1)
  // (client 0x4702f0: the body's colour from the top byte, the dealership's 0x08000002 = 8 Vanilla white)
  const PALETTE = { 1: [180, 180, 180], 2: [135, 206, 235], 3: [235, 212, 90], 4: [239, 232, 201], 5: [58, 182, 92], 6: [228, 11, 50],
    7: [12, 106, 222], 8: [233, 245, 245], 9: [27, 44, 88], 10: [27, 135, 81], 11: [42, 138, 227], 12: [235, 220, 47], 13: [255, 121, 0],
    14: [170, 205, 30], 15: [89, 54, 200], 16: [88, 102, 108], 17: [252, 84, 168], 18: [250, 165, 37], 19: [1, 73, 66], 20: [232, 23, 106],
    21: [74, 126, 184], 22: [170, 165, 171], 23: [31, 36, 39], 24: [70, 70, 70], 25: [160, 1, 21], 26: [10, 54, 207], 27: [108, 62, 108],
    28: [78, 125, 78], 29: [157, 147, 219], 30: [70, 70, 70], 31: [160, 1, 21], 32: [10, 54, 207] };
  let palette = PALETTE;
  const GLASS = [0.12, 0.13, 0.15];
  const PER_FLOOR = 8;
  // how bright the garage is, matched against a screenshot of the game's garage: the walls and floor with a light map,
  // the ones without, the light beams from the fans
  const LOOK = { light: 0.85, plain: 0.55, beams: 1.4 };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function texFromRGBA(w, h, data, opts) {
    const t = new THREE.DataTexture(data, w, h, THREE.RGBAFormat);
    t.flipY = false;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.magFilter = THREE.LinearFilter;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.generateMipmaps = true;
    t.anisotropy = 4;
    if (opts && opts.srgb !== false) t.encoding = THREE.sRGBEncoding;
    t.needsUpdate = true;
    return t;
  }
  // the game's textures are used as they are (its lighting works on the screen's colours, not linear light)
  function ddsTex(bytes) {
    const d = window.DDS.decode(bytes);
    return { w: d.w, h: d.h, data: new Uint8Array(d.data.buffer), tex: texFromRGBA(d.w, d.h, new Uint8Array(d.data.buffer), { srgb: false }) };
  }
  // NiPixelData (the garage keeps its textures inside the NIF): RGB24 or RGBA32, first mip level
  function pixTex(p) {
    const [w, h, off] = p.mips[0];
    const out = new Uint8Array(w * h * 4);
    const src = p.data;
    if (p.fmt === 0) { for (let i = 0, j = off; i < w * h; i++, j += 3) { out[i * 4] = src[j]; out[i * 4 + 1] = src[j + 1]; out[i * 4 + 2] = src[j + 2]; out[i * 4 + 3] = 255; } }
    else if (p.fmt === 1) out.set(src.subarray(off, off + w * h * 4));
    else if (p.fmt >= 4 && p.fmt <= 6) {      // DXT1/3/5 inside the NIF: wrap it as a DDS for the decoder
      const four = ['DXT1', 'DXT3', 'DXT5'][p.fmt - 4];
      const hdr = new Uint8Array(128); const dv = new DataView(hdr.buffer);
      dv.setUint32(0, 0x20534444, true); dv.setUint32(12, h, true); dv.setUint32(16, w, true);
      for (let i = 0; i < 4; i++) hdr[84 + i] = four.charCodeAt(i);
      const all = new Uint8Array(128 + src.length - off); all.set(hdr); all.set(src.subarray(off), 128);
      return ddsTex(all).tex;
    } else return null;
    return texFromRGBA(w, h, out, { srgb: false });
  }

  // a number plate's picture with its text: i_num01 has the club badge on the left, the others a frame around
  const plateCache = new Map();
  function plateTex(bytes, text, n) {
    if (!bytes) return null;
    const key = n + '|' + text;
    if (plateCache.has(key)) return plateCache.get(key);
    const d = window.DDS.decode(bytes);
    const src = document.createElement('canvas'); src.width = d.w; src.height = d.h;
    src.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(d.data.buffer.slice(0)), d.w, d.h), 0, 0);
    const cv = document.createElement('canvas'); cv.width = 512; cv.height = 200;
    const c = cv.getContext('2d');
    c.drawImage(src, 0, 0, cv.width, cv.height);
    const [x0, x1, y0, y1] = n === 1 ? [0.3, 0.95, 0.2, 0.86] : n === 2 ? [0.08, 0.92, 0.34, 0.9] : [0.08, 0.92, 0.2, 0.86];
    const w = (x1 - x0) * cv.width, h = (y1 - y0) * cv.height;
    let size = h * 0.72;
    c.font = `900 ${size}px Arial Black, Arial, sans-serif`;
    while (size > 12 && c.measureText(text).width > w * 0.94) { size -= 2; c.font = `900 ${size}px Arial Black, Arial, sans-serif`; }
    c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillStyle = '#1b2436'; c.fillText(text, (x0 + x1) / 2 * cv.width, (y0 + y1) / 2 * cv.height + size * 0.04);
    const t = new THREE.CanvasTexture(cv); t.anisotropy = 4;
    plateCache.set(key, t);
    return t;
  }

  function geometry(sh, uvset) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(sh.v, 3));
    if (sh.n) g.setAttribute('normal', new THREE.BufferAttribute(sh.n, 3));
    const uv = sh.uvs[uvset] || sh.uvs[0];
    if (uv) g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    if (sh.uvs[1]) g.setAttribute('uv2', new THREE.BufferAttribute(sh.uvs[1], 2));
    g.setIndex(new THREE.BufferAttribute(sh.tri, 1));
    if (!sh.n) g.computeVertexNormals();
    return g;
  }
  function placed(mesh, M) {
    mesh.matrixAutoUpdate = false;
    mesh.matrix.set(...M);
    return mesh;
  }
  function blending(sh, mat) {
    if (!sh.blend) return;
    mat.transparent = true;
    mat.depthWrite = false;
    if (sh.srcBlend === 0 && sh.dstBlend === 0) mat.blending = THREE.AdditiveBlending;
  }

  /* ---------------- the garage ---------------- */
  // the garage: root (fixed), turntable (the floor circle and the spot numbers: it turns like in the game), the fans and
  // the light beams that move (anim), the eight spots (port1..port8)
  function buildGarage(bytes, look) {
    const blocks = window.NIF.parse(bytes);
    const root = new THREE.Group(), turntable = new THREE.Group();
    const anim = [];
    const cache = new Map();
    const tex = (src) => {
      if (!src || !src.pix) return null;
      if (!cache.has(src.pix)) cache.set(src.pix, pixTex(src.pix));
      return cache.get(src.pix);
    };
    for (const sh of window.NIF.shapes(blocks)) {
      let map = tex(sh.base);
      const light = sh.dark ? tex(sh.dark) : null;
      const em = sh.emit[0] + sh.emit[1] + sh.emit[2] > 0;
      const add = sh.blend && sh.srcBlend === 0 && sh.dstBlend === 0;
      // the game's fixed pipeline: texture x light map x material, all in the screen's colours (no linear light)
      const col = new THREE.Color(...(map ? sh.dif : em ? sh.emit : [0.15, 0.16, 0.18]));
      const k = add ? look.beams : light ? look.light : em ? 1 : look.plain;
      const mat = new THREE.ShaderMaterial({
        uniforms: { uvTransform: { value: new THREE.Matrix3() }, map: { value: map }, lm: { value: light }, col: { value: col }, k: { value: k }, op: { value: sh.alpha },
          useMap: { value: !!map }, useLm: { value: !!light }, test: { value: sh.test ? 0.5 : -1 } },
        vertexShader: GV, fragmentShader: GF,
        side: sh.twoSided || sh.blend ? THREE.DoubleSide : THREE.FrontSide,
      });
      if (sh.blend) {
        mat.transparent = true; mat.depthWrite = false;
        if (add) { mat.blending = THREE.CustomBlending; mat.blendSrc = THREE.OneFactor; mat.blendDst = THREE.OneFactor; mat.blendEquation = THREE.AddEquation; }
      }
      if (sh.test) { mat.transparent = false; mat.depthWrite = true; }
      if (sh.alpha < 1 && !add) mat.transparent = true;
      const mesh = placed(new THREE.Mesh(geometry(sh, 0), mat), sh.M);
      const top = (sh.path[1] || '').toLowerCase();
      (top === 'floor' || top === 'number' ? turntable : root).add(mesh);
      if (sh.spin) {
        const N = new THREE.Matrix4().set(...sh.spin.N);
        anim.push({ kind: 'spin', mesh, N, rest: N.clone().invert().multiply(new THREE.Matrix4().set(...sh.M)), axis: sh.spin.axis, delta: sh.spin.delta, period: sh.spin.period });
      }
      if (sh.uvAnim && map) anim.push({ kind: 'uv', u: mat.uniforms.uvTransform.value, op: sh.uvAnim.op, from: sh.uvAnim.from, to: sh.uvAnim.to, period: sh.uvAnim.period });
    }
    const nodes = window.NIF.nodes(blocks);
    const ports = [];
    for (let i = 1; i <= PER_FLOOR; i++) {
      const k = Object.keys(nodes).find((n) => n.endsWith('/port' + i));
      const M = k ? nodes[k] : null;
      const a = (i - 1) * Math.PI / 4;
      ports.push(M ? [M[3], M[7], M[11]] : [-6.2 * Math.sin(a), -6.2 * Math.cos(a), 0]);
    }
    return { root, turntable, anim, ports };
  }
  const GV = `varying vec2 vUv; varying vec2 vUv2; attribute vec2 uv2;
    uniform mat3 uvTransform;
    void main() { vUv = (uvTransform * vec3(uv, 1.0)).xy; vUv2 = uv2; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
  const GF = `uniform sampler2D map; uniform sampler2D lm; uniform vec3 col; uniform float k; uniform float op; uniform bool useMap; uniform bool useLm; uniform float test;
    varying vec2 vUv; varying vec2 vUv2;
    void main() {
      vec4 c = vec4(col, op);
      if (useMap) c *= texture2D(map, vUv);
      if (test >= 0.0 && c.a < test) discard;
      if (useLm) c.rgb *= texture2D(lm, vUv2).rgb;
      gl_FragColor = vec4(c.rgb * k, c.a);
    }`;
  const R = new THREE.Matrix4();
  function animate(list, t) {
    for (const a of list) {
      const f = (t % a.period) / a.period;
      if (a.kind === 'spin') {
        const ang = a.delta * f;
        if (a.axis === 0) R.makeRotationX(ang); else if (a.axis === 1) R.makeRotationY(ang); else R.makeRotationZ(ang);
        a.mesh.matrix.copy(a.N).multiply(R).multiply(a.rest);
      } else {
        const v = a.from + (a.to - a.from) * f;
        if (a.op === 0) a.u.set(1, 0, v, 0, 1, 0, 0, 0, 1); else if (a.op === 1) a.u.set(1, 0, 0, 0, 1, v, 0, 0, 1);
      }
    }
  }

  /* ---------------- a car ---------------- */
  function hex3(h) { const c = new THREE.Color(h); return [c.r, c.g, c.b]; }
  // the car's colour: a paint drift item (RGB) wins; else SKID_CAR_TB COLOR: 0x8X RRGGBB is RGB, otherwise a palette
  // colour, its index in the top byte (the dealership's 0x01010102, 0x08000002) or the plain number
  function colorOf(car) {
    if (car.paint != null) return [(car.paint >> 16 & 255) / 255, (car.paint >> 8 & 255) / 255, (car.paint & 255) / 255];
    if (car.paintPal && palette[car.paintPal]) return palette[car.paintPal].map((v) => v / 255);
    const c = (car.color || 0) >>> 0;
    // 0x8X......: a colour as the game keeps it, 0x8X BB GG RR (a Windows colour; a red car holds 0x82030AFF: user's
    // Birdie, 2026-11-22); otherwise the high byte picks Data/effects.agt VehicleColor.nxt
    if ((c >>> 28) === 8) return [(c & 255) / 255, (c >> 8 & 255) / 255, (c >> 16 & 255) / 255];
    const rgb = palette[(c >>> 24) || 1] || palette[1];
    return rgb.map((v) => v / 255);
  }
  // Gamebryo's fixed-function lighting, per pixel: (ambient + diffuse x N.L) x material x texture + emissive, on the
  // screen's colours; the garage's light comes from above the gate (where the camera is)
  // the paint also mirrors the game's reflection picture (vehicle\texture\refl_img2.dds) by the view-space normal
  const CAR = { amb: 0.36, dif: 0.56, env: 0 };   // env: the reflection picture made bands across the cars (off)
  const CV = `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
    void main() { vUv = uv; vN = normalize(mat3(modelMatrix) * normal); vV = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
  const CF = `uniform sampler2D map; uniform bool useMap; uniform vec3 col; uniform vec3 emis; uniform float op; uniform float test;
    uniform vec3 L; uniform float amb; uniform float dif; uniform sampler2D env; uniform float envK; uniform bool twoLit;
    varying vec2 vUv; varying vec3 vN; varying vec3 vV;
    void main() {
      vec4 c = vec4(col, op);
      if (useMap) c *= texture2D(map, vUv);
      if (test >= 0.0 && c.a < test) discard;
      vec3 n = normalize(vN);
      if (!gl_FrontFacing) n = -n;
      float d = dot(n, L);
      float l = amb + dif * (twoLit ? abs(d) : max(d, 0.0));
      vec3 rgb = c.rgb * l + emis * c.rgb;
      if (envK > 0.0) { vec3 v = normalize(vV); if (!gl_FrontFacing) v = -v; rgb += texture2D(env, (twoLit ? abs(v.xy) * vec2(sign(v.x + 1e-4), 1.0) : v.xy) * 0.5 + 0.5).rgb * envK; }
      gl_FragColor = vec4(rgb, c.a);
    }`;
  const LIGHT = new THREE.Vector3(-0.35, 1.0, 0.75).normalize();
  function carMat(o) {
    const m = new THREE.ShaderMaterial({
      uniforms: { map: { value: o.map || null }, useMap: { value: !!o.map }, col: { value: new THREE.Color(...(o.col || [1, 1, 1])) },
        emis: { value: new THREE.Color(...(o.emis || [0, 0, 0])) }, op: { value: o.op == null ? 1 : o.op }, test: { value: o.test ? 0.5 : -1 },
        L: { value: LIGHT }, twoLit: { value: !!o.twoLit }, amb: { value: CAR.amb }, dif: { value: CAR.dif }, env: { value: o.env || null }, envK: { value: o.env ? CAR.env : 0 } },
      vertexShader: CV, fragmentShader: CF, side: o.side || THREE.FrontSide,
    });
    return m;
  }
  // a soft dark patch under the car (the game's shadow is a dark blob plus the car's outline cast on the floor)
  let BLOB = null;
  function blobTex() {
    if (BLOB) return BLOB;
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d');
    const r = g.createRadialGradient(64, 64, 8, 64, 64, 64);
    r.addColorStop(0, 'rgba(0,0,0,0.85)'); r.addColorStop(0.55, 'rgba(0,0,0,0.55)'); r.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = r; g.fillRect(0, 0, 128, 128);
    BLOB = new THREE.CanvasTexture(c);
    return BLOB;
  }

  /* ---------------- a car's drift items -> the files to load and the look for buildCar ---------------- */
  // list: [{cat, file, name, rgb}] (the launcher's helper resolves the files: odc_inv.look_entry)
  const WING = 7, AERO = 6, TIRE = 8, GTIRE = 48, ROOF = 47, DUCT = 52, BUMPER = 4, COOLER = 5, NEON = 2, PLATE = 9, DECAL = 11;
  // cars whose body has no bumpers of its own: the classic ('c') cars and the MINI copies of three of them
  const BARE = new Set(['pc_0215s', 'pc_0216s', 'pc_0242s']);
  const bare = (m) => /c$/.test(m || '') || BARE.has(m);
  function lookParts(model, list) {
    const out = new Set();
    const has = (c) => list.some((e) => e.cat === c);
    for (const e of list || []) {
      const f = e.file || '';
      if (e.cat === DECAL && e.index) { out.add('decal:' + e.index); continue; }
      if (!f || /^i_g_|^pc_aero/.test(f)) continue;
      if ([BUMPER, COOLER, AERO, WING, ROOF, DUCT, TIRE, GTIRE].includes(e.cat)) out.add(f);
      if (e.cat === WING && /^pc_\d+\w?_sp\d+/.test(f) && !f.startsWith(model)) out.add(f.replace(/_sp\d+$/, '_dm'));
    }
    if (bare(model)) { if (!has(BUMPER)) out.add(model + '_b01'); if (!has(COOLER)) out.add(model + '_i01'); }
    return [...out];
  }
  function lookBuild(model, list, f) {
    const P = (f && f.parts) || {};
    const nif = (n) => P[n] || P[n + '.nif'] || null;
    const node = (bytes, name) => { try { const n = window.NIF.nodes(window.NIF.parse(bytes)); const k = Object.keys(n).find((x) => x.endsWith('/items/' + name)); return k ? n[k] : null; } catch { return null; } };
    const look = { extras: [] };
    const has = (c) => (list || []).some((e) => e.cat === c);
    for (const e of list || []) {
      const file = e.file || '';
      if (e.cat === AERO && nif(file)) look.body = nif(file);
      else if (e.cat === WING && nif(file)) {
        if (file.startsWith(model)) look.wing = { bytes: nif(file) };
        else if (/^pc_/.test(file)) {
          // a wing made for another car: moved by the difference of the two cars' spoiler dummies
          const own = f.dm ? node(f.dm, 'spoiler') : null, od = nif(file.replace(/_sp\d+$/, '_dm')), orig = od ? node(od, 'spoiler') : null;
          look.wing = { bytes: nif(file), offset: own && orig ? [own[3] - orig[3], own[7] - orig[7], own[11] - orig[11]] : [0, 0, 0] };
        } else look.wing = { bytes: nif(file), at: 'spoiler' };
      } else if ((e.cat === TIRE || e.cat === GTIRE) && nif(file)) look.tire = nif(file);
      else if (e.cat === ROOF && nif(file)) look.extras.push({ bytes: nif(file), at: 'roof' });
      else if (e.cat === DUCT && nif(file)) look.extras.push({ bytes: nif(file), at: 'intake' });
      else if ((e.cat === BUMPER || e.cat === COOLER) && nif(file)) look.extras.push({ bytes: nif(file) });
      else if (e.cat === DECAL && e.index) look.decal = { id: String(e.index), rgb: e.rgb == null ? null : e.rgb };
      else if (e.cat === PLATE) look.plate = { n: e.plate || 1, text: e.text || '' };
      else if (e.cat === NEON && e.rgb != null) look.neon = [(e.rgb >> 16 & 255) / 255, (e.rgb >> 8 & 255) / 255, (e.rgb & 255) / 255];
    }
    if (bare(model)) for (const [c, suf] of [[BUMPER, '_b01'], [COOLER, '_i01']]) if (!has(c) && nif(model + suf)) look.extras.push({ bytes: nif(model + suf) });
    return look;
  }

  // the special versions are drawn at their own size, as in the game: ST 20 % smaller, MINI 30 % smaller,
  // Xmas 15 % smaller, BT 5 % bigger (by the car's name)
  function carSize(name) {
    const n = String(name || '');
    if (/\bMINI\b/i.test(n)) return 0.7;
    if (/\bX-?mas\b/i.test(n)) return 0.85;
    if (/\bST\b/.test(n)) return 0.8;
    if (/\bBT\b/.test(n)) return 1.05;
    return 1;
  }

  function buildCar(model, files, textures, car) {
    const group = new THREE.Group();
    const T = new Map();
    const tex = (file) => {
      if (!file) return null;
      const base = file.replace(/\\/g, '/').split('/').pop().replace(/\.[^.]+$/, '').toLowerCase();
      if (!T.has(base)) {
        const b = textures[base];
        if (!b && window.__odcMiss) window.__odcMiss.push(model + ':' + base);
        try { T.set(base, b ? ddsTex(b).tex : null); } catch { T.set(base, null); if (window.__odcMiss) window.__odcMiss.push(model + ':bad:' + base); }
      }
      return T.get(base);
    };
    const paint = colorOf(car);
    const glass = car.tint != null ? [(car.tint >> 16 & 255) / 255 * 0.35, (car.tint >> 8 & 255) / 255 * 0.35, (car.tint & 255) / 255 * 0.35] : GLASS;
    // newer cars: <model>_map.dds read through the second UV set, the mask's red = paint, blue = glass
    let comp = null, maskTex = null;
    if (files.map && files.mask) {
      try {
        const m = ddsTex(files.map), k = ddsTex(files.mask);
        maskTex = k.tex;
        const out = new Uint8Array(m.w * m.h * 4);
        for (let y = 0; y < m.h; y++) {
          const ky = Math.min(k.h - 1, Math.floor(y * k.h / m.h));
          for (let x = 0; x < m.w; x++) {
            const kx = Math.min(k.w - 1, Math.floor(x * k.w / m.w));
            const ko = (ky * k.w + kx) * 4, o = (y * m.w + x) * 4;
            const r = k.data[ko] / 255, bl = k.data[ko + 2] / 255;
            // the mask's red marks the paint, blue the glass: those take the car's colours (the map holds a placeholder
            // swatch there, orange on the 04xx cars), the rest keeps the map
            for (let c = 0; c < 3; c++) out[o + c] = Math.max(0, Math.min(255, m.data[o + c] * Math.max(0, 1 - r - bl) + 255 * (r * paint[c] + bl * glass[c])));
            out[o + 3] = 255;
          }
        }
        comp = texFromRGBA(m.w, m.h, out, { srgb: false });
      } catch { comp = null; }
    }
    // the body, and its lights (<model>_light.nif: tail lights, indicators), as the game puts them together
    // the older cars (pc_XXXXc): their nearest LOD has the hood (and more) open, the engine bay showing; the game's
    // garage shows the middle one, whole and painted
    // car.look (the drift shop's try-on): body = another body NIF (aero sets), wing = {bytes, at, offset} in place of its own
    // wing (null: none), extras = [{bytes, at, offset}] (roof items at the 'roof' dummy, air ducts at 'intake', classic
    // bumpers / intercoolers in place), tire = another tire NIF, neon = [r, g, b] under the car
    const look = car.look || {};
    // a decal (drift shop, category 11), as the game draws it (client 0x467350): decal.nxt's pieces for this car are
    // drawn into the body's paint texture (car_color01), each inside the rectangle of its area of the body's texture
    // layout (first texture coordinates: the roof, the two sides, front and rear laid out flat); a piece's centre and
    // size are in thousandths / percent of that rectangle, turned by its angle; in the decal's colour
    const decalSpec = look.decal && files.decals ? files.decals[look.decal.id] : null;
    let decalRects = null;
    // which area a face belongs to, by its normal: 0 roof (up), 1 / 2 the sides, 3 front, 4 rear (-1: underneath)
    const areaOf = (nx, ny, nz) => {
      const ax = Math.abs(nx), ay = Math.abs(ny), az = Math.abs(nz);
      if (az >= ax && az >= ay) return nz > 0 ? 0 : -1;
      if (ax >= ay) return nx > 0 ? 2 : 1;
      return ny > 0 ? 3 : 4;
    };
    const decalAreas = () => {
      if (decalRects) return decalRects;
      const pts = [[], [], [], [], []];
      for (const s2 of shapes) {
        if (!(s2.base && /car_color/i.test(s2.base.file || '')) || !s2.uvs[0] || !s2.n) continue;
        const u0 = s2.uvs[0];
        for (let t = 0; t < s2.tri.length; t += 3) {
          // a face's normal (world), its corners' texture coordinates go to its area
          const a = s2.tri[t], b = s2.tri[t + 1], c = s2.tri[t + 2];
          let nx = 0, ny = 0, nz = 0;
          for (const k of [a, b, c]) for (let q = 0; q < 3; q++) {
            const v = s2.M[q * 4] * s2.n[k * 3] + s2.M[q * 4 + 1] * s2.n[k * 3 + 1] + s2.M[q * 4 + 2] * s2.n[k * 3 + 2];
            if (q === 0) nx += v; else if (q === 1) ny += v; else nz += v;
          }
          const ar = areaOf(nx, ny, nz);
          if (ar < 0) continue;
          for (const k of [a, b, c]) if (u0[k * 2] < 0.99 || u0[k * 2 + 1] < 0.99) pts[ar].push(u0[k * 2], u0[k * 2 + 1]);
        }
      }
      // the rectangle of each area: its texture coordinates' extent (the 1st..99th percentile, past stray corners)
      decalRects = pts.map((p) => {
        if (p.length < 6) return null;
        const us = [], vs = [];
        for (let i = 0; i < p.length; i += 2) { us.push(p[i]); vs.push(p[i + 1]); }
        us.sort((x, y) => x - y); vs.sort((x, y) => x - y);
        const q = (arr, f) => arr[Math.min(arr.length - 1, Math.max(0, Math.round(f * (arr.length - 1))))];
        return [q(us, 0.01), q(vs, 0.01), q(us, 0.99), q(vs, 0.99)];
      });
      return decalRects;
    };
    const decalMeshes = (sh, put) => {
      if (!decalSpec || !sh.uvs[0]) return;
      // the areas' rectangles: the game's layout of the paint texture (the same on every car: roof in the middle, the
      // sides above and below, front and rear at the ends), measured on the newer cars' bodies
      const R = decalAreas();
      const rgbI = look.decal.rgb;
      const n = sh.v.length / 3, u0 = sh.uvs[0];
      for (const pc of decalSpec.pieces) {
        const map = tex(pc.tex);
        if (!map) continue;
        const rect = pc.area === 5 ? [0, 0, 1, 1] : R[pc.area];
        if (!rect) continue;
        const [rx0, ry0, rx1, ry1] = rect, rw = (rx1 - rx0) || 1, rh = (ry1 - ry0) || 1;
        const uv = new Float32Array(n * 2), on = new Float32Array(n);
        const cr = Math.cos(-pc.rot * Math.PI / 180), sr = Math.sin(-pc.rot * Math.PI / 180);
        for (let i = 0; i < n; i++) {
          const tu = u0[i * 2], tv = u0[i * 2 + 1];
          if (pc.area === 5) { uv[i * 2] = tu; uv[i * 2 + 1] = tv; on[i] = 1; continue; }
          const X = (tu - rx0) / rw * 1000, Y = (tv - ry0) / rh * 1000;
          const dx = X - pc.x, dy = Y - pc.y;
          let u = (dx * cr - dy * sr) / (pc.w * 10) + 0.5, v = (dx * sr + dy * cr) / (pc.h * 10) + 0.5;
          if (pc.flip[0]) u = 1 - u;
          if (pc.flip[1]) v = 1 - v;
          v = 1 - v;                                   // the pictures' rows run upwards in the render target
          uv[i * 2] = u; uv[i * 2 + 1] = v;
          on[i] = X >= -0.5 && X <= 1000.5 && Y >= -0.5 && Y <= 1000.5 ? 1 : 0;      // inside the area's rectangle
        }
        const g = geometry(sh, 0).clone();
        g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
        g.setAttribute('dOn', new THREE.BufferAttribute(on, 1));
        // the windows: where the body's mask (second UV set) is blue (glass), the decal is not drawn
        const useMask = !!(maskTex && sh.uvs.length > 1 && sh.uvs[1]);
        g.setAttribute('uvM', new THREE.BufferAttribute(useMask ? new Float32Array(sh.uvs[1]) : new Float32Array(n * 2), 2));
        const col = rgbI != null ? new THREE.Color(((rgbI >> 16) & 255) / 255, ((rgbI >> 8) & 255) / 255, (rgbI & 255) / 255) : new THREE.Color(pc.rgb[0] / 255, pc.rgb[1] / 255, pc.rgb[2] / 255);
        const mat = new THREE.ShaderMaterial({
          uniforms: { map: { value: map }, col: { value: col }, clip: { value: pc.area !== 5 }, mask: { value: useMask ? maskTex : null }, useMask: { value: useMask } },
          vertexShader: 'attribute float dOn; attribute vec2 uvM; varying vec2 vU; varying vec2 vM; varying float vOn; void main(){ vU = uv; vM = uvM; vOn = dOn; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
          fragmentShader: 'uniform sampler2D map; uniform sampler2D mask; uniform bool useMask; uniform vec3 col; uniform bool clip; varying vec2 vU; varying vec2 vM; varying float vOn; void main(){ if (clip && (vOn < 0.5 || vU.x < 0.0 || vU.x > 1.0 || vU.y < 0.0 || vU.y > 1.0)) discard; if (useMask) { vec4 k = texture2D(mask, vM); if (k.b > 0.4 && k.b > k.r) discard; } vec4 c = texture2D(map, vU); if (c.a < 0.04) discard; gl_FragColor = vec4(c.rgb * col, c.a); }',
          transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -8,
        });
        const m = put(new THREE.Mesh(g, mat)); m.renderOrder = 2;
      }
    };
    let decalBox = null;
    const decalMeshesSide = (sh, put) => {
      if (!decalSpec) return;
      const W3 = (i) => [0, 1, 2].map((a) => sh.M[a * 4] * sh.v[i] + sh.M[a * 4 + 1] * sh.v[i + 1] + sh.M[a * 4 + 2] * sh.v[i + 2] + sh.M[a * 4 + 3]);
      if (!decalBox) {
        // the painted body's box; its sides' height from the lowest side-facing paint (not the floor pan)
        decalBox = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9, 1e9];
        for (const s2 of shapes) {
          if (!(s2.base && /car_color/i.test(s2.base.file || ''))) continue;
          for (let i = 0; i < s2.v.length; i += 3) {
            const q = [0, 1, 2].map((a) => s2.M[a * 4] * s2.v[i] + s2.M[a * 4 + 1] * s2.v[i + 1] + s2.M[a * 4 + 2] * s2.v[i + 2] + s2.M[a * 4 + 3]);
            for (let a = 0; a < 3; a++) { decalBox[a] = Math.min(decalBox[a], q[a]); decalBox[a + 3] = Math.max(decalBox[a + 3], q[a]); }
            const nx = s2.n ? s2.M[0] * s2.n[i] + s2.M[1] * s2.n[i + 1] + s2.M[2] * s2.n[i + 2] : 0;
            if (Math.abs(nx) > 0.6) decalBox[6] = Math.min(decalBox[6], q[2]);
          }
        }
        if (decalBox[6] > 1e8) decalBox[6] = decalBox[2];
      }
      const [x0, y0, z0, x1, y1, z1, zs] = decalBox, L = (y1 - y0) || 1, Wd = (x1 - x0) || 1, H = (z1 - z0) || 1, Hs = (z1 - zs) || 1;
      const rgbI = look.decal.rgb;
      const n = sh.v.length / 3;
      for (const pc of decalSpec.pieces) {
        const map = tex(pc.tex);
        if (!map) continue;
        const uv = new Float32Array(n * 2), on = new Float32Array(n);
        const cr = Math.cos(-pc.rot * Math.PI / 180), sr = Math.sin(-pc.rot * Math.PI / 180);
        for (let i = 0; i < n; i++) {
          if (pc.area === 5) { uv[i * 2] = sh.uvs[0] ? sh.uvs[0][i * 2] : 0; uv[i * 2 + 1] = sh.uvs[0] ? sh.uvs[0][i * 2 + 1] : 0; on[i] = sh.uvs[0] ? 1 : 0; continue; }
          const p = W3(i * 3);
          const nx = sh.n ? sh.M[0] * sh.n[i * 3] + sh.M[1] * sh.n[i * 3 + 1] + sh.M[2] * sh.n[i * 3 + 2] : 0;
          const ny = sh.n ? sh.M[4] * sh.n[i * 3] + sh.M[5] * sh.n[i * 3 + 1] + sh.M[6] * sh.n[i * 3 + 2] : 0;
          const nz = sh.n ? sh.M[8] * sh.n[i * 3] + sh.M[9] * sh.n[i * 3 + 1] + sh.M[10] * sh.n[i * 3 + 2] : 1;
          let X, Y, face;
          if (pc.area === 1 || pc.area === 2) {
            const left = pc.area === 1;
            X = (p[1] - y0) / L * 1000; Y = 500 + (left ? 1 : -1) * (p[2] - zs) / Hs * 500;
            face = left ? nx < -0.15 : nx > 0.15;
          } else if (pc.area === 0) { X = (p[1] - y0) / L * 1000; Y = (x1 - p[0]) / Wd * 1000; face = nz > 0.35; }
          else { X = (p[2] - z0) / H * 1000; Y = (x1 - p[0]) / Wd * 1000; face = pc.area === 4 ? ny < -0.35 : ny > 0.35; }
          const dx = X - pc.x, dy = Y - pc.y;
          let u = (dx * cr - dy * sr) / (pc.w * 10) + 0.5, v = (dx * sr + dy * cr) / (pc.h * 10) + 0.5;
          if (pc.flip[0]) u = 1 - u;
          if (pc.flip[1]) v = 1 - v;
          if (pc.area === 1 || pc.area === 2) { u = 1 - u; v = 1 - v; }   // the side pictures: front first, top up
          uv[i * 2] = u; uv[i * 2 + 1] = v; on[i] = face ? 1 : 0;
        }
        const g = geometry(sh, 0).clone();
        g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
        g.setAttribute('dOn', new THREE.BufferAttribute(on, 1));
        // the windows: where the body's mask (second UV set) is blue (glass), the decal is not drawn
        const useMask = !!(maskTex && sh.uvs.length > 1 && sh.uvs[1]);
        g.setAttribute('uvM', new THREE.BufferAttribute(useMask ? new Float32Array(sh.uvs[1]) : new Float32Array(n * 2), 2));
        const col = rgbI != null ? new THREE.Color(((rgbI >> 16) & 255) / 255, ((rgbI >> 8) & 255) / 255, (rgbI & 255) / 255) : new THREE.Color(pc.rgb[0] / 255, pc.rgb[1] / 255, pc.rgb[2] / 255);
        const mat = new THREE.ShaderMaterial({
          uniforms: { map: { value: map }, col: { value: col }, clip: { value: pc.area !== 5 }, mask: { value: useMask ? maskTex : null }, useMask: { value: useMask } },
          vertexShader: 'attribute float dOn; attribute vec2 uvM; varying vec2 vU; varying vec2 vM; varying float vOn; void main(){ vU = uv; vM = uvM; vOn = dOn; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
          fragmentShader: 'uniform sampler2D map; uniform sampler2D mask; uniform bool useMask; uniform vec3 col; uniform bool clip; varying vec2 vU; varying vec2 vM; varying float vOn; void main(){ if (clip && (vOn < 0.5 || vU.x < 0.0 || vU.x > 1.0 || vU.y < 0.0 || vU.y > 1.0)) discard; if (useMask) { vec4 k = texture2D(mask, vM); if (k.b > 0.4 && k.b > k.r) discard; } vec4 c = texture2D(map, vU); if (c.a < 0.04) discard; gl_FragColor = vec4(c.rgb * col, c.a); }',
          transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -8,
        });
        const m = put(new THREE.Mesh(g, mat)); m.renderOrder = 2;
      }
    };
    let dmNodes = {};
    try { if (files.dm) dmNodes = window.NIF.nodes(window.NIF.parse(files.dm)); } catch (e) { console.error('dm', model, e); }
    const node = (name) => { const k = Object.keys(dmNodes).find((n) => n.endsWith('/items/' + name)); return k ? dmNodes[k] : null; };
    // where a part goes: at a dummy node of the car (translation only), shifted by offset (a wing made for another car)
    const partMatrix = (at, offset) => {
      const m = new THREE.Matrix4();
      const N = at ? node(at) : null;
      const o = offset || [0, 0, 0];
      m.makeTranslation((N ? N[3] : 0) + o[0], (N ? N[7] : 0) + o[1], (N ? N[11] : 0) + o[2]);
      return m;
    };
    const shapes = window.NIF.shapes(window.NIF.parse(look.body || files.body), /c$/.test(model) ? 1 : null);
    const lightShapes = [];
    if (files.light) { try { lightShapes.push(...window.NIF.shapes(window.NIF.parse(files.light))); } catch (e) { console.error('lights', model, e); } }
    const parts = [];                       // [shapes, Matrix4 | null, role]
    const wing = look.wing === undefined ? (files.spoiler ? { bytes: files.spoiler } : null) : look.wing;
    for (const p of [wing, ...(look.extras || [])]) {
      if (!p || !p.bytes) continue;
      try { parts.push([window.NIF.shapes(window.NIF.parse(p.bytes)), p.at || p.offset ? partMatrix(p.at, p.offset) : null]); } catch (e) { console.error('part', e); }
    }
    // the lights by their node in <model>_light.nif: tail (brake), winker_left / _right, reversing, head; off until asked
    const lights = { tail: [], winkL: [], winkR: [], rev: [], head: [], volume: [] };
    const roleOf = (sh) => {
      const p = (sh.path || []).join('/').toLowerCase() + '/' + String(sh.name || '').toLowerCase() + '/' + String((sh.base && sh.base.file) || '').toLowerCase();
      if (/spotlight|pointlight|\/ld\d/.test(p)) return 'volume';         // the light's helper boxes: never drawn
      // where the shape sits on the car (Y forward, X right): for lights named only by their texture or not at all
      let cx = 0, cy = 0;
      const n = sh.v.length / 3;
      for (let i = 0; i < sh.v.length; i += 3) { cx += sh.M[0] * sh.v[i] + sh.M[1] * sh.v[i + 1] + sh.M[2] * sh.v[i + 2] + sh.M[3]; cy += sh.M[4] * sh.v[i] + sh.M[5] * sh.v[i + 1] + sh.M[6] * sh.v[i + 2] + sh.M[7]; }
      cx /= n || 1; cy /= n || 1;
      if (/winker|blink|turn/.test(p)) return /left|_l\b|_l\//.test(p) ? 'winkL' : /right|_r\b|_r\//.test(p) ? 'winkR' : cx < 0 ? 'winkL' : 'winkR';
      if (/revers|back_?up/.test(p)) return 'rev';
      if (/head|lamp|front/.test(p)) return 'head';
      if (/tail|brake|stop|rear/.test(p)) return 'tail';
      return cy > 0 ? 'head' : 'tail';
    };
    const draw = (list, pre, role) => {
      for (const sh of list) {
        const file = sh.base && sh.base.file;
        const M = pre ? new THREE.Matrix4().multiplyMatrices(pre, new THREE.Matrix4().set(...sh.M)) : null;
        const put = (mesh) => { if (M) { mesh.matrixAutoUpdate = false; mesh.matrix.copy(M); } else placed(mesh, sh.M); group.add(mesh); return mesh; };
        if (sh.name === 'OutlineMesh') {
          // the toon outline (a slightly bigger hull, back faces): pushed back in depth so it only shows round the car's
          // edges and not as lines through thin panels (hood, roof)
          const mat = new THREE.MeshBasicMaterial({ color: 0x0b0c0e, side: THREE.BackSide, polygonOffset: true, polygonOffsetFactor: 3, polygonOffsetUnits: 12 });
          put(new THREE.Mesh(geometry(sh, 0), mat));
          continue;
        }
        // paint: the car_color layer (parts made to be painted carry it too)
        const isPaint = file && /car_color/i.test(file);
        if (isPaint) {
          const env = tex('refl_img2');
          const useComp = comp && sh.uvs.length > 1 && !pre;
          const mat = useComp ? carMat({ map: comp, env }) : carMat({ col: paint, env });
          const mesh = put(new THREE.Mesh(geometry(sh, useComp ? 1 : 0), mat));
          // a paint layer the game blends over the textured body under it (older cars: the hood, the doors): drawn
          // after it and pulled forward so it wins where both lie on the same surface
          if (sh.blend) { mat.polygonOffset = true; mat.polygonOffsetFactor = -1; mat.polygonOffsetUnits = -4; mesh.renderOrder = 1; }
          // the car's own livery (<model>_decal01.dds: the ST / BT cars' stripes and logos) over the paint
          if (!pre) (comp ? decalMeshes : decalMeshesSide)(sh, put);
          continue;
        }
        const map = tex(file);
        if (file && !map && sh.blend) continue;          // a shine layer whose texture the pack does not have
        // a textured part whose material colour is black (the wings' spoiller_map parts): the game's toon shading
        // shows the texture as it is, so it is not darkened to black here
        const dif = map && sh.dif && sh.dif[0] + sh.dif[1] + sh.dif[2] < 0.05 ? [1, 1, 1] : sh.dif;
        const mat = carMat({ map, col: dif, emis: sh.emit, op: sh.alpha, test: sh.test, side: sh.twoSided ? THREE.DoubleSide : THREE.FrontSide });
        if (sh.blend) { mat.transparent = true; mat.depthWrite = false; }
        if (sh.test) { mat.transparent = false; mat.depthWrite = true; }
        if (sh.alpha < 1) mat.transparent = true;
        const mesh = put(new THREE.Mesh(geometry(sh, 0), mat));
        if (role) {
          const r = roleOf(sh) || 'tail';
          lights[r].push(mesh);
          mesh.visible = false;
          // the game fades a lamp in through its material's alpha (0 in the file while off): lit = fully drawn
          if (mat.uniforms && mat.uniforms.op && mat.uniforms.op.value < 0.5) mat.uniforms.op.value = 1;
          if (sh.blend) mat.blending = THREE.AdditiveBlending;
          // a lamp without a picture (head light glass, light cones): lit in the lamp's own colour
          if (!map) { mat.uniforms.col.value.setRGB(...(r === 'head' ? [1, 0.95, 0.8] : r === 'tail' ? [1, 0.1, 0.08] : r === 'rev' ? [1, 1, 1] : [1, 0.6, 0.1])); mat.uniforms.emis.value.setRGB(1, 1, 1); mat.transparent = true; mat.blending = THREE.AdditiveBlending; mat.depthWrite = false; mat.uniforms.op.value = 0.6; }
        }
      }
    };
    draw(shapes, null);
    draw(lightShapes, null, true);
    for (const [list, pre] of parts) draw(list, pre);
    group.userData.lights = lights;
    // the neon: neon_<model>.nif under the car, in the neon's colour, added on the floor
    if (look.neon && files.neon) {
      try {
        for (const sh of window.NIF.shapes(window.NIF.parse(files.neon))) {
          const map = tex(sh.base && sh.base.file);
          if (!map) continue;                       // without its glow picture the neon would be a flat plate
          const nmat = new THREE.MeshBasicMaterial({ map, color: new THREE.Color(...look.neon), transparent: true, depthWrite: false, opacity: 0.85,
            side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -4 });
          const m = placed(new THREE.Mesh(geometry(sh, 0), nmat), sh.M); m.renderOrder = 3; group.add(m);
        }
      } catch (e) { console.error('neon', e); }
    }
    // the number plates at the dummies num_front / num_back: the plate's picture with its text (DRIFT CITY by default)
    if (look.plate !== false) {
      try {
        const pl = look.plate || { n: 1, text: '' };
        const pt = plateTex(textures && textures['i_num0' + (pl.n || 1)], pl.text || 'DRIFT CITY', pl.n || 1);
        if (pt) {
          const W = 0.41, H = 0.16, g = new THREE.BufferGeometry();
          g.setAttribute('position', new THREE.BufferAttribute(new Float32Array([W / 2, 0, -H / 2, -W / 2, 0, -H / 2, -W / 2, 0, H / 2, W / 2, 0, H / 2]), 3));
          g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]), 2));
          g.setIndex([0, 1, 2, 0, 2, 3]);
          const pmat = new THREE.MeshBasicMaterial({ map: pt, color: 0xe6e6e6, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -4 });
          for (const at of ['num_front', 'num_back']) {
            const N = node(at); if (!N) continue;
            const m = new THREE.Mesh(g, pmat); m.matrixAutoUpdate = false;
            m.matrix.set(...N).multiply(new THREE.Matrix4().makeTranslation(0, 0.012, 0));
            m.userData.plate = true; group.add(m);
          }
        }
      } catch (e) { console.error('plate', e); }
    }
    if (look.tire) files = Object.assign({}, files, { tire: look.tire });
    // the wheels: the tire NIF at the dummy nodes wheels/01..04 (01, 02 front), sized by the car's tire scale (mm)
    let minZ = 0;
    const steer = [];
    group.userData.steer = steer;
    if (files.dm && files.tire) {
      const nodes = window.NIF.nodes(window.NIF.parse(files.dm));
      const tire = window.NIF.shapes(window.NIF.parse(files.tire));
      let zmin = Infinity, zmax = -Infinity;
      for (const sh of tire) for (let i = 0; i < sh.v.length; i += 3) { const z = sh.M[8] * sh.v[i] + sh.M[9] * sh.v[i + 1] + sh.M[10] * sh.v[i + 2] + sh.M[11]; zmin = Math.min(zmin, z); zmax = Math.max(zmax, z); }
      const dia = zmax > zmin ? zmax - zmin : 0.2;
      const tg = tire.map((sh) => [sh, geometry(sh, 0), carMat({ map: tex(sh.base && sh.base.file), col: sh.dif, side: THREE.DoubleSide })]);
      minZ = Infinity;
      for (const [k, M] of Object.entries(nodes)) {
        const m = k.match(/\/wheels\/0([1-4])$/);
        if (!m) continue;
        const front = m[1] === '1' || m[1] === '2';
        const s = ((front ? car.tire_scale[0] : car.tire_scale[1]) || 660) / 1000 / dia;
        const wd = (front ? car.tire_width[0] : car.tire_width[1]) || 1;
        const left = M[3] < 0;
        // each wheel turns round its own upright (the front ones steer): holder at the hub -> flip / size -> the tire
        const hub = new THREE.Group();
        hub.position.set(M[3], M[7], M[11]);
        const inner = new THREE.Group();
        inner.matrixAutoUpdate = false;
        const S = new THREE.Matrix4();
        if (left) S.multiply(new THREE.Matrix4().makeRotationZ(Math.PI));
        S.multiply(new THREE.Matrix4().makeScale(s * wd, s, s));
        inner.matrix.copy(S);
        hub.add(inner);
        for (const [sh, g, mat] of tg) {
          const mesh = new THREE.Mesh(g, mat);
          mesh.matrixAutoUpdate = false;
          mesh.matrix.set(...sh.M);
          inner.add(mesh);
        }
        group.add(hub);
        if (front) steer.push(hub);
        minZ = Math.min(minZ, M[11] - (s * dia) / 2);
      }
      if (!isFinite(minZ)) minZ = 0;
    }
    group.userData.lift = -minZ;
    // the shadow: <model>_s.nif (the plain body the game casts it with) flattened onto the floor along the light, each
    // pixel darkened once (stencil), over a soft dark patch the size of the car
    const ground = minZ + 0.012;
    let bx0 = Infinity, bx1 = -Infinity, by0 = Infinity, by1 = -Infinity;
    if (files.shadow) {
      try {
        const ld = [-0.35, -0.75, 1.0];        // the light, game axes (x, y, z up): from above and the gate
        const smat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.42, depthWrite: false, side: THREE.DoubleSide,
          stencilWrite: true, stencilRef: 1, stencilFunc: THREE.NotEqualStencilFunc, stencilZPass: THREE.ReplaceStencilOp });
        for (const sh of window.NIF.shapes(window.NIF.parse(files.shadow))) {
          const M = sh.M, v = sh.v, out = new Float32Array(v.length);
          for (let i = 0; i < v.length; i += 3) {
            const x = M[0] * v[i] + M[1] * v[i + 1] + M[2] * v[i + 2] + M[3];
            const y = M[4] * v[i] + M[5] * v[i + 1] + M[6] * v[i + 2] + M[7];
            const z = M[8] * v[i] + M[9] * v[i + 1] + M[10] * v[i + 2] + M[11];
            const h = Math.max(0, z - ground);
            out[i] = x - ld[0] * h / ld[2]; out[i + 1] = y - ld[1] * h / ld[2]; out[i + 2] = ground;
            bx0 = Math.min(bx0, x); bx1 = Math.max(bx1, x); by0 = Math.min(by0, y); by1 = Math.max(by1, y);
          }
          const g = new THREE.BufferGeometry();
          g.setAttribute('position', new THREE.BufferAttribute(out, 3));
          g.setIndex(new THREE.BufferAttribute(sh.tri, 1));
          const m = new THREE.Mesh(g, smat); m.renderOrder = 2; m.userData.shadow = true;
          group.add(m);
        }
      } catch (e) { console.error('shadow', e); }
    }
    if (!isFinite(bx0)) { bx0 = -1; bx1 = 1; by0 = -2.2; by1 = 2.2; }
    const blob = new THREE.Mesh(new THREE.PlaneGeometry((bx1 - bx0) * 1.45, (by1 - by0) * 1.25),
      new THREE.MeshBasicMaterial({ map: blobTex(), transparent: true, depthWrite: false, opacity: 0.75 }));
    blob.position.set((bx0 + bx1) / 2, (by0 + by1) / 2, ground - 0.004);
    blob.renderOrder = 1; blob.userData.shadow = true;
    group.add(blob);
    const k = carSize(car && car.name);
    if (k !== 1) { group.scale.setScalar(k); group.userData.lift = (group.userData.lift || 0) * k; }
    group.userData.size = k;
    return group;
  }

  /* ---------------- the window ---------------- */
  async function open(opts) {
    const { inv, T, onUse, onSell, onClose } = opts;
    const cars = inv.cars.slice();
    if (!cars.length) return;
    let sel = Math.max(0, cars.findIndex((c) => c.current));
    let floor = Math.floor(sel / PER_FLOOR);
    let details = false, busy = false;
    const ctl = { steer: 0 };

    const el = document.createElement('div');
    el.id = 'garage';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', T.garTitle);
    el.innerHTML = `
      <canvas id="garCv"></canvas>
      <header class="gtop"><h1>${esc(T.garTitle)}</h1><nav class="gfl" aria-label="${esc(T.garFloors)}"></nav><div class="grow"></div>
        <span class="gmsg muted small" id="garMsg"></span>
        <button class="gico" id="garOpt" aria-expanded="false" aria-controls="garPanel" aria-label="${esc(T.garOptions)}" title="${esc(T.garOptions)}"><svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.4 7.4 0 0 0-1.7-1L15 3h-4l-.4 2.9a7.4 7.4 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7.4 7.4 0 0 0 1.7 1L11 21h4l.4-2.9a7.4 7.4 0 0 0 1.7-1l2.5 1 2-3.5zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z" transform="translate(-1 0)"/></svg></button>
        <button class="gico" id="garMute" aria-pressed="false"></button>
        <button class="gico gx" id="garX" aria-label="${esc(T.close)}"><svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M3 3l16 16M19 3L3 19" stroke="currentColor" stroke-width="4" stroke-linecap="round"/></svg></button></header>
      <div class="gctl">${ctlBar(T)}</div>
      <section class="gpanel" id="garPanel" aria-label="${esc(T.garOptions)}" hidden>
        <h2>${esc(T.garOptions)}</h2>
        <div class="gp-row"><span id="garGfxL">${esc(T.garGfx)}</span><div class="gseg" role="radiogroup" aria-labelledby="garGfxL">
          ${['low', 'mid', 'high'].map((q) => `<button role="radio" data-q="${q}">${esc(T['garGfx_' + q])}</button>`).join('')}</div></div>
        <label class="gp-row"><span>${esc(T.garMusic)}</span><input type="range" id="garVolM" min="0" max="100" step="5"><output id="garVolMo"></output></label>
        <label class="gp-row"><span>${esc(T.garSfx)}</span><input type="range" id="garVolS" min="0" max="100" step="5"><output id="garVolSo"></output></label>
        <p class="muted small">${esc(T.garSfxNote)}</p>
        <p class="warn3d small">⚠ ${esc(T.v3dWarn || '')}</p>
      </section>
      <div class="gplate" id="garPlate"></div>
      <div class="gask" id="garAsk" role="alertdialog" aria-modal="true" aria-labelledby="garAskT" hidden>
        <p id="garAskT"></p>
        <div class="gsellbox" id="garAskBox"></div>
        <div><button class="gbtn" id="garAskYes"><b>$</b>${esc(T.garSell)}</button><button class="gbtn" id="garAskNo">${esc(T.cancel || 'Cancelar')}</button></div>
      </div>
      <div class="gswap gsale" id="garSale" role="status" aria-live="polite" hidden><span>${esc(T.garSelling)}</span>
        <svg width="200" height="60" viewBox="0 0 200 60" aria-hidden="true">
          <text class="gsl-dollar" x="52" y="20" font-size="24" font-weight="700" fill="#5BD889" font-family="Chakra Petch, sans-serif">$</text>
          <g class="gsl-car">
            <g class="gsl-wind" stroke="#FFC21A" stroke-width="2.5" stroke-linecap="round"><path d="M4 34h16"/><path d="M0 42h22"/><path d="M6 50h14"/></g>
            <path d="M30 51v-7l9-3 9-8h20l10 8 10 2 2 5v3z" fill="#FFC21A"/><path d="M50 35h7v6h-13zM60 35h7l6 6H60z" fill="#1A1406"/>
            <circle cx="42" cy="52" r="6" fill="#1A1406" stroke="#FFC21A" stroke-width="2"/><circle cx="80" cy="52" r="6" fill="#1A1406" stroke="#FFC21A" stroke-width="2"/>
          </g>
        </svg></div>
      <div class="gswap" id="garSwap" role="status" aria-live="polite" hidden><span>${esc(T.garSwapping)}</span>
        <svg class="gsw-car" width="96" height="44" viewBox="0 0 96 44" aria-hidden="true">
          <g class="gsw-wind" stroke="#FFC21A" stroke-width="2.5" stroke-linecap="round"><path d="M4 14h16"/><path d="M0 22h22"/><path d="M6 30h14"/></g>
          <g class="gsw-body"><path d="M30 31v-7l9-3 9-8h20l10 8 10 2 2 5v3z" fill="#FFC21A"/><path d="M50 15h7v6h-13zM60 15h7l6 6H60z" fill="#1A1406"/>
          <circle class="gsw-w" cx="42" cy="32" r="6" fill="#1A1406" stroke="#FFC21A" stroke-width="2"/><circle class="gsw-w" cx="80" cy="32" r="6" fill="#1A1406" stroke="#FFC21A" stroke-width="2"/></g>
        </svg></div>
      <div class="gload" id="garLoad">${esc(T.garLoading)}</div>
      <div class="gbar" id="garBar">
        <button class="garr" id="garPrev" aria-label="${esc(T.garPrev)}"><svg width="44" height="36" viewBox="0 0 44 36" aria-hidden="true"><path d="M42 2L2 18l40 16-10-16z"/></svg></button>
        <button class="gbtn" id="garDet"><i>↵</i>${esc(T.garDetails)}</button>
        <button class="garr" id="garNext" aria-label="${esc(T.garNext)}"><svg width="44" height="36" viewBox="0 0 44 36" aria-hidden="true"><path d="M2 2l40 16L2 34l10-16z"/></svg></button>
      </div>
      <section class="ginfo" id="garInfo" hidden></section>`;
    document.body.appendChild(el);
    const $ = (s) => el.querySelector(s);
    const canvas = $('#garCv');

    // options (gear button): graphics, music volume, the select sound's volume; remembered with the mute button
    const blobUrl = (b, type) => (b ? URL.createObjectURL(new Blob([b], { type })) : null);
    let muted = false;
    const optsSaved = { gfx: 'mid', music: 60, sfx: 80 };
    try {
      muted = localStorage.getItem('odc_garage_mute') === '1';
      Object.assign(optsSaved, JSON.parse(localStorage.getItem('odc_garage_opts') || '{}'));
    } catch { /* storage off */ }
    const O = optsSaved;
    O.gfx = gfxGet();
    const saveOpts = () => { try { localStorage.setItem('odc_garage_opts', JSON.stringify(O)); } catch { /* off */ } };
    let music = null, click = null, cash = null;
    const muteBtn = $('#garMute');
    const drawMute = () => {
      muteBtn.setAttribute('aria-pressed', muted ? 'true' : 'false');
      muteBtn.setAttribute('aria-label', muted ? T.garUnmute : T.garMute);
      muteBtn.title = muted ? T.garUnmute : T.garMute;
      muteBtn.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/>${muted
        ? '<path d="M16 9l5 6M21 9l-5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
        : '<path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'}</svg>`;
      if (music) { music.muted = muted; music.volume = O.music / 100; if (!muted) music.play().catch(() => {}); }
    };
    drawMute();
    muteBtn.onclick = () => { muted = !muted; try { localStorage.setItem('odc_garage_mute', muted ? '1' : '0'); } catch { /* off */ } drawMute(); };

    const panel = $('#garPanel'), optBtn = $('#garOpt');
    const drawOpts = () => {
      panel.querySelectorAll('.gseg button').forEach((b) => { const on = b.dataset.q === O.gfx; b.classList.toggle('on', on); b.setAttribute('aria-checked', on ? 'true' : 'false'); });
      $('#garVolM').value = O.music; $('#garVolMo').textContent = O.music + '%';
      $('#garVolS').value = O.sfx; $('#garVolSo').textContent = O.sfx + '%';
    };
    const showPanel = (on) => { panel.hidden = !on; optBtn.setAttribute('aria-expanded', on ? 'true' : 'false'); if (on) drawOpts(); };
    optBtn.onclick = () => showPanel(panel.hidden);
    panel.querySelectorAll('.gseg button').forEach((b) => { b.onclick = () => { O.gfx = b.dataset.q; saveOpts(); gfxSet(O.gfx); drawOpts(); if (renderer) { applyGfx(); resize(); } }; });
    $('#garVolM').oninput = (e) => { O.music = +e.target.value; saveOpts(); drawOpts(); if (music) music.volume = O.music / 100; };
    $('#garVolS').oninput = (e) => { O.sfx = +e.target.value; saveOpts(); drawOpts(); };
    $('#garVolS').onchange = () => playSel();
    const playSel = () => { if (click && O.sfx > 0) { click.volume = O.sfx / 100; click.currentTime = 0; click.play().catch(() => {}); } };

    // three.js
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    } catch (e) {
      $('#garLoad').textContent = T.garNoGl;
      $('#garX').onclick = () => close();
      return;
    }
    renderer.outputEncoding = THREE.sRGBEncoding;
    const GFX = { low: 0.6, mid: 1, high: 2 };
    // Low: lower resolution, no car shadows, the fans and light beams stand still; High: up to twice the resolution
    const applyGfx = () => {
      renderer.setPixelRatio(Math.min(GFX[O.gfx] || 1, (window.devicePixelRatio || 1) * (O.gfx === 'high' ? 2 : 1)));
      scene.traverse((o) => { if (o.userData.shadow) o.visible = O.gfx !== 'low'; });
    };
    const scene = new THREE.Scene();
    applyGfx();
    scene.background = new THREE.Color(0x101418);
    const world = new THREE.Group();
    world.rotation.x = -Math.PI / 2;            // the game is Z-up
    scene.add(world);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 200);

    let alive = true, raf = 0;
    const resize = () => {
      const w = el.clientWidth, h = Math.max(1, el.clientHeight - 54);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    window.addEventListener('resize', resize);
    resize();

    // load the files
    let data;
    try {
      const want = [];
      const seen = new Set();
      const byModel = new Map();
      for (const c of cars) if (c.model) { const w = byModel.get(c.model) || { model: c.model, type: c.type, tire: c.tire, parts: [] }; w.parts = [...new Set([...w.parts, ...lookParts(c.model, c.look || [])])]; byModel.set(c.model, w); }
      want.push(...byModel.values()); void seen;
      data = await window.odc.models(want);
    } catch (e) {
      $('#garLoad').textContent = (e && e.message) || String(e);
      $('#garX').onclick = () => close();
      return;
    }
    if (data.palette && Object.keys(data.palette).length) palette = data.palette;
    let ports = [], anim = [];
    const turntable = new THREE.Group();
    world.add(turntable);
    if (data.garage) {
      try {
        const g = buildGarage(data.garage, LOOK);
        world.add(g.root); turntable.add(g.turntable); ports = g.ports; anim = g.anim;
      } catch (e) { console.error('garage', e); }
    }
    if (!ports.length) for (let i = 0; i < PER_FLOOR; i++) { const a = i * Math.PI / 4; ports.push([-6.2 * Math.sin(a), -6.2 * Math.cos(a), 0]); }
    const angleOf = (p) => Math.atan2(p[0], -p[1]);      // 0 = port1, the spot towards the gate (and the camera)

    // cars on the current floor (built when the floor is shown, kept for later)
    const built = new Map();
    const floorGroup = new THREE.Group();
    turntable.add(floorGroup);
    const showFloor = () => {
      floorGroup.clear();
      for (let i = 0; i < PER_FLOOR; i++) {
        const ci = floor * PER_FLOOR + i;
        const c = cars[ci];
        if (!c) continue;
        if (!built.has(ci)) {
          const f = data.cars[c.model];
          let g = null;
          if (f && f.body) { try { g = buildCar(c.model, f, data.textures, Object.assign({}, c, { look: lookBuild(c.model, c.look || [], f) })); } catch (e) { console.error('car', c.model, e); } }
          built.set(ci, g);
        }
        const g = built.get(ci);
        if (!g) continue;
        const p = ports[i];
        const holder = new THREE.Group();
        holder.position.set(p[0], p[1], p[2] + g.userData.lift);
        holder.rotation.z = Math.atan2(-p[0], p[1]);   // the car's nose (+Y) points out from the centre
        holder.add(g);
        floorGroup.add(holder);
      }
      applyGfx();
    };

    // as in the game the camera stays (Camera01 in garage.nif, looking over the turntable from the gate) and the
    // turntable turns the chosen car to the front; Details moves the camera down beside that car
    const CAM = { all: { pos: [0, -18.2, 5.0], at: [0, 6.8, -3.3], fov: 46 }, det: { pos: [4.4, -11.8, 2.9], at: [-0.2, -5.9, -0.35], fov: 40 } };
    let turn = 0, turnGoal = 0;
    const cam = { pos: CAM.all.pos.slice(), at: CAM.all.at.slice(), fov: CAM.all.fov };
    const setGoal = () => {
      const a = -angleOf(ports[sel - floor * PER_FLOOR] || ports[0]);
      let d = a - turnGoal;
      d = ((d + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
      turnGoal += d;
    };
    const camAt = () => {
      // world (Z-up) -> scene (Y-up): (x, y, z) -> (x, z, -y)
      camera.position.set(cam.pos[0], cam.pos[2], -cam.pos[1]);
      camera.lookAt(cam.at[0], cam.at[2], -cam.at[1]);
      if (Math.abs(camera.fov - cam.fov) > 0.01) { camera.fov = cam.fov; camera.updateProjectionMatrix(); }
    };

    // HTML around the scene
    const fmt = (n) => Number(n || 0).toLocaleString();
    const floors = Math.max(1, Math.ceil(cars.length / PER_FLOOR));
    const drawFloors = () => {
      $('.gfl').innerHTML = Array.from({ length: 10 }, (_, i) => `<button class="gf${i === floor ? ' on' : ''}" data-f="${i}" ${i >= floors ? 'disabled' : ''} aria-label="${esc(T.garFloor)} ${i + 1}" aria-pressed="${i === floor}">${i + 1}<small>F</small></button>`).join('');
      el.querySelectorAll('.gf').forEach((b) => { b.onclick = () => { const f = +b.dataset.f; if (f !== floor) { floor = f; sel = floor * PER_FLOOR; details = false; showFloor(); setGoal(); drawUi(); } }; });
    };
    const drawUi = () => {
      const c = cars[sel];
      $('#garPlate').innerHTML = c ? `${c.current ? `<span class="gdrv"><svg width="18" height="12" viewBox="0 0 18 12" aria-hidden="true"><path d="M2 9V6l3-4h8l3 4v3z" fill="currentColor"/></svg>${esc(T.invDriving)}</span>` : ''}<b>${esc(c.name)}</b><em>V${c.grade}</em>` : '';
      $('#garPlate').classList.toggle('det', details);
      $('#garDet').hidden = details;
      const info = $('#garInfo');
      info.hidden = !details;
      if (details && c) {
        const P = c.points || { base: [0, 0, 0, 0], parts: [0, 0, 0, 0] };
        const names = [T.inv_speed, T.inv_accel, T.inv_crash, T.inv_boost];
        const sum = (a) => a.reduce((x, y) => x + y, 0);
        const slots = inv.items.filter((x) => x.car === c.id && x.slot >= 100 && x.slot <= 111);
        const has = (col, line) => slots.some((x) => x.slot === 100 + col * 3 + line);
        info.innerHTML = `
          <div class="gi-h"><h2>${esc(T.garInfo)}</h2><span>${sel + 1}/${cars.length}</span></div>
          <div class="gi-b">
            <table class="gi-t"><thead><tr><th></th><th></th><th></th><th>${esc(T.invCar)}</th><th></th><th>${esc(T.invPartsCol)}</th></tr></thead><tbody>
              ${names.map((n, k) => `<tr><td>${esc(n)}</td><td class="tot">${P.base[k] + P.parts[k]}</td><td class="op">=</td><td>${P.base[k]}</td><td class="op">+</td><td>${P.parts[k]}</td></tr>`).join('')}
              <tr class="sum"><td>${esc(T.garTotal)}</td><td class="tot">${sum(P.base) + sum(P.parts)}</td><td class="op">=</td><td>${sum(P.base)}</td><td class="op">+</td><td>${sum(P.parts)}</td></tr>
            </tbody></table>
            <div class="gi-s"><div class="gi-sh"><span>${esc(T.garSlots)}</span>${['S', 'A', 'D', 'B'].map((x) => `<b>${x}</b>`).join('')}</div>
              ${Array.from({ length: Math.max(1, inv.lines || 2) }, (_, l) => `<div class="gi-sr"><span></span>${[0, 1, 2, 3].map((col) => `<i class="${has(col, l) ? 'on' : ''}"></i>`).join('')}</div>`).join('')}
              <div class="muted small">${esc(T.invTank)} ${fmt(P.tank)}</div></div>
            <div class="gi-a">
              <button class="gbtn" id="garUse" ${c.current || c.auction ? 'disabled' : ''}><i>↵</i>${esc(c.current ? T.invDriving : T.garUse)}</button>
              <button class="gbtn" id="garAll"><i>←</i>${esc(T.garAll)}</button>
              <button class="gsell" id="garSell" ${sellWhy(c) ? `disabled title="${esc(sellWhy(c))}"` : ''}><b>$</b>${esc(T.garSell)}<span>${c.sell != null ? fmt(c.sell) + ' Mito' : ''}</span></button>
            </div>
          </div>`;
        $('#garUse').onclick = use;
        $('#garSell').onclick = askSell;
        $('#garAll').onclick = () => { details = false; setGoal(); drawUi(); };
      }
      drawFloors();
    };
    const move = (d) => {
      const first = floor * PER_FLOOR, n = Math.min(PER_FLOOR, cars.length - first);
      if (n < 2) return;
      sel = first + ((sel - first + d) % n + n) % n;
      playSel();
      setGoal(); drawUi();
    };
    const use = async () => {
      const c = cars[sel];
      if (!c || c.current || c.auction || busy) return;
      // the server takes a moment to switch the car in use: "Changing..." with a car running meanwhile
      busy = true;
      const swap = $('#garSwap');
      swap.hidden = false;
      const t0w = performance.now();
      try {
        await onUse(c);
        await new Promise((r) => setTimeout(r, Math.max(0, 700 - (performance.now() - t0w))));
        cars.forEach((x) => { x.current = x === c; });
        $('#garMsg').textContent = T.invUsed;
        playSel();                                   // the server took the change: the same select sound
      } catch (e) {
        $('#garMsg').textContent = (e && e.message) || String(e);
      }
      swap.hidden = true;
      busy = false;
      drawUi();
    };
    // selling the chosen car (Details): the game's own rules, a question first, then "Selling..." with the car
    // driving away and the Mito sound
    const sellWhy = (c) => (c.current ? T.err.car_current : c.auction ? T.err.car_auction : cars.length < 2 ? T.err.car_last
      : c.sell == null ? T.err.no_sell : '');
    const ask = $('#garAsk');
    let sellMode = null;
    const askSell = () => {
      const c = cars[sel];
      if (!c || sellWhy(c) || busy) return;
      // the price of the car, of the performance parts and the drift shop items on it; with parts on it: sell the car
      // alone (they go to the inventory) or with them (their prices added, they are sold too)
      const lines = c.sale || [];
      const partsSum = lines.reduce((a, l) => a + (l.mito || 0), 0);
      sellMode = lines.length ? (sellMode || 'car') : null;
      const total = () => c.sell + (sellMode === 'parts' ? partsSum : 0);
      $('#garAskT').textContent = T.garSellQ2.replace('{n}', c.name).replace('{v}', 'V' + c.grade);
      const row = (name, p, cls) => `<tr class="${cls || ''}"><td>${esc(name)}</td><td class="n">${fmt(p)} Mito</td></tr>`;
      const draw = () => {
        $('#garAskBox').innerHTML = `<table class="gselltab"><tbody>${row(`${c.name} V${c.grade}`, c.sell, 'car')}
          ${lines.length ? `<tr class="h"><td colspan="2">${esc(T.garSellParts)} (${lines.length})</td></tr>` : ''}</tbody></table>
          ${lines.length ? `<div class="gsellparts" tabindex="0" aria-label="${esc(T.garSellParts)}"><table class="gselltab"><tbody>${lines.map((l) => row(`${l.kind === 'drift' ? '◆ ' : ''}${l.name}`, l.mito, l.kind)).join('')}</tbody></table></div>
          <table class="gselltab"><tbody>${row(T.garSellPartsSum, partsSum, 'sum')}</tbody></table>` : ''}
          ${lines.length ? `<div class="gsellmode" role="radiogroup" aria-label="${esc(T.garSell)}">
            <label><input type="radio" name="gsm" value="car" ${sellMode === 'car' ? 'checked' : ''}><span><b>${esc(T.garSellCar)}</b><small>${esc(T.garSellCarD)}</small></span></label>
            <label><input type="radio" name="gsm" value="parts" ${sellMode === 'parts' ? 'checked' : ''}><span><b>${esc(T.garSellAll)}</b><small>${esc(T.garSellAllD)}</small></span></label></div>` : ''}
          <div class="gselltot">${esc(T.garSellTotal)} <b>${fmt(total())} Mito</b></div>
          <p class="gsellnote">${esc(T.garSellNote)}</p>`;
        ask.querySelectorAll('input[name=gsm]').forEach((r) => r.onchange = () => { sellMode = r.value; draw(); });
      };
      draw();
      ask.hidden = false;
      $('#garAskNo').focus();
    };
    $('#garAskNo').onclick = () => { ask.hidden = true; };
    $('#garAskYes').onclick = async () => {
      ask.hidden = true;
      const c = cars[sel];
      if (!c || busy) return;
      busy = true;
      const sale = $('#garSale');
      const svg = sale.querySelector('svg');
      sale.hidden = false;
      svg.classList.remove('go'); void svg.getBoundingClientRect(); svg.classList.add('go');
      const t0s = performance.now();
      let got = null, err = null;
      try { got = await onSell(c, sellMode); } catch (e) { err = e; }
      await new Promise((r) => setTimeout(r, Math.max(0, 2500 - (performance.now() - t0s))));
      sale.hidden = true;
      busy = false;
      if (err) { $('#garMsg').textContent = (err && err.message) || String(err); drawUi(); return; }
      if (cash && O.sfx > 0) { cash.volume = O.sfx / 100; cash.currentTime = 0; cash.play().catch(() => {}); }
      $('#garMsg').textContent = T.garSold.replace('{p}', fmt((got && got.mito) || c.sell));
      // the car leaves the garage: the cars after it move up one spot
      const ix = cars.indexOf(c);
      cars.splice(ix, 1);
      built.clear();
      sel = Math.min(ix, cars.length - 1);
      floor = Math.floor(sel / PER_FLOOR);
      details = false;
      showFloor(); setGoal(); drawUi();
    };

    $('#garPrev').onclick = () => move(-1);
    $('#garNext').onclick = () => move(1);
    $('#garDet').onclick = () => { details = true; setGoal(); drawUi(); };
    const key = (e) => {
      if (busy && e.key !== 'Escape') { e.preventDefault(); return; }
      if (!ask.hidden) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); ask.hidden = true; } return; }
      if (e.target && e.target.tagName === 'INPUT' && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) return;
      if (e.key === 'ArrowLeft') { e.preventDefault(); move(-1); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); move(1); }
      else if (e.key === 'Enter') { e.preventDefault(); if (!details) { details = true; setGoal(); drawUi(); } else use(); }
      else if (e.key === 'Escape' && !panel.hidden) { e.preventDefault(); e.stopPropagation(); showPanel(false); }
      else if (e.key === 'Escape' || e.key === 'Backspace') { e.preventDefault(); e.stopPropagation(); if (details) { details = false; setGoal(); drawUi(); } else close(); }
    };
    window.addEventListener('keydown', key, true);
    function close() {
      alive = false;
      cancelAnimationFrame(raf);
      window.removeEventListener('keydown', key, true);
      window.removeEventListener('resize', resize);
      if (music) { music.pause(); URL.revokeObjectURL(music.src); }
      try { renderer.dispose(); renderer.forceContextLoss(); } catch { /* gone */ }
      el.remove();
      if (onClose) onClose();
    }
    $('#garX').onclick = close;
    bindCtl(el, ctl);

    music = data.music ? new Audio(blobUrl(data.music, 'audio/mpeg')) : null;
    // the client's effects are IMA ADPCM WAVs, which Chromium does not play: turned into PCM first
    const wav = (b) => { try { return window.ADPCM.toPcmWav(b); } catch { return b; } };
    click = data.select ? new Audio(blobUrl(wav(data.select), 'audio/wav')) : null;
    cash = data.sell ? new Audio(blobUrl(wav(data.sell), 'audio/wav')) : null;
    if (music) { music.loop = true; music.volume = O.music / 100; music.muted = muted; music.play().catch(() => {}); }

    showFloor();
    setGoal();
    turn = turnGoal;
    drawUi();
    $('#garLoad').remove();

    // the name plate sits above the car at the front spot
    const plate = $('#garPlate');
    const v = new THREE.Vector3();
    const t0 = performance.now();
    let last = t0;
    const front = ports[0] || [0, -6.2, 0];
    const loop = (now) => {
      if (!alive) return;
      const dt = Math.min(0.1, (now - last) / 1000); last = now;
      const k = 1 - Math.pow(0.003, dt);
      turn += (turnGoal - turn) * k;
      turntable.rotation.z = turn;
      const g = details ? CAM.det : CAM.all;
      for (let i = 0; i < 3; i++) { cam.pos[i] += (g.pos[i] - cam.pos[i]) * k; cam.at[i] += (g.at[i] - cam.at[i]) * k; }
      cam.fov += (g.fov - cam.fov) * k;
      camAt();
      if (O.gfx !== 'low') animate(anim, (now - t0) / 1000);
      for (const [ci, g] of built) if (g) applyCtl(g, ci === sel ? ctl : {}, (now - t0) / 1000);
      renderer.render(scene, camera);
      if (!details) {
        v.set(front[0], 1.9, -front[1]).project(camera);
        plate.style.left = ((v.x + 1) / 2 * el.clientWidth) + 'px';
        plate.style.top = (54 + (1 - v.y) / 2 * (el.clientHeight - 54)) + 'px';
      } else { plate.style.left = ''; plate.style.top = ''; }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    el.tabIndex = -1;
    el.focus();
  }

  /* ---------------- the 3D quality, one setting for every 3D view of the launcher (garage, drift shop, inventory,
     coupon book, gotcha) and the video settings page ---------------- */
  const GFX_KEY = 'odc_3d_gfx';
  const GFX_PX = { low: 0.6, mid: 1, high: 2 };
  function gfxGet() {
    try { return localStorage.getItem(GFX_KEY) || JSON.parse(localStorage.getItem('odc_garage_opts') || '{}').gfx || 'mid'; } catch { return 'mid'; }
  }
  function gfxSet(q) {
    if (!GFX_PX[q]) return;
    try { localStorage.setItem(GFX_KEY, q); } catch { /* storage off */ }
    window.dispatchEvent(new CustomEvent('odc-gfx', { detail: q }));
  }
  const gfxPx = (q) => Math.min(GFX_PX[q || gfxGet()] || 1, (window.devicePixelRatio || 1) * ((q || gfxGet()) === 'high' ? 2 : 1));

  /* ---------------- the car's controls: wheels (±65°), indicators, brake, head lights ---------------- */
  // ctl = {steer: degrees (+ left), winkL, winkR, hazard, brake, head, rev}; t = seconds (the indicators blink)
  function applyCtl(g, ctl, t) {
    if (!g) return;
    const a = Math.max(-65, Math.min(65, ctl.steer || 0)) * Math.PI / 180;
    for (const h of g.userData.steer || []) h.rotation.z = a;
    const L = g.userData.lights || {};
    const blink = (t * 1.6) % 1 < 0.5;
    const show = (list, on) => { for (const m of list || []) m.visible = !!on; };
    show(L.winkL, (ctl.winkL || ctl.hazard) && blink);
    show(L.winkR, (ctl.winkR || ctl.hazard) && blink);
    show(L.tail, ctl.brake || ctl.head);
    show(L.rev, ctl.rev);
    show(L.head, ctl.head);
  }

  // the control strip for a car (garage and drift shop): steering (±65°), indicators, hazard, brake, head lights
  function ctlBar(T, o) {
    o = o || {};
    const b = (k, icon, label) => `<button class="cbtn" data-ctl="${k}" aria-pressed="false" title="${esc(label)}" aria-label="${esc(label)}">${icon}</button>`;
    return `<div class="carctl${o.hidden ? ' folded' : ''}" role="group" aria-label="${esc(T.ctlTitle || 'Car')}">
      <button class="cbtn cfold" data-fold="1" aria-expanded="${o.hidden ? 'false' : 'true'}" title="${esc(T.ctlFold || 'Show / hide')}" aria-label="${esc(T.ctlFold || 'Show / hide')}">${o.hidden ? '▸' : '▾'}</button>
      ${o.auto ? `<button class="cbtn${o.still ? '' : ' on'}" data-auto="1" aria-pressed="${o.still ? 'false' : 'true'}" title="${esc(T.ctlAuto || 'Turn by itself')}" aria-label="${esc(T.ctlAuto || 'Turn by itself')}">⟳</button>` : ''}
      ${b('winkL', '◀', T.ctlLeft || 'Left')}
      <label class="csteer" title="${esc(T.ctlSteer || 'Steering')}"><span>⟲</span><input type="range" min="-65" max="65" step="1" value="0" data-ctl="steer" aria-label="${esc(T.ctlSteer || 'Steering')}"><output>0°</output></label>
      ${b('winkR', '▶', T.ctlRight || 'Right')}
      ${b('hazard', '⚠', T.ctlHazard || 'Hazard')}${b('brake', '■', T.ctlBrake || 'Brake')}${b('head', '☀', T.ctlHead || 'Head lights')}</div>`;
  }
  function bindCtl(root, ctl, onFold) {
    const bar = root.querySelector('.carctl');
    const fold = root.querySelector('.carctl [data-fold]');
    if (fold) fold.onclick = () => { const f = bar.classList.toggle('folded'); fold.textContent = f ? '▸' : '▾'; fold.setAttribute('aria-expanded', f ? 'false' : 'true'); if (onFold) onFold(f); };
    const auto = root.querySelector('.carctl [data-auto]');
    if (auto) auto.onclick = () => { ctl.still = !ctl.still; auto.classList.toggle('on', !ctl.still); auto.setAttribute('aria-pressed', ctl.still ? 'false' : 'true'); };
    root.querySelectorAll('.carctl button[data-ctl]').forEach((btn) => {
      btn.onclick = () => {
        const k = btn.dataset.ctl;
        ctl[k] = !ctl[k];
        if (k === 'winkL' && ctl.winkL) ctl.winkR = false;
        if (k === 'winkR' && ctl.winkR) ctl.winkL = false;
        root.querySelectorAll('.carctl button[data-ctl]').forEach((x) => { x.setAttribute('aria-pressed', ctl[x.dataset.ctl] ? 'true' : 'false'); x.classList.toggle('on', !!ctl[x.dataset.ctl]); });
      };
    });
    const r = root.querySelector('.carctl input[data-ctl=steer]');
    if (r) {
      r.oninput = () => { ctl.steer = -Number(r.value); r.nextElementSibling.textContent = `${Math.abs(r.value)}° ${r.value < 0 ? '◀' : r.value > 0 ? '▶' : ''}`; };
      r.ondblclick = () => { r.value = 0; r.oninput(); };
    }
  }

  /* ---------------- a stage for one car: dragged round 360°, zoomed, in white or in the garage ---------------- */
  // host: an element; first: {model, tire, tire_scale, tire_width, color, look, parts}; opts: {yaw, auto, bg: 'white' | 'garage',
  // onReady(group)}. -> {set(car), scene(bg), ctl, dispose(), car}
  function studio(host, first, opts) {
    opts = opts || {};
    const canvas = document.createElement('canvas');
    canvas.className = 'pv3d';
    host.appendChild(canvas);
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true }); } catch { canvas.remove(); return { set() {}, scene() {}, dispose() {}, ctl: {} }; }
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.setPixelRatio(gfxPx());
    const onGfx = () => { try { renderer.setPixelRatio(gfxPx()); resizeTo(); } catch { /* gone */ } };
    window.addEventListener('odc-gfx', onGfx);
    const scene = new THREE.Scene();
    const world = new THREE.Group(); world.rotation.x = -Math.PI / 2; scene.add(world);
    const carHolder = new THREE.Group(); world.add(carHolder);
    const backdrop = new THREE.Group(); world.add(backdrop);
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 200);
    const ctl = { steer: 0, winkL: false, winkR: false, hazard: false, brake: false, head: false, rev: false };
    let yaw = opts.yaw == null ? -0.6 : opts.yaw, pitch = 0.16, drag = null, idle = 0, alive = true, raf = 0, dist = 11, token = 0, car = null, anim = [], bg = 'white';
    const resize = () => resizeTo();
    const ro = new ResizeObserver(() => resize());
    canvas.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, y: e.clientY, yaw, pitch }; canvas.setPointerCapture(e.pointerId); canvas.style.cursor = 'grabbing'; });
    canvas.addEventListener('pointermove', (e) => {
      if (!drag) return;
      yaw = drag.yaw - (e.clientX - drag.x) * 0.012;
      pitch = Math.max(-0.05, Math.min(0.9, drag.pitch + (e.clientY - drag.y) * 0.006));
      idle = 0;
    });
    const up = () => { drag = null; canvas.style.cursor = 'grab'; };
    canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
    canvas.addEventListener('wheel', (e) => { e.preventDefault(); dist = Math.max(4, Math.min(24, dist * (e.deltaY > 0 ? 1.08 : 0.93))); }, { passive: false });
    canvas.style.cursor = 'grab';
    let last = performance.now();
    const born = last;
    const loop = (now) => {
      if (!alive) return;
      if (!canvas.isConnected && now - born > 1000) { dispose(); return; }   // the window around it went away
      const dt = Math.min(0.1, (now - last) / 1000); last = now;
      idle += dt;
      if (!drag && idle > 2 && opts.auto !== false && !ctl.still) yaw += dt * 0.3;
      // the camera goes round the car (Y up in the scene: the game's Z)
      const r = dist, cy = 0.55;
      camera.position.set(Math.sin(yaw) * Math.cos(pitch) * r, cy + Math.sin(pitch) * r, Math.cos(yaw) * Math.cos(pitch) * r);
      camera.lookAt(0, cy, 0);
      const t = (now - born) / 1000;
      applyCtl(car, ctl, t);
      if (bg === 'garage' && anim.length) animate(anim, t);
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    const spin = document.createElement('span'); spin.className = 'pvload';
    const set = async (c) => {
      const my = ++token;
      if (!c || !c.model) { carHolder.clear(); car = null; return; }
      let data;
      if (!car) hostNow.appendChild(spin);
      try { data = await window.odc.models([{ model: c.model, type: c.type, tire: c.tire, parts: c.parts || [] }], false); } catch (e) { console.error(e); spin.remove(); return; } finally { if (my === token) spin.remove(); }
      if (my !== token || !alive) return;
      if (data.palette && Object.keys(data.palette).length) palette = data.palette;
      const f = data.cars[c.model];
      if (!f || !f.body) { carHolder.clear(); car = null; return; }
      const look = typeof c.look === 'function' ? c.look(f) : c.look;
      let g;
      try { g = buildCar(c.model, f, data.textures, Object.assign({ tire_scale: [660, 660], tire_width: [1, 1], color: 0x08000002 }, c, { look })); } catch (e) { console.error('car', e); return; }
      g.updateMatrixWorld(true);
      const box = new THREE.Box3();
      g.traverse((o) => { if (o.isMesh && o.visible && !o.userData.shadow) box.expandByObject(o); });
      const size = box.getSize(new THREE.Vector3());
      g.position.set(-(box.min.x + box.max.x) / 2, -(box.min.y + box.max.y) / 2, g.userData.lift || 0);
      // framed as the car's normal size, so a MINI or an ST looks smaller and a BT bigger
      if (!c.keepView) dist = Math.max(5, Math.max(size.x, size.y) / (g.userData.size || 1) * (opts.fit || 1.45)) * Math.max(1, 1.6 / (camera.aspect || 1.6));
      carHolder.clear(); carHolder.add(g); car = g;
      if (bg === 'garage') for (const o of g.children) if (o.userData.shadow) o.visible = true;
      if (opts.onReady) opts.onReady(g);
    };
    // the backdrop: 'white' (the drift shop's bright room: just the colour behind) or the garage, its first spot at the centre
    const sceneBg = async (which) => {
      bg = which;
      backdrop.clear(); anim = [];
      if (which !== 'garage') { scene.background = null; return; }
      scene.background = new THREE.Color(0x101418);
      let data;
      try { data = await window.odc.models([], true); } catch (e) { console.error(e); return; }
      if (!alive || bg !== 'garage' || !data.garage) return;
      try {
        const gg = buildGarage(data.garage, LOOK);
        const P = gg.ports[0] || [0, -6.2, 0];
        const th = Math.atan2(-P[0], P[1]);
        const holder = new THREE.Group();
        holder.add(gg.root); holder.add(gg.turntable);
        holder.rotation.z = -th;
        const v = new THREE.Vector3(-P[0], -P[1], -P[2]).applyAxisAngle(new THREE.Vector3(0, 0, 1), -th);
        holder.position.copy(v);
        backdrop.add(holder); anim = gg.anim;
      } catch (e) { console.error('garage', e); }
    };
    const dispose = () => {
      alive = false; cancelAnimationFrame(raf); ro.disconnect(); token++;
      window.removeEventListener('odc-gfx', onGfx);
      try { renderer.dispose(); renderer.forceContextLoss(); } catch { /* gone */ }
      canvas.remove();
    };
    let hostNow = host;
    ro.observe(host); setTimeout(() => resizeTo(), 0);
    if (opts.bg) sceneBg(opts.bg);
    if (first) set(first);
    const mount = (h) => { if (!h || h === hostNow) return; ro.unobserve(hostNow); hostNow = h; h.prepend(canvas); ro.observe(h); resizeTo(); };
    const resizeTo = () => { const w = Math.max(1, hostNow.clientWidth), hh = Math.max(1, hostNow.clientHeight); renderer.setSize(w, hh, false); camera.aspect = w / hh; camera.updateProjectionMatrix(); };
    return { set, scene: sceneBg, dispose, ctl, mount, canvas, get alive() { return alive; }, get car() { return car; }, get bg() { return bg; },
      setQuality(px) { renderer.setPixelRatio(Math.min(px, (window.devicePixelRatio || 1) * 2)); resizeTo(); } };
  }
  const preview = (host, first, opts) => studio(host, first, opts);

  window.Garage = { open, preview, studio, buildCar, applyCtl, ctlBar, bindCtl, lookParts, lookBuild, setPalette(p) { if (p && Object.keys(p).length) palette = p; }, gfxGet, gfxSet };
})();
