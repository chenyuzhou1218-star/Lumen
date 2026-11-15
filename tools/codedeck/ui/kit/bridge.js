/* The way to the tool's Python (webshell.py): QWebChannel inside the window, one call and one signal.
     call(name, args)  -> a promise of the answer of the Python method api_<name>(**args)
     on(type, fn)      -> the events Python sends ({type, ...}); returns a function that takes the listener off
   Opened in an ordinary browser (to look at the page while making it, or for screenshots), a stand-in answers from
   window.__SAMPLE__ = {boot: {...}, answers: {name: answer}} instead, so nothing here depends on being in the tool. */

let ready = null;
const listeners = {};

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = reject;
    document.head.append(s);
  });
}

function fire(text) {
  let ev;
  try { ev = typeof text === 'string' ? JSON.parse(text) : text; } catch { return; }
  (listeners[ev.type] || []).forEach((f) => f(ev));
  (listeners['*'] || []).forEach((f) => f(ev));
}

export function bridge() {
  if (ready) return ready;
  ready = (async () => {
    if (window.qt && window.qt.webChannelTransport) {
      if (!window.QWebChannel) await loadScript('qrc:///qtwebchannel/qwebchannel.js');
      const obj = await new Promise((resolve) => {
        new window.QWebChannel(window.qt.webChannelTransport, (ch) => resolve(ch.objects.tool));
      });
      obj.event.connect(fire);
      return {
        call: (name, args) => new Promise((resolve) => obj.call(name, JSON.stringify(args || {}), (r) => {
          let v = null;
          try { v = r ? JSON.parse(r) : null; } catch { v = null; }
          if (v && v.__error) console.error(`${name}: ${v.__error}`);
          resolve(v);
        })),
        live: true,
      };
    }
    const sample = window.__SAMPLE__ || {};
    window.__fire = fire; // a screenshot script can play events
    return {
      call: async (name) => {
        if (name === 'boot') return sample.boot || {};
        const a = (sample.answers || {})[name];
        return a === undefined ? {} : a;
      },
      live: false,
    };
  })();
  return ready;
}

export async function call(name, args) {
  const b = await bridge();
  return b.call(name, args);
}

export function on(type, fn) {
  (listeners[type] = listeners[type] || new Set()).add(fn);
  return () => listeners[type].delete(fn);
}

/* 浅色 / 深色: the mode comes in the address (?mode=dark, so the first paint is right), then follows Lumen's setting. */
export function applyMode(mode) {
  const m = mode === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.mode = m;
  return m;
}

export function startMode() {
  const q = new URLSearchParams(location.search);
  applyMode(q.get('mode'));
  on('theme', (ev) => applyMode(ev.mode));
  if (q.get('still') === '1') document.documentElement.classList.add('still');
}
