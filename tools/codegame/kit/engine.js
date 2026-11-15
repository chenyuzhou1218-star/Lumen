/* CodeGame's engine: a small 3D game engine with no libraries, written straight on WebGL 2.
   It draws lit, shadowed things with fog and a sky, reads GLB models (from Code3D), plays sounds (from CodeSound), walks a character over
   ground and into walls, and reports what happens to a machine player. A game is one file that talks to the global G. Written for weak
   graphics chips: one light, one shadow map, simple materials. */
'use strict';

(function () {
  /* --- small maths --------------------------------------------------------------------------------------------------- */
  const V = {
    add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    len: (a) => Math.hypot(a[0], a[1], a[2]),
    norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
    dist: (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]),
    lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
  };
  const M = {
    identity: () => new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
    mul(a, b) {
      const o = new Float32Array(16);
      for (let c = 0; c < 4; c++) {
        for (let r = 0; r < 4; r++) {
          o[c * 4 + r] = a[r] * b[c * 4] + a[r + 4] * b[c * 4 + 1] + a[r + 8] * b[c * 4 + 2] + a[r + 12] * b[c * 4 + 3];
        }
      }
      return o;
    },
    perspective(fovy, aspect, near, far) {
      const f = 1 / Math.tan(fovy / 2);
      const o = new Float32Array(16);
      o[0] = f / aspect; o[5] = f; o[10] = (far + near) / (near - far); o[11] = -1; o[14] = 2 * far * near / (near - far);
      return o;
    },
    ortho(l, r, b, t, n, f) {
      const o = new Float32Array(16);
      o[0] = 2 / (r - l); o[5] = 2 / (t - b); o[10] = -2 / (f - n);
      o[12] = -(r + l) / (r - l); o[13] = -(t + b) / (t - b); o[14] = -(f + n) / (f - n); o[15] = 1;
      return o;
    },
    lookAt(eye, at, up) {
      const z = V.norm(V.sub(eye, at));
      const x = V.norm(V.cross(up, z));
      const y = V.cross(z, x);
      return new Float32Array([x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -V.dot(x, eye), -V.dot(y, eye), -V.dot(z, eye), 1]);
    },
    trs(p, r, s) {
      /* yaw (around Y), then pitch (X), then roll (Z), all in degrees */
      const a = r[1] * Math.PI / 180, b = r[0] * Math.PI / 180, c = r[2] * Math.PI / 180;
      const ca = Math.cos(a), sa = Math.sin(a), cb = Math.cos(b), sb = Math.sin(b), cc = Math.cos(c), sc = Math.sin(c);
      const m00 = ca * cc + sa * sb * sc, m01 = -ca * sc + sa * sb * cc, m02 = sa * cb;
      const m10 = cb * sc, m11 = cb * cc, m12 = -sb;
      const m20 = -sa * cc + ca * sb * sc, m21 = sa * sc + ca * sb * cc, m22 = ca * cb;
      return new Float32Array([m00 * s[0], m10 * s[0], m20 * s[0], 0, m01 * s[1], m11 * s[1], m21 * s[1], 0, m02 * s[2], m12 * s[2], m22 * s[2], 0, p[0], p[1], p[2], 1]);
    },
  };

  function colour(c) {
    if (Array.isArray(c)) return c;
    const m = /^#?([0-9a-f]{6})$/i.exec(String(c || '#ffffff'));
    if (!m) throw new Error(`颜色要写成 #rrggbb：${c}`);
    const n = parseInt(m[1], 16);
    const lin = (v) => Math.pow(v / 255, 2.2);
    return [lin((n >> 16) & 255), lin((n >> 8) & 255), lin(n & 255)];
  }

  /* --- WebGL ------------------------------------------------------------------------------------------------------------ */
  const canvas = document.createElement('canvas');
  canvas.id = 'game';
  document.body.append(canvas);
  const gl = canvas.getContext('webgl2', { antialias: true, powerPreference: 'low-power' });
  if (!gl) {
    document.body.textContent = '这台电脑的浏览器不支持 WebGL 2。';
    throw new Error('no WebGL 2');
  }

  function program(vs, fs) {
    const make = (kind, text) => {
      const s = gl.createShader(kind);
      gl.shaderSource(s, text);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    const p = gl.createProgram();
    gl.attachShader(p, make(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, make(gl.FRAGMENT_SHADER, fs));
    gl.bindAttribLocation(p, 0, 'aPos');
    gl.bindAttribLocation(p, 1, 'aNormal');
    gl.bindAttribLocation(p, 2, 'aUv');
    gl.bindAttribLocation(p, 3, 'aColor');
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    const u = {};
    const count = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < count; i++) {
      const name = gl.getActiveUniform(p, i).name;
      u[name] = gl.getUniformLocation(p, name);
    }
    return { p, u };
  }

  const LIT = program(`#version 300 es
  layout(location=0) in vec3 aPos; layout(location=1) in vec3 aNormal; layout(location=2) in vec2 aUv; layout(location=3) in vec3 aColor;
  uniform mat4 uModel, uViewProj, uLight;
  out vec3 vPos, vNormal, vColor; out vec2 vUv; out vec4 vLight;
  void main(){ vec4 w=uModel*vec4(aPos,1.); vPos=w.xyz; vNormal=mat3(uModel)*aNormal; vColor=aColor; vUv=aUv; vLight=uLight*w; gl_Position=uViewProj*w; }`,
  `#version 300 es
  precision highp float;
  in vec3 vPos, vNormal, vColor; in vec2 vUv; in vec4 vLight;
  uniform vec3 uBase, uEmit, uEye, uSunDir, uSunColor, uSkyColor, uGroundColor, uFogColor;
  uniform float uRough, uMetal, uFog, uOpacity, uUnlit, uHasMap, uTile;
  uniform sampler2D uMap; uniform highp sampler2D uShadow;
  out vec4 frag;
  float shadowAt(vec3 n){
    vec3 p=vLight.xyz/vLight.w*.5+.5;
    if(p.x<0.||p.x>1.||p.y<0.||p.y>1.||p.z>1.) return 1.;
    float bias=.0015+.004*(1.-max(dot(n,uSunDir),0.)); float s=0.; float t=1./1024.;
    for(int x=-1;x<=1;x+=2) for(int y=-1;y<=1;y+=2){ s+= p.z-bias>texture(uShadow,p.xy+vec2(x,y)*t*.75).r?0.:1.; }
    return s*.25;
  }
  vec3 aces(vec3 x){ return clamp(x*(2.51*x+.03)/(x*(2.43*x+.59)+.14),0.,1.); }
  void main(){
    vec3 albedo=uBase*vColor; float alpha=uOpacity;
    if(uHasMap>.5){ vec4 t=texture(uMap,vUv*uTile); albedo*=pow(t.rgb,vec3(2.2)); alpha*=t.a; if(alpha<.04) discard; }
    vec3 color;
    if(uUnlit>.5){ color=albedo; }
    else{
      vec3 n=normalize(vNormal); vec3 v=normalize(uEye-vPos); if(dot(n,v)<0.) n=-n;
      float nl=max(dot(n,uSunDir),0.); float s=nl>0.?shadowAt(n):0.;
      vec3 amb=mix(uGroundColor,uSkyColor,n.y*.5+.5);
      vec3 h=normalize(uSunDir+v); float shin=2./max(uRough*uRough*uRough*uRough,.002);
      float spec=pow(max(dot(n,h),0.),shin)*(shin+8.)/25.;
      vec3 f0=mix(vec3(.04),albedo,uMetal);
      float fres=pow(1.-max(dot(n,v),0.),5.);
      color=albedo*(1.-uMetal)*(amb+uSunColor*nl*s)+f0*spec*nl*s*uSunColor+amb*mix(f0,vec3(1.),fres)*(1.-uRough)*.5;
    }
    color+=uEmit;
    float d=length(uEye-vPos); float fog=1.-exp(-d*d*uFog*uFog); color=mix(color,uFogColor,fog);
    frag=vec4(pow(aces(color*.62),vec3(1./2.2)),alpha);
  }`);

  const DEPTH = program(`#version 300 es
  layout(location=0) in vec3 aPos; uniform mat4 uModel, uLight; void main(){ gl_Position=uLight*uModel*vec4(aPos,1.); }`,
  `#version 300 es
  precision mediump float; void main(){}`);

  const SKY = program(`#version 300 es
  out vec2 vP; void main(){ vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2); vP=p*2.-1.; gl_Position=vec4(vP,1.,1.); }`,
  `#version 300 es
  precision highp float; in vec2 vP; uniform mat4 uInvView; uniform vec3 uTop,uHorizon,uGround,uSunDir,uSunTint; out vec4 frag;
  void main(){
    vec4 w=uInvView*vec4(vP,1.,1.); vec3 d=normalize(w.xyz/w.w);
    float t=clamp(d.y,0.,1.); vec3 c=d.y>0.?mix(uHorizon,uTop,pow(t,.55)):mix(uHorizon,uGround,clamp(-d.y*5.,0.,1.));
    float s=max(dot(d,uSunDir),0.); c+=uSunTint*(pow(s,700.)*3.+pow(s,14.)*.22);
    frag=vec4(pow(clamp(c,0.,1.),vec3(1./2.2)),1.);
  }`);

  const SHADOW_SIZE = 1024;
  const shadowTex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, shadowTex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.DEPTH_COMPONENT24, SHADOW_SIZE, SHADOW_SIZE, 0, gl.DEPTH_COMPONENT, gl.UNSIGNED_INT, null);
  for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.NEAREST], [gl.TEXTURE_MAG_FILTER, gl.NEAREST], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
  const shadowFbo = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, shadowFbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.TEXTURE_2D, shadowTex, 0);
  gl.drawBuffers([gl.NONE]);
  gl.readBuffer(gl.NONE);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  const skyVao = gl.createVertexArray();
  const whiteTex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, whiteTex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([255, 255, 255, 255]));

  /* --- geometry --------------------------------------------------------------------------------------------------------- */
  function mesh(data, indices) {
    /* data: interleaved x y z, nx ny nz, u v, r g b */
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const vbo = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
    gl.bufferData(gl.ARRAY_BUFFER, data instanceof Float32Array ? data : new Float32Array(data), gl.STATIC_DRAW);
    const stride = 11 * 4;
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, stride, 0);
    gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, stride, 12);
    gl.enableVertexAttribArray(2); gl.vertexAttribPointer(2, 2, gl.FLOAT, false, stride, 24);
    gl.enableVertexAttribArray(3); gl.vertexAttribPointer(3, 3, gl.FLOAT, false, stride, 32);
    const ibo = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo);
    const big = data.length / 11 > 65535;
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, big ? new Uint32Array(indices) : new Uint16Array(indices), gl.STATIC_DRAW);
    gl.bindVertexArray(null);
    let lo = [Infinity, Infinity, Infinity];
    let hi = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < data.length; i += 11) {
      for (let k = 0; k < 3; k++) {
        lo[k] = Math.min(lo[k], data[i + k]);
        hi[k] = Math.max(hi[k], data[i + k]);
      }
    }
    return { vao, count: indices.length, type: big ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT, lo, hi };
  }

  const geo = {};

  function boxMesh() {
    if (geo.box) return geo.box;
    const d = [];
    const idx = [];
    const face = (n, u, v) => {
      const base = d.length / 11;
      for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
        const p = [0, 1, 2].map((k) => (n[k] + a * u[k] + b * v[k]) * .5);
        d.push(...p, ...n, (a + 1) / 2, (b + 1) / 2, 1, 1, 1);
      }
      idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    };
    face([0, 0, 1], [1, 0, 0], [0, 1, 0]); face([0, 0, -1], [-1, 0, 0], [0, 1, 0]);
    face([1, 0, 0], [0, 0, -1], [0, 1, 0]); face([-1, 0, 0], [0, 0, 1], [0, 1, 0]);
    face([0, 1, 0], [1, 0, 0], [0, 0, -1]); face([0, -1, 0], [1, 0, 0], [0, 0, 1]);
    geo.box = mesh(d, idx);
    return geo.box;
  }

  function sphereMesh(rows = 16, cols = 24) {
    const key = `sphere${rows}x${cols}`;
    if (geo[key]) return geo[key];
    const d = [];
    const idx = [];
    for (let r = 0; r <= rows; r++) {
      const a = r / rows * Math.PI;
      for (let c = 0; c <= cols; c++) {
        const b = c / cols * Math.PI * 2;
        const n = [Math.sin(a) * Math.cos(b), Math.cos(a), Math.sin(a) * Math.sin(b)];
        d.push(n[0] * .5, n[1] * .5, n[2] * .5, ...n, c / cols, r / rows, 1, 1, 1);
      }
    }
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const a = r * (cols + 1) + c;
        const b = a + cols + 1;
        idx.push(a, a + 1, b, b, a + 1, b + 1);
      }
    }
    geo[key] = mesh(d, idx);
    return geo[key];
  }

  function cylinderMesh(top = .5, sides = 20) {
    const key = `cyl${top}x${sides}`;
    if (geo[key]) return geo[key];
    const d = [];
    const idx = [];
    const slope = (.5 - top);
    for (let c = 0; c <= sides; c++) {
      const b = c / sides * Math.PI * 2;
      const x = Math.cos(b);
      const z = Math.sin(b);
      const n = V.norm([x, slope, z]);
      d.push(x * .5, -.5, z * .5, ...n, c / sides, 0, 1, 1, 1);
      d.push(x * top, .5, z * top, ...n, c / sides, 1, 1, 1, 1);
    }
    for (let c = 0; c < sides; c++) {
      const a = c * 2;
      idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3);
    }
    for (const [y, r, ny] of [[.5, top, 1], [-.5, .5, -1]]) {
      if (r <= 0) continue;
      const center = d.length / 11;
      d.push(0, y, 0, 0, ny, 0, .5, .5, 1, 1, 1);
      const start = d.length / 11;
      for (let c = 0; c <= sides; c++) {
        const b = c / sides * Math.PI * 2;
        d.push(Math.cos(b) * r, y, Math.sin(b) * r, 0, ny, 0, .5 + Math.cos(b) * .5, .5 + Math.sin(b) * .5, 1, 1, 1);
      }
      for (let c = 0; c < sides; c++) idx.push(center, start + c, start + c + 1);
    }
    geo[key] = mesh(d, idx);
    return geo[key];
  }

  function gridMesh(size, cells, height, tint) {
    /* A square of ground, y from height(x, z). tint(x, z, y, slope) gives a colour per point. */
    const n = cells + 1;
    const d = new Float32Array(n * n * 11);
    const step = size / cells;
    const hs = new Float32Array(n * n);
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) hs[j * n + i] = height(-size / 2 + i * step, -size / 2 + j * step);
    const at = (i, j) => hs[Math.max(0, Math.min(n - 1, j)) * n + Math.max(0, Math.min(n - 1, i))];
    let o = 0;
    for (let j = 0; j < n; j++) {
      for (let i = 0; i < n; i++) {
        const x = -size / 2 + i * step;
        const z = -size / 2 + j * step;
        const nm = V.norm([at(i - 1, j) - at(i + 1, j), 2 * step, at(i, j - 1) - at(i, j + 1)]);
        const c = tint ? colour(tint(x, z, at(i, j), 1 - nm[1])) : [1, 1, 1];
        d.set([x, at(i, j), z, nm[0], nm[1], nm[2], i / cells, j / cells, c[0], c[1], c[2]], o);
        o += 11;
      }
    }
    const idx = [];
    for (let j = 0; j < cells; j++) {
      for (let i = 0; i < cells; i++) {
        const a = j * n + i;
        idx.push(a, a + n, a + 1, a + 1, a + n, a + n + 1);
      }
    }
    return mesh(d, idx);
  }

  /* --- the scene --------------------------------------------------------------------------------------------------------- */
  const nodes = new Set();
  const colliders = [];
  const updates = [];
  let camEye = [0, 6, 12];
  let camAt = [0, 1, 0];
  const world = {
    sunDir: V.norm([.5, .8, .3]), sunColor: [3, 2.8, 2.5], skyColor: [.5, .6, .8], groundColor: [.22, .2, .16],
    top: colour('#3f77c4'), horizon: colour('#c9dcef'), below: colour('#8d8a80'), fog: colour('#c9dcef'), fogAmount: .007,
  };

  class Node {
    constructor(geometry, mat) {
      this.geometry = geometry;
      this.mat = { color: [1, 1, 1], emit: [0, 0, 0], rough: .7, metal: 0, opacity: 1, unlit: false, map: null, tile: 1, ...mat };
      this.pos = [0, 0, 0];
      this.rot = [0, 0, 0];
      this.size = [1, 1, 1];
      this.visible = true;
      this.parts = null;
      this.tags = new Set();
      nodes.add(this);
    }

    at(x, y, z) { this.pos = [x, y, z]; return this; }

    remove() { nodes.delete(this); return this; }

    tag(...names) { names.forEach((n) => this.tags.add(n)); return this; }

    /* A wall others walk into. Its box follows the node's position and size; it does not turn. */
    solid() {
      colliders.push(this);
      return this;
    }
  }

  function options(n, o) {
    if (o.at) n.pos = o.at.slice();
    if (o.turn !== undefined) n.rot = [0, o.turn, 0];
    if (o.rot) n.rot = o.rot.slice();
    if (o.size !== undefined) n.size = Array.isArray(o.size) ? o.size.slice() : [o.size, o.size, o.size];
    if (o.solid) n.solid();
    if (o.tag) n.tag(o.tag);
    return n;
  }

  function matOf(o) {
    const m = {};
    if (o.color !== undefined) m.color = colour(o.color);
    if (o.emit !== undefined) m.emit = colour(o.emit).map((v) => v * (o.glow === undefined ? 1 : o.glow));
    for (const k of ['rough', 'metal', 'opacity', 'unlit', 'tile']) if (o[k] !== undefined) m[k] = o[k];
    return m;
  }

  /* --- textures, GLB ------------------------------------------------------------------------------------------------------ */
  function textureFrom(image) {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    return t;
  }

  function assetUrl(name) {
    const url = (window.__ASSETS || {})[name];
    if (!url) throw new Error(`没有这个素材：${name}（放进项目的 assets 文件夹）`);
    return url;
  }

  async function bytesOf(name) {
    return (await fetch(assetUrl(name))).arrayBuffer();
  }

  async function loadGlb(name) {
    const buf = await bytesOf(name);
    const head = new DataView(buf);
    if (head.getUint32(0, true) !== 0x46546c67) throw new Error(`${name} 不是 GLB 文件`);
    let at = 12;
    let json = null;
    let bin = null;
    while (at < buf.byteLength) {
      const size = head.getUint32(at, true);
      const type = head.getUint32(at + 4, true);
      if (type === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, at + 8, size)));
      else if (type === 0x004e4942) bin = buf.slice(at + 8, at + 8 + size);
      at += 8 + size;
    }
    const COUNT = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
    const KIND = { 5121: Uint8Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
    const accessor = (i) => {
      const a = json.accessors[i];
      const view = json.bufferViews[a.bufferView];
      const K = KIND[a.componentType];
      const n = COUNT[a.type];
      const offset = (view.byteOffset || 0) + (a.byteOffset || 0);
      const stride = view.byteStride || 0;
      if (stride && stride !== n * K.BYTES_PER_ELEMENT) {
        const out = new K(a.count * n);
        const dv = new DataView(bin);
        for (let e = 0; e < a.count; e++) {
          for (let c = 0; c < n; c++) {
            const p = offset + e * stride + c * K.BYTES_PER_ELEMENT;
            out[e * n + c] = K === Float32Array ? dv.getFloat32(p, true) : K === Uint16Array ? dv.getUint16(p, true) : K === Uint32Array ? dv.getUint32(p, true) : dv.getUint8(p);
          }
        }
        return out;
      }
      return new K(bin.slice(offset, offset + a.count * n * K.BYTES_PER_ELEMENT));
    };
    const images = await Promise.all((json.images || []).map(async (im) => {
      const view = json.bufferViews[im.bufferView];
      const blob = new Blob([bin.slice(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength)], { type: im.mimeType });
      return createImageBitmap(blob);
    }));
    const tex = (json.textures || []).map((t) => textureFrom(images[t.source]));
    const parts = [];
    const visit = (id, parent) => {
      const node = json.nodes[id];
      let local = M.identity();
      if (node.matrix) local = new Float32Array(node.matrix);
      else {
        const t = node.translation || [0, 0, 0];
        const q = node.rotation || [0, 0, 0, 1];
        const s = node.scale || [1, 1, 1];
        const [x, y, z, w] = q;
        local = new Float32Array([
          (1 - 2 * (y * y + z * z)) * s[0], 2 * (x * y + z * w) * s[0], 2 * (x * z - y * w) * s[0], 0,
          2 * (x * y - z * w) * s[1], (1 - 2 * (x * x + z * z)) * s[1], 2 * (y * z + x * w) * s[1], 0,
          2 * (x * z + y * w) * s[2], 2 * (y * z - x * w) * s[2], (1 - 2 * (x * x + y * y)) * s[2], 0,
          t[0], t[1], t[2], 1]);
      }
      const whole = M.mul(parent, local);
      if (node.mesh !== undefined) {
        for (const prim of json.meshes[node.mesh].primitives) {
          const pos = accessor(prim.attributes.POSITION);
          const nor = prim.attributes.NORMAL !== undefined ? accessor(prim.attributes.NORMAL) : null;
          const uv = prim.attributes.TEXCOORD_0 !== undefined ? accessor(prim.attributes.TEXCOORD_0) : null;
          const count = pos.length / 3;
          const d = new Float32Array(count * 11);
          for (let i = 0; i < count; i++) {
            const o = i * 11;
            d[o] = pos[i * 3]; d[o + 1] = pos[i * 3 + 1]; d[o + 2] = pos[i * 3 + 2];
            if (nor) { d[o + 3] = nor[i * 3]; d[o + 4] = nor[i * 3 + 1]; d[o + 5] = nor[i * 3 + 2]; } else d[o + 4] = 1;
            if (uv) { d[o + 6] = uv[i * 2]; d[o + 7] = uv[i * 2 + 1]; }
            d[o + 8] = 1; d[o + 9] = 1; d[o + 10] = 1;
          }
          const index = prim.indices !== undefined ? accessor(prim.indices) : Array.from({ length: count }, (_, i) => i);
          const mat = (json.materials || [])[prim.material] || {};
          const pbr = mat.pbrMetallicRoughness || {};
          const f = pbr.baseColorFactor || [1, 1, 1, 1];
          const e = mat.emissiveFactor || [0, 0, 0];
          parts.push({ geometry: mesh(d, Array.from(index)), local: whole, mat: { color: [f[0], f[1], f[2]], opacity: f[3], rough: pbr.roughnessFactor === undefined ? .8 : pbr.roughnessFactor, metal: pbr.metallicFactor === undefined ? 0 : pbr.metallicFactor, emit: e, map: pbr.baseColorTexture ? tex[pbr.baseColorTexture.index] : null } });
        }
      }
      (node.children || []).forEach((c) => visit(c, whole));
    };
    for (const root of (json.scenes[json.scene || 0].nodes || [])) visit(root, M.identity());
    return parts;
  }

  /* --- drawing ------------------------------------------------------------------------------------------------------------ */
  function drawNode(n, prog, model, lit) {
    const items = n.parts || [{ geometry: n.geometry, local: null, mat: n.mat }];
    for (const it of items) {
      const m = it.local ? M.mul(model, it.local) : model;
      gl.uniformMatrix4fv(prog.u.uModel, false, m);
      if (lit) {
        const mat = it.mat === n.mat ? n.mat : { rough: .8, metal: 0, opacity: 1, emit: [0, 0, 0], unlit: false, map: null, tile: 1, ...it.mat };
        gl.uniform3fv(prog.u.uBase, mat.color);
        gl.uniform3fv(prog.u.uEmit, mat.emit);
        gl.uniform1f(prog.u.uRough, mat.rough);
        gl.uniform1f(prog.u.uMetal, mat.metal);
        gl.uniform1f(prog.u.uOpacity, mat.opacity);
        gl.uniform1f(prog.u.uUnlit, mat.unlit ? 1 : 0);
        gl.uniform1f(prog.u.uTile, mat.tile);
        gl.uniform1f(prog.u.uHasMap, mat.map ? 1 : 0);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, mat.map || whiteTex);
      }
      gl.bindVertexArray(it.geometry.vao);
      gl.drawElements(gl.TRIANGLES, it.geometry.count, it.geometry.type, 0);
    }
  }

  function render() {
    const w = canvas.clientWidth * Math.min(window.devicePixelRatio, G.quality);
    const h = canvas.clientHeight * Math.min(window.devicePixelRatio, G.quality);
    if (canvas.width !== Math.floor(w) || canvas.height !== Math.floor(h)) {
      canvas.width = Math.floor(w);
      canvas.height = Math.floor(h);
    }
    const shown = [...nodes].filter((n) => n.visible);
    const models = new Map();
    for (const n of shown) models.set(n, M.trs(n.pos, n.rot, n.size));
    const reach = G.shadowReach;
    const centre = camAt;
    const lightEye = V.add(centre, V.mul(world.sunDir, 120));
    const lightVP = M.mul(M.ortho(-reach, reach, -reach, reach, 1, 260), M.lookAt(lightEye, centre, Math.abs(world.sunDir[1]) > .98 ? [0, 0, 1] : [0, 1, 0]));

    gl.bindFramebuffer(gl.FRAMEBUFFER, shadowFbo);
    gl.viewport(0, 0, SHADOW_SIZE, SHADOW_SIZE);
    gl.clear(gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.BLEND);
    gl.useProgram(DEPTH.p);
    gl.uniformMatrix4fv(DEPTH.u.uLight, false, lightVP);
    for (const n of shown) if (!n.mat.unlit && n.mat.opacity > .5 && !n.noShadow) drawNode(n, DEPTH, models.get(n), false);

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const view = M.lookAt(camEye, camAt, [0, 1, 0]);
    const proj = M.perspective(G.camera.fov * Math.PI / 180, canvas.width / Math.max(1, canvas.height), .1, 900);
    const vp = M.mul(proj, view);

    gl.useProgram(SKY.p);
    gl.depthMask(false);
    gl.disable(gl.DEPTH_TEST);
    const rotOnly = new Float32Array(view);
    rotOnly[12] = rotOnly[13] = rotOnly[14] = 0;
    gl.uniformMatrix4fv(SKY.u.uInvView, false, invert(M.mul(proj, rotOnly)));
    gl.uniform3fv(SKY.u.uTop, world.top);
    gl.uniform3fv(SKY.u.uHorizon, world.horizon);
    gl.uniform3fv(SKY.u.uGround, world.below);
    gl.uniform3fv(SKY.u.uSunDir, world.sunDir);
    gl.uniform3fv(SKY.u.uSunTint, world.sunColor.map((v) => v * .33));
    gl.bindVertexArray(skyVao);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.depthMask(true);
    gl.enable(gl.DEPTH_TEST);

    gl.useProgram(LIT.p);
    gl.uniformMatrix4fv(LIT.u.uViewProj, false, vp);
    gl.uniformMatrix4fv(LIT.u.uLight, false, lightVP);
    gl.uniform3fv(LIT.u.uEye, camEye);
    gl.uniform3fv(LIT.u.uSunDir, world.sunDir);
    gl.uniform3fv(LIT.u.uSunColor, world.sunColor);
    gl.uniform3fv(LIT.u.uSkyColor, world.skyColor);
    gl.uniform3fv(LIT.u.uGroundColor, world.groundColor);
    gl.uniform3fv(LIT.u.uFogColor, world.fog);
    gl.uniform1f(LIT.u.uFog, world.fogAmount);
    gl.uniform1i(LIT.u.uMap, 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, shadowTex);
    gl.uniform1i(LIT.u.uShadow, 1);
    const solidOnes = shown.filter((n) => n.mat.opacity >= 1);
    for (const n of solidOnes) drawNode(n, LIT, models.get(n), true);
    const clear = shown.filter((n) => n.mat.opacity < 1).sort((a, b) => V.dist(b.pos, camEye) - V.dist(a.pos, camEye));
    if (clear.length) {
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.depthMask(false);
      for (const n of clear) drawNode(n, LIT, models.get(n), true);
      gl.depthMask(true);
      gl.disable(gl.BLEND);
    }
    gl.bindVertexArray(null);
    G.stats.drawn = shown.length;
  }

  function invert(m) {
    const o = new Float32Array(16);
    const a = m;
    const b00 = a[0] * a[5] - a[1] * a[4], b01 = a[0] * a[6] - a[2] * a[4], b02 = a[0] * a[7] - a[3] * a[4], b03 = a[1] * a[6] - a[2] * a[5];
    const b04 = a[1] * a[7] - a[3] * a[5], b05 = a[2] * a[7] - a[3] * a[6], b06 = a[8] * a[13] - a[9] * a[12], b07 = a[8] * a[14] - a[10] * a[12];
    const b08 = a[8] * a[15] - a[11] * a[12], b09 = a[9] * a[14] - a[10] * a[13], b10 = a[9] * a[15] - a[11] * a[13], b11 = a[10] * a[15] - a[11] * a[14];
    const det = 1 / (b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06);
    o[0] = (a[5] * b11 - a[6] * b10 + a[7] * b09) * det; o[1] = (a[2] * b10 - a[1] * b11 - a[3] * b09) * det;
    o[2] = (a[13] * b05 - a[14] * b04 + a[15] * b03) * det; o[3] = (a[10] * b04 - a[9] * b05 - a[11] * b03) * det;
    o[4] = (a[6] * b08 - a[4] * b11 - a[7] * b07) * det; o[5] = (a[0] * b11 - a[2] * b08 + a[3] * b07) * det;
    o[6] = (a[14] * b02 - a[12] * b05 - a[15] * b01) * det; o[7] = (a[8] * b05 - a[10] * b02 + a[11] * b01) * det;
    o[8] = (a[4] * b10 - a[5] * b08 + a[7] * b06) * det; o[9] = (a[1] * b08 - a[0] * b10 - a[3] * b06) * det;
    o[10] = (a[12] * b04 - a[13] * b02 + a[15] * b00) * det; o[11] = (a[9] * b02 - a[8] * b04 - a[11] * b00) * det;
    o[12] = (a[5] * b07 - a[4] * b09 - a[6] * b06) * det; o[13] = (a[0] * b09 - a[1] * b07 + a[2] * b06) * det;
    o[14] = (a[13] * b01 - a[12] * b03 - a[14] * b00) * det; o[15] = (a[8] * b03 - a[9] * b01 + a[10] * b00) * det;
    return o;
  }

  /* --- input ------------------------------------------------------------------------------------------------------------- */
  const held = new Set();
  const hits = new Set();
  const mouse = { x: 0, y: 0, dx: 0, dy: 0, down: false, clicked: false };
  addEventListener('keydown', (e) => {
    if (!held.has(e.code)) hits.add(e.code);
    held.add(e.code);
    if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
    resumeSound();
  });
  addEventListener('keyup', (e) => held.delete(e.code));
  addEventListener('blur', () => held.clear());
  canvas.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.dx += e.movementX || 0;
    mouse.dy += e.movementY || 0;
  });
  canvas.addEventListener('mousedown', () => {
    mouse.down = true;
    mouse.clicked = true;
    resumeSound();
    if (G.camera.lock && document.pointerLockElement !== canvas) canvas.requestPointerLock();
  });
  addEventListener('mouseup', () => { mouse.down = false; });

  /* --- sound ------------------------------------------------------------------------------------------------------------- */
  let ears = null;
  const sounds = {};

  function resumeSound() {
    if (!ears) {
      const Kind = window.AudioContext || window.webkitAudioContext;
      if (Kind) ears = new Kind();
    }
    if (ears && ears.state === 'suspended') ears.resume();
  }

  async function bufferOf(name) {
    if (!sounds[name]) {
      resumeSound();
      if (!ears) return null;
      sounds[name] = await ears.decodeAudioData(await bytesOf(name));
    }
    return sounds[name];
  }

  /* --- moving things ------------------------------------------------------------------------------------------------------ */
  let groundAt = () => -Infinity;

  function boxOf(n) {
    const hx = Math.abs(n.size[0]) / 2, hy = Math.abs(n.size[1]) / 2, hz = Math.abs(n.size[2]) / 2;
    return { lo: [n.pos[0] - hx, n.pos[1] - hy, n.pos[2] - hz], hi: [n.pos[0] + hx, n.pos[1] + hy, n.pos[2] + hz] };
  }

  function blocked(p, half, height) {
    for (const c of colliders) {
      if (!nodes.has(c)) continue;
      const b = boxOf(c);
      if (p[0] + half > b.lo[0] && p[0] - half < b.hi[0] && p[2] + half > b.lo[2] && p[2] - half < b.hi[2] && p[1] + height > b.lo[1] && p[1] < b.hi[1]) return b;
    }
    return null;
  }

  function walker(node, o = {}) {
    /* A character: arrow keys or WASD relative to the camera, a jump, gravity, ground and walls. node.pos is at its feet. */
    const self = { node, speed: o.speed || 6, jump: o.jump === undefined ? 7 : o.jump, gravity: o.gravity || 20, half: o.radius || .35, height: o.height || 1.8, vy: 0, grounded: false, enabled: true, moved: 0 };
    updates.push((dt) => {
      if (!self.enabled) return;
      let fx = 0, fz = 0;
      if (held.has('KeyW') || held.has('ArrowUp')) fz += 1;
      if (held.has('KeyS') || held.has('ArrowDown')) fz -= 1;
      if (held.has('KeyA') || held.has('ArrowLeft')) fx -= 1;
      if (held.has('KeyD') || held.has('ArrowRight')) fx += 1;
      const forward = V.norm([camAt[0] - camEye[0], 0, camAt[2] - camEye[2]]);
      const right = [-forward[2], 0, forward[0]];
      let mv = V.add(V.mul(forward, fz), V.mul(right, fx));
      const l = Math.hypot(mv[0], mv[2]);
      const p = node.pos;
      if (l > 0) {
        mv = V.mul(mv, self.speed * dt / l);
        node.rot = [0, Math.atan2(mv[0], mv[2]) * 180 / Math.PI, 0];
        const nx = [p[0] + mv[0], p[1], p[2]];
        if (!blocked(nx, self.half, self.height)) p[0] = nx[0];
        const nz = [p[0], p[1], p[2] + mv[2]];
        if (!blocked(nz, self.half, self.height)) p[2] = nz[2];
        self.moved += Math.hypot(mv[0], mv[2]);
      }
      if (self.grounded && hits.has('Space') && self.jump) {
        self.vy = self.jump;
        self.grounded = false;
      }
      self.vy -= self.gravity * dt;
      let y = p[1] + self.vy * dt;
      let floor = groundAt(p[0], p[2]);
      const under = blocked([p[0], y, p[2]], self.half, self.height);
      if (under) {
        if (self.vy <= 0 && p[1] >= under.hi[1] - .3) floor = Math.max(floor, under.hi[1]);
        else if (self.vy > 0) {
          self.vy = 0;
          y = p[1];
        }
      }
      if (y <= floor) {
        y = floor;
        self.vy = 0;
        self.grounded = true;
      } else {
        self.grounded = false;
      }
      p[1] = y;
    });
    G.player = self;
    return self;
  }

  /* --- touch and gamepad ------------------------------------------------------------------------------------------------- */
  const timers = [];
  const bars = {};
  const padHeld = new Set();

  function padInput() {
    const pad = (navigator.getGamepads ? [...navigator.getGamepads()] : []).find((p) => p);
    if (!pad) return;
    const set = (code, on) => {
      if (on && !held.has(code)) hits.add(code);
      if (on) { held.add(code); padHeld.add(code); } else if (padHeld.has(code)) { held.delete(code); padHeld.delete(code); }
    };
    set('KeyW', pad.axes[1] < -.3);
    set('KeyS', pad.axes[1] > .3);
    set('KeyA', pad.axes[0] < -.3);
    set('KeyD', pad.axes[0] > .3);
    set('Space', pad.buttons[0] && pad.buttons[0].pressed);
    mouse.dx += (pad.axes[2] || 0) * 6;
    mouse.dy += (pad.axes[3] || 0) * 4;
  }

  if ('ontouchstart' in window) {
    const stick = document.createElement('div');
    stick.id = 'stick';
    document.body.append(stick);
    const move = (e) => {
      const r = stick.getBoundingClientRect();
      const t = e.touches[0];
      const x = (t.clientX - r.left) / r.width - .5;
      const y = (t.clientY - r.top) / r.height - .5;
      for (const [code, on] of [['KeyW', y < -.15], ['KeyS', y > .15], ['KeyA', x < -.15], ['KeyD', x > .15]]) {
        if (on) held.add(code); else held.delete(code);
      }
      e.preventDefault();
    };
    stick.addEventListener('touchstart', move);
    stick.addEventListener('touchmove', move);
    stick.addEventListener('touchend', () => ['KeyW', 'KeyS', 'KeyA', 'KeyD'].forEach((c) => held.delete(c)));
    canvas.addEventListener('touchstart', () => hits.add('Space'));
  }

  /* --- HUD ---------------------------------------------------------------------------------------------------------------- */
  const hud = document.createElement('div');
  hud.id = 'hud';
  document.body.append(hud);
  const banner = document.createElement('div');
  banner.id = 'banner';
  document.body.append(banner);
  const lines = {};
  let bannerUntil = 0;

  /* --- the G everyone talks to --------------------------------------------------------------------------------------------- */
  const G = {
    V,
    time: 0,
    frame: 0,
    quality: 1,
    shadowReach: 34,
    ended: null,
    player: null,
    stats: { fps: 0, drawn: 0 },
    camera: { fov: 55, lock: false, yaw: 0, pitch: 18, distance: 9, height: 1.2, target: null, mode: 'fixed' },
    watched: {},

    box: (o = {}) => options(new Node(boxMesh(), matOf(o)), o),
    ball: (o = {}) => options(new Node(sphereMesh(), matOf(o)), o),
    cylinder: (o = {}) => options(new Node(cylinderMesh(.5), matOf(o)), o),
    cone: (o = {}) => options(new Node(cylinderMesh(.0001), matOf(o)), o),

    ground({ size = 200, cells = 120, height = () => 0, tint = null, ...o } = {}) {
      const n = new Node(gridMesh(size, cells, height, tint), matOf({ rough: .95, ...o }));
      groundAt = height;
      return n;
    },
    heightAt: (x, z) => groundAt(x, z),
    noise(x, z, seed = 0) {
      /* Smooth rolling hills, -1..1: sums of sine waves at unrelated angles. */
      let v = 0, a = .5, f = 1;
      for (let i = 0; i < 4; i++) {
        const c = Math.cos(i * 1.7 + seed), s = Math.sin(i * 1.7 + seed);
        v += a * Math.sin((x * c - z * s) * f + seed * 3.1) * Math.cos((x * s + z * c) * f * .83 + i);
        a *= .5;
        f *= 2.03;
      }
      return v;
    },

    sky({ top, horizon, below, sunHeight = 50, sunTurn = 35, sun = '#fff1dc', sunPower = 3, ambient = '#8ea3c8', fog, fogAmount } = {}) {
      if (top) world.top = colour(top);
      if (horizon) world.horizon = colour(horizon);
      if (below) world.below = colour(below);
      world.fog = colour(fog || horizon || '#c9dcef');
      if (fogAmount !== undefined) world.fogAmount = fogAmount;
      const h = sunHeight * Math.PI / 180;
      const t = sunTurn * Math.PI / 180;
      world.sunDir = V.norm([Math.cos(h) * Math.sin(t), Math.sin(h), Math.cos(h) * Math.cos(t)]);
      world.sunColor = colour(sun).map((v) => v * sunPower);
      world.skyColor = colour(ambient);
      world.groundColor = world.skyColor.map((v) => v * .42);
    },

    async model(name, o = {}) {
      const parts = await loadGlb(name);
      const proto = { name, parts };
      const place = (more = {}) => {
        const n = new Node(null, {});
        n.parts = proto.parts;
        return options(n, { ...o, ...more });
      };
      const first = place();
      first.copy = place;
      return first;
    },

    async texture(name) {
      const blob = await (await fetch(assetUrl(name))).blob();
      return textureFrom(await createImageBitmap(blob));
    },

    walker,
    update: (fn) => updates.push(fn),
    key: (code) => held.has(code),
    pressed: (code) => hits.has(code),
    mouse,
    near: (a, b, d) => V.dist(a.pos || a, b.pos || b) <= d,
    all: (tag) => [...nodes].filter((n) => n.tags.has(tag)),

    ray(from, dir, far = 100, tag = null) {
      /* The nearest box hit: {node, at, distance} or null. */
      const d = V.norm(dir);
      let best = null;
      for (const n of nodes) {
        if (!n.visible || (tag ? !n.tags.has(tag) : !colliders.includes(n))) continue;
        const b = boxOf(n);
        let lo = 0, hi = far, ok = true;
        for (let k = 0; k < 3 && ok; k++) {
          if (Math.abs(d[k]) < 1e-8) {
            if (from[k] < b.lo[k] || from[k] > b.hi[k]) ok = false;
          } else {
            let t1 = (b.lo[k] - from[k]) / d[k];
            let t2 = (b.hi[k] - from[k]) / d[k];
            if (t1 > t2) [t1, t2] = [t2, t1];
            lo = Math.max(lo, t1);
            hi = Math.min(hi, t2);
            if (lo > hi) ok = false;
          }
        }
        if (ok && (!best || lo < best.distance)) best = { node: n, at: V.add(from, V.mul(d, lo)), distance: lo };
      }
      return best;
    },

    /* something on a timer: G.after(2, fn), G.every(.5, fn) */
    after(seconds, fn) {
      timers.push({ at: G.time + seconds, fn, every: 0 });
    },
    every(seconds, fn) {
      timers.push({ at: G.time + seconds, fn, every: seconds });
    },

    /* a thing that walks after a target over the ground, and does something on reaching it */
    chaser(node, target, { speed = 3, sight = 20, reach = 1.5, onReach = null, lift = 1 } = {}) {
      updates.push((dt) => {
        if (!nodes.has(node)) return;
        const t = target.pos || target;
        const d = V.dist(node.pos, t);
        if (d > sight) return;
        if (d < reach) {
          if (onReach) onReach(node);
          return;
        }
        const way = Math.atan2(t[0] - node.pos[0], t[2] - node.pos[2]);
        node.pos[0] += Math.sin(way) * speed * dt;
        node.pos[2] += Math.cos(way) * speed * dt;
        const g = groundAt(node.pos[0], node.pos[2]);
        if (g > -Infinity) node.pos[1] = g + lift;
        node.rot[1] = way * 180 / Math.PI;
      });
      return node;
    },

    /* a thing that flies straight and calls hit(target) on what it touches, tagged */
    shoot(from, dir, { speed = 22, size = .22, color = '#ffd27a', life = 2.5, tag = '', hit = null } = {}) {
      const n = G.ball({ at: from, size, color, emit: color, glow: 1.5 });
      n.noShadow = true;
      const way = V.mul(V.norm(dir), speed);
      const born = G.time;
      const fly = (dt) => {
        if (!nodes.has(n)) return;
        n.pos = V.add(n.pos, V.mul(way, dt));
        if (G.time - born > life) {
          n.remove();
          return;
        }
        if (tag) {
          for (const t of G.all(tag)) {
            if (V.dist(t.pos, n.pos) < (Math.max(...t.size) * .6 + size)) {
              n.remove();
              if (hit) hit(t);
              return;
            }
          }
        }
      };
      updates.push(fly);
      return n;
    },

    /* small things flying apart: an explosion, a pickup, a hit */
    burst(at, { count = 18, color = '#ffc070', speed = 6, life = .8, size = .16 } = {}) {
      const bits = [];
      for (let i = 0; i < count; i++) {
        const b = G.box({ at, size, color, emit: color, glow: 1 });
        b.noShadow = true;
        b.way = V.norm([G.random(-1, 1), G.random(.1, 1.2), G.random(-1, 1)]);
        bits.push(b);
      }
      const born = G.time;
      updates.push((dt) => {
        if (!bits.length) return;
        const age = G.time - born;
        for (const b of bits) {
          b.pos = V.add(b.pos, V.mul(b.way, speed * dt * (1 - age / life)));
          b.way[1] -= dt * 1.4;
          const s = size * Math.max(0, 1 - age / life);
          b.size = [s, s, s];
        }
        if (age > life) {
          bits.forEach((b) => b.remove());
          bits.length = 0;
        }
      });
    },

    /* a bar on the screen: health, time, charge */
    bar(id, value, max = 100, color = '#e34948') {
      let el = bars[id];
      if (!el) {
        el = bars[id] = document.createElement('div');
        el.className = 'bar';
        el.innerHTML = '<i></i>';
        hud.append(el);
      }
      el.firstChild.style.width = `${Math.max(0, Math.min(100, value / max * 100))}%`;
      el.firstChild.style.background = color;
    },

    /* what stays between plays */
    save(key, value) {
      try { localStorage.setItem(`game:${key}`, JSON.stringify(value)); } catch (e) { /* a private window keeps nothing */ }
    },
    load(key, fallback = null) {
      try {
        const v = localStorage.getItem(`game:${key}`);
        return v === null ? fallback : JSON.parse(v);
      } catch (e) {
        return fallback;
      }
    },

    /* a small map in the corner: dots for what is tagged */
    minimap(tags = {}, range = 60) {
      const c = document.createElement('canvas');
      c.width = c.height = 150;
      c.id = 'minimap';
      document.body.append(c);
      const x2 = c.getContext('2d');
      updates.push(() => {
        x2.clearRect(0, 0, 150, 150);
        x2.fillStyle = 'rgba(255,255,255,.8)';
        x2.fillRect(0, 0, 150, 150);
        const dot = (p, colour, r) => {
          x2.fillStyle = colour;
          x2.beginPath();
          x2.arc(75 + p[0] / range * 75, 75 + p[2] / range * 75, r, 0, 7);
          x2.fill();
        };
        for (const [tag, colour] of Object.entries(tags)) G.all(tag).forEach((n) => dot(n.pos, colour, 2.5));
        if (G.player) dot(G.player.node.pos, '#111113', 3.5);
      });
    },

    follow(node, o = {}) {
      Object.assign(G.camera, { target: node, mode: 'follow', ...o });
    },
    lookFrom(eye, at) {
      G.camera.mode = 'fixed';
      camEye = eye.slice();
      camAt = at.slice();
    },

    async sound(name, { volume = 1, loop = false } = {}) {
      const buffer = await bufferOf(name);
      if (!buffer || !ears) return null;
      const src = ears.createBufferSource();
      src.buffer = buffer;
      src.loop = loop;
      const gain = ears.createGain();
      gain.gain.value = volume;
      src.connect(gain).connect(ears.destination);
      src.start();
      return src;
    },

    show(id, text) {
      if (!lines[id]) {
        lines[id] = document.createElement('div');
        hud.append(lines[id]);
      }
      lines[id].textContent = text;
    },
    message(text, seconds = 2) {
      banner.textContent = text;
      banner.style.opacity = 1;
      bannerUntil = G.time + seconds;
    },
    watch(name, value) {
      /* A number a machine player should see: score, lives, enemies left. */
      G.watched[name] = value;
    },
    end(text) {
      if (G.ended) return;
      G.ended = text;
      banner.textContent = `${text}  ·  按 R 重新开始`;
      banner.style.opacity = 1;
      bannerUntil = Infinity;
    },
    random: (lo = 0, hi = 1) => lo + (hi - lo) * rand(),
  };

  let seed = 12345;
  function rand() {  // the same game every time, so that a bug can be found again
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  }

  function moveCamera() {
    const c = G.camera;
    if (c.mode !== 'follow' || !c.target) return;
    const sensitivity = .18;
    c.yaw -= mouse.dx * sensitivity;
    c.pitch = Math.max(-5, Math.min(70, c.pitch + mouse.dy * sensitivity));
    const yaw = c.yaw * Math.PI / 180;
    const pitch = c.pitch * Math.PI / 180;
    const at = V.add(c.target.pos, [0, c.height, 0]);
    const eye = V.add(at, [Math.sin(yaw) * Math.cos(pitch) * c.distance, Math.sin(pitch) * c.distance, Math.cos(yaw) * Math.cos(pitch) * c.distance]);
    eye[1] = Math.max(eye[1], groundAt(eye[0], eye[2]) + .4);  // the camera does not go under the hill
    camAt = V.lerp(camAt, at, .25);
    camEye = V.lerp(camEye, eye, .2);
  }

  function step(dt) {
    G.time += dt;
    G.frame += 1;
    if (!G.ended) {
      for (const fn of updates) fn(dt);
      for (const t of timers.slice()) {
        if (G.time >= t.at) {
          t.fn();
          if (t.every) t.at += t.every;
          else timers.splice(timers.indexOf(t), 1);
        }
      }
      padInput();
    }
    moveCamera();
    if (G.ended && hits.has('KeyR')) location.reload();
    if (G.time > bannerUntil) banner.style.opacity = 0;
    hits.clear();
    mouse.dx = 0;
    mouse.dy = 0;
    mouse.clicked = false;
  }

  let last = 0;
  let spent = 0;
  let counted = 0;
  function frame(now) {
    const dt = Math.min(.1, (now - last) / 1000 || .016);  // a slow chip plays at its own frame rate, not in slow motion
    last = now;
    step(dt);
    render();
    spent += dt;
    counted += 1;
    if (spent > .5) {
      G.stats.fps = Math.round(counted / spent);
      spent = 0;
      counted = 0;
    }
    requestAnimationFrame(frame);
  }

  /* What a machine player reads. codegame.py play calls this between its key presses. */
  window.__report = () => {
    const p = G.player && G.player.node;
    return {
      time: +G.time.toFixed(2), frames: G.frame, fps: G.stats.fps, things: nodes.size, ended: G.ended, watched: G.watched,
      player: p ? { pos: p.pos.map((v) => +v.toFixed(2)), moved: +G.player.moved.toFixed(2), grounded: G.player.grounded } : null,
    };
  };

  window.G = G;
  window.__start = () => requestAnimationFrame((t) => {
    last = t;
    frame(t);
  });
}());
