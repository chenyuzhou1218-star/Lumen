import { useCallback, useEffect, useRef, useState } from 'react';
import { t } from './i18n.js';

/* How hard the model thinks, as the Qt window drew it (desktop/picker.py ThinkSlider): a thick rounded track; the knob
   follows the pointer and, let go, springs onto the nearest stop with a small overshoot; light flows along the filled part
   toward the knob; the top stop turns violet and bursts. ← → (and Home, End) move it from the keyboard. White or dark
   with the window. levels: [{key, name}]; onChange(key) when a stop is chosen. */

const H = 30;        // the track's height
const PAD = 14;      // room around it for the top stop's glow and burst
const ease = (x) => { const c = 1.70158; const c3 = c + 1; return 1 + c3 * (x - 1) ** 3 + c * (x - 1) ** 2; }; // OutBack

function mix(a, b, k) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  const q = Math.max(0, Math.min(1, k));
  return `#${x.map((v, i) => Math.round(v + (y[i] - v) * q).toString(16).padStart(2, '0')).join('')}`; // hex, so it can be mixed again
}

export function ThinkSlider({ levels, value, onChange }) {
  const n = levels.length;
  const start = Math.max(0, levels.findIndex((l) => l.key === value));
  const canvas = useRef(null);
  const box = useRef(null);
  const st = useRef({ pos: start, from: start, to: start, began: 0, dragging: false, particles: [], burst: [], last: 0 });
  const [shown, setShown] = useState(start); // the stop under the knob: its name is shown, and follows a drag

  // a new value from outside (another box, the model changed): spring there
  useEffect(() => {
    const s = st.current;
    if (!s.dragging && s.to !== start) { s.from = s.pos; s.to = start; s.began = performance.now(); setShown(start); }
  }, [start]);

  const spring = useCallback((to) => {
    const s = st.current;
    const reachedTop = to === n - 1 && s.to !== to;
    s.from = s.pos; s.to = to; s.began = performance.now();
    setShown(to);
    if (reachedTop) s.burstAt = performance.now();
  }, [n]);

  const choose = useCallback((i) => {
    const to = Math.max(0, Math.min(n - 1, i));
    spring(to);
    if (levels[to] && levels[to].key !== value) onChange(levels[to].key);
  }, [n, levels, value, onChange, spring]);

  useEffect(() => {
    const cv = canvas.current;
    const ctx = cv.getContext('2d');
    const s = st.current;
    let seed = 11;
    const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    const particle = (fresh) => [rnd() * (fresh ? 1 : 0.25), rnd() * 2 - 1, 0.1 + rnd() * 0.18, [1, 1.3, 1.7, 2.2][Math.floor(rnd() * 4)], rnd()];
    s.particles = Array.from({ length: 34 }, () => particle(true));
    let frame = 0;
    const draw = (now) => {
      const dpr = window.devicePixelRatio || 1;
      const w = cv.clientWidth;
      const h = cv.clientHeight;
      if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const dark = document.documentElement.dataset.mode === 'dark';
      const dt = Math.min((now - (s.last || now)) / 1000, 0.05);
      s.last = now;
      if (!s.dragging) { // the spring
        const k = Math.min(1, (now - s.began) / 340);
        s.pos = s.from + (s.to - s.from) * ease(k);
      }
      const r = H / 2;
      const x0 = PAD + r;
      const span = Math.max(1, w - 2 * PAD - 2 * r);
      const xAt = (p) => x0 + (p * span) / Math.max(1, n - 1);
      const cy = h / 2;
      const top = Math.max(0, s.pos - (n - 2)); // 0..1 over the last step
      const track = { x: PAD, y: cy - r + 3, w: w - 2 * PAD, h: H - 6 };
      const round = (x, y, ww, hh, rr) => { ctx.beginPath(); ctx.roundRect(x, y, Math.max(ww, 0.1), hh, rr); };
      // the top stop glows violet all round
      if (top > 0) {
        [[12, 0.07], [7, 0.12], [3, 0.18]].forEach(([g, a]) => {
          ctx.fillStyle = `rgba(139,43,226,${a * top})`;
          round(track.x - g, track.y - g, track.w + 2 * g, track.h + 2 * g, track.h / 2 + g); ctx.fill();
        });
      }
      ctx.fillStyle = dark ? '#2c2c33' : '#ebebf0';
      round(track.x, track.y, track.w, track.h, track.h / 2); ctx.fill();
      // the filled part, its colour following the knob: blue, deeper, violet at the top
      const kx = xAt(s.pos);
      const k01 = s.pos / Math.max(1, n - 1);
      const ca = mix(mix('#5b9bff', '#2f6bff', k01 * 1.4), '#3b2fd6', top);
      const cb = mix(mix('#2f6bff', '#1f3fd0', k01), '#8b2be2', top);
      const fillW = kx - track.x + r - 3;
      const grad = ctx.createLinearGradient(track.x, 0, track.x + Math.max(fillW, 1), 0);
      grad.addColorStop(0, ca); grad.addColorStop(1, cb);
      ctx.save();
      round(track.x, track.y, fillW, track.h, track.h / 2);
      ctx.fillStyle = grad; ctx.fill(); ctx.clip();
      // light flowing to the knob, drawn to the centre line as it nears it
      const speed = 0.6 + 0.35 * s.pos;
      s.particles.forEach((p) => {
        p[0] += p[2] * dt * speed;
        p[1] *= 1 - 1.6 * dt * p[0];
        p[4] += dt * 0.7;
        if (p[0] >= 1) { const q = particle(false); for (let i = 0; i < 5; i += 1) p[i] = q[i]; }
        const x = track.x + 4 + p[0] * (kx - track.x - 8);
        const y = cy + p[1] * (track.h / 2 - 4);
        const tw = 0.55 + 0.45 * Math.sin(p[4] * 6);
        ctx.fillStyle = `rgba(255,255,255,${(70 + 150 * tw * Math.min(1, p[0] * 3)) / 255})`;
        ctx.beginPath(); ctx.arc(x, y, p[3] * 0.6, 0, Math.PI * 2); ctx.fill();
      });
      const glow = ctx.createLinearGradient(kx - 60, 0, kx, 0);
      glow.addColorStop(0, 'rgba(255,255,255,0)'); glow.addColorStop(1, `rgba(255,255,255,${0.24 * (1 - 0.6 * top)})`);
      ctx.fillStyle = glow; ctx.fillRect(kx - 60, track.y, 60, track.h);
      ctx.restore();
      // the stops not reached yet
      ctx.fillStyle = dark ? 'rgba(255,255,255,.28)' : 'rgba(15,23,42,.24)';
      for (let i = 0; i < n; i += 1) if (xAt(i) > kx + r) { ctx.beginPath(); ctx.arc(xAt(i), cy, 2.4, 0, Math.PI * 2); ctx.fill(); }
      // the top stop's burst
      if (s.burstAt && now - s.burstAt < 30) {
        s.burstAt = 0;
        for (let i = 0; i < 30; i += 1) { const a = rnd() * Math.PI * 2; const v = 30 + rnd() * 60; s.burst.push([xAt(n - 1), cy, Math.cos(a) * v, Math.sin(a) * v, 1]); }
      }
      s.burst = s.burst.filter((b) => b[4] > 0);
      s.burst.forEach((b) => {
        b[0] += b[2] * dt; b[1] += b[3] * dt; b[3] += 60 * dt; b[4] -= dt * 1.6;
        ctx.fillStyle = `rgba(${b[4] > 0.5 ? '139,43,226' : '255,196,61'},${Math.max(0, b[4])})`;
        ctx.beginPath(); ctx.arc(b[0], b[1], 2.4, 0, Math.PI * 2); ctx.fill();
      });
      // the knob
      ctx.fillStyle = dark ? 'rgba(0,0,0,.45)' : 'rgba(15,23,42,.16)';
      ctx.beginPath(); ctx.arc(kx, cy + 1.5, r - 1.5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = dark ? '#f4f4f7' : '#ffffff';
      ctx.beginPath(); ctx.arc(kx, cy, r - 3, 0, Math.PI * 2); ctx.fill();
      ctx.lineWidth = 1 + 1.2 * top;
      ctx.strokeStyle = top > 0 ? `rgba(139,43,226,${0.2 + 0.55 * top})` : (dark ? 'rgba(255,255,255,.25)' : 'rgba(15,23,42,.10)');
      ctx.stroke();
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [n]);

  const posAt = (clientX) => {
    const rect = canvas.current.getBoundingClientRect();
    const span = Math.max(1, rect.width - 2 * PAD - H);
    return Math.max(0, Math.min(n - 1, ((clientX - rect.left - PAD - H / 2) * (n - 1)) / span));
  };
  const down = (e) => {
    e.preventDefault();
    const s = st.current;
    e.currentTarget.setPointerCapture(e.pointerId);
    s.dragging = true;
    s.pos = posAt(e.clientX);
    setShown(Math.round(s.pos));
    box.current && box.current.focus();
  };
  const move = (e) => {
    const s = st.current;
    if (!s.dragging) return;
    s.pos = posAt(e.clientX);
    setShown(Math.round(s.pos));
  };
  const up = () => {
    const s = st.current;
    if (!s.dragging) return;
    s.dragging = false;
    choose(Math.round(s.pos));
  };
  const key = (e) => {
    const s = st.current;
    const at = s.to;
    const go = { ArrowLeft: at - 1, ArrowDown: at - 1, ArrowRight: at + 1, ArrowUp: at + 1, Home: 0, End: n - 1 }[e.key];
    if (go === undefined) return;
    e.preventDefault();
    choose(go);
  };
  const name = levels[shown] ? levels[shown].name : '';
  return (
    <div className="think">
      <div className="think-head"><span>{t('思考')}</span><b key={name}>{name}</b></div>
      <div ref={box} className="think-track" tabIndex={0} role="slider" aria-label={t('思考')} aria-valuemin={0} aria-valuemax={n - 1}
        aria-valuenow={shown} aria-valuetext={name} onKeyDown={key} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
        <canvas ref={canvas} style={{ height: H + 2 * PAD }} />
      </div>
      <div className="think-stops" style={{ padding: `0 ${PAD + H / 2 - 24}px` }}>
        {levels.map((l, i) => (
          <button key={l.key} type="button" className={i === shown ? 'on' : ''} onClick={() => choose(i)} tabIndex={-1}>{l.name}</button>
        ))}
      </div>
    </div>
  );
}
