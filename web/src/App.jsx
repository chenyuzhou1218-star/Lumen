import { useCallback, useEffect, useRef, useState } from 'react';
import { bridge } from './bridge.js';
import { Chat, Home, ToolPane } from './Chat.jsx';
import { Plugins } from './Plugins.jsx';
import { Settings } from './Settings.jsx';
import { Sidebar } from './Sidebar.jsx';
import { Slot, Suspend } from './Slot.jsx';
import { Icon } from './icons.jsx';
import { setCatalog, t } from './i18n.js';
import { Asks } from './Questions.jsx';
import { Prefs } from './prefs.js';
import { Terminal } from './Terminal.jsx';
import { Browser } from './Browser.jsx';
import { Onboarding, Welcome } from './Onboarding.jsx';

const NARROW = 880; // below this the sidebar is a narrow column, and opens over the page

function useWidth() {
  const [w, setW] = useState(window.innerWidth);
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    window.addEventListener('resize', on);
    return () => window.removeEventListener('resize', on);
  }, []);
  return w;
}

function remembered(key, fallback) {
  try {
    const v = JSON.parse(localStorage.getItem(`lumen.${key}`));
    return v === null ? fallback : v;
  } catch (e) {
    return fallback;
  }
}

function remember(key, value) {
  try { localStorage.setItem(`lumen.${key}`, JSON.stringify(value)); } catch (e) { /* a convenience only */ }
}

/* A page still drawn by Qt (settings, plugins, 详细): room for it beside the sidebar, and for 详细 a line to go back. */
function NativePage({ api, view }) {
  return (
    <div className="native">
      {view.key === 'details' && (
        <header className="native-head">
          <button className="back" onClick={() => api.back()}><Icon name="back" size={15} />{t('返回对话')}</button>
          <span className="sep" />
          <b>{t('详细')}</b>
        </header>
      )}
      <Slot api={api} name="page" className="page-slot">
        <div className="page-wait"><span className="spin" /></div>
      </Slot>
    </div>
  );
}

/* A line to drag: up and down (the browser above the terminal) or left and right (the panel's width). */
function Handle({ dir, onMove, title }) {
  const down = (e) => {
    e.preventDefault();
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    document.body.classList.add(dir === 'x' ? 'dragging-x' : 'dragging-y');
    const move = (ev) => onMove(ev);
    const up = () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointercancel', up);
      el.removeEventListener('lostpointercapture', up);
      document.body.classList.remove('dragging-x', 'dragging-y');
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    el.addEventListener('lostpointercapture', up);
  };
  return <div className={`handle handle-${dir}`} onPointerDown={down} title={title}><i /></div>;
}

/* The panel on the right: the browser above, the terminal below, the line between them dragged; either alone fills it.
   The browser's pages are a real Chromium view lying over the room left for them (web_dock.py). */
function RightPanel({ api, docks, prefs, width, setWidth, split, setSplit }) {
  const area = useRef(null);
  const browser = docks.includes('browser');
  const terminal = docks.includes('terminal');
  return (
    <aside className="rpanel" style={{ width }}>
      <Handle dir="x" title={t('拖动来调整宽度')} onMove={(ev) => setWidth(window.innerWidth - ev.clientX)} />
      <div className="rpanel-body" ref={area}>
        {browser && <Browser api={api} style={terminal ? { height: `${split * 100}%` } : { flex: 1 }} />}
        {browser && terminal && (
          <Handle dir="y" title={t('拖动来调整大小')} onMove={(ev) => {
            const r = area.current.getBoundingClientRect();
            setSplit(Math.round(Math.max(0.15, Math.min(0.85, (ev.clientY - r.top) / r.height)) * 1000) / 1000);
          }} />
        )}
        {terminal && <Terminal api={api} prefs={prefs} close={() => api.go('terminal')} />}
      </div>
    </aside>
  );
}

const PREF_CLASS = (p) => [
  `fs-${p.font_size || 'normal'}`, `cw-${p.chat_width || 'normal'}`, p.reduced_motion ? 'still' : '', p.figure_motion !== false ? 'float' : '',
].filter(Boolean).join(' ');

const ONBOARDING = new URLSearchParams(location.search).get('boot') === 'onboarding';

/* Before any window: the greeting, the first-run setup, or why a folder did not open (the launcher's own page). */
function OnboardingApp() {
  const [api, setApi] = useState(null);
  const [info, setInfo] = useState(null);
  useEffect(() => {
    bridge().then(async (b) => {
      const r = await b.boot();
      setCatalog(r.lang, r.catalog);
      document.documentElement.dataset.mode = (r.prefs || {}).mode === 'dark' ? 'dark' : 'light';
      setInfo(r);
      setApi(b);
    });
  }, []);
  if (!api || !info) return <div className="booting" />;
  return <Onboarding api={api} texts={info.texts} still={!!(info.prefs || {}).reduced_motion} />;
}

export function App() {
  if (ONBOARDING) return <OnboardingApp />;
  return <Shell />;
}

function Shell() {
  const [api, setApi] = useState(null);
  const [boot, setBoot] = useState(null);
  const [prefs, setPrefs] = useState({});
  const [view, setView] = useState({ page: 'home' });
  const [side, setSide] = useState(null);
  const [home, setHome] = useState(null);
  const [chat, setChat] = useState(null);
  const [tool, setTool] = useState({ on: false, name: '' });
  const [asks, setAsks] = useState({ approvals: [], questions: [] }); // waiting for the user: approvals and questions
  const [toolShare, setToolShare] = useState(() => remembered('toolWidth', 0.5)); // half of the window, on the right
  const [command, setCommand] = useState(null);
  const [collapsed, setCollapsedRaw] = useState(() => remembered('sideCollapsed', new URLSearchParams(location.search).get('side') === 'closed'));
  const [overlay, setOverlay] = useState(false);
  const [welcome, setWelcome] = useState(false); // 播放一次开场动画 (设置 → 外观)
  const [panel, setPanel] = useState(() => remembered('panelWidth', 0));
  const [split, setSplit] = useState(() => remembered('panelSplit', 0.5));
  const width = useWidth();
  const docks = (side && side.docks) || [];
  // the panel on the right: as wide as the user left it, never so wide that the chat has no room
  const panelWidth = docks.length ? Math.round(Math.min(Math.max(240, Math.min(panel || width * 0.4, width - 58 - 360)), Math.max(160, width - 58 - 320))) : 0;
  const narrow = width - panelWidth < NARROW;
  const timer = useRef(null);

  useEffect(() => {
    bridge().then(async (b) => {
      const info = await b.boot();
      setCatalog(info.lang, info.catalog);
      setPrefs(info.prefs || {});
      setBoot(info);
      setApi(b);
      b.home().then(setHome); // the @ tools and the project, for the chat page's box too
      b.sidebar().then(setSide);
      b.on('show', (v) => { setView(v); setOverlay(false); });
      b.on('changed', () => setView((v) => ({ ...v })));
      b.on('side', setSide);
      b.on('tool', setTool);
      b.on('asks', setAsks);
      b.asks().then(setAsks);
      b.on('prefs', setPrefs);
      b.on('command', (c) => setCommand({ ...c, at: Date.now() }));
    });
  }, []);

  // Ctrl+B and the panel button: the sidebar put away or back; in a narrow window it opens over the page instead
  const setCollapsed = useCallback((v) => {
    if (narrow) { setOverlay(!v); return; }
    setCollapsedRaw(v);
    remember('sideCollapsed', v);
  }, [narrow]);
  useEffect(() => {
    if (command && command.do === 'toggle_side') setCollapsed(narrow ? overlay : !collapsed);
    if (command && command.do === 'welcome') setWelcome(true);
  }, [command]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!narrow) setOverlay(false); }, [narrow]);
  useEffect(() => { remember('toolWidth', toolShare); }, [toolShare]);
  useEffect(() => { if (panel) remember('panelWidth', panel); }, [panel]);
  useEffect(() => { remember('panelSplit', split); }, [split]);

  useEffect(() => {
    document.documentElement.dataset.mode = prefs.mode === 'dark' ? 'dark' : 'light'; // 浅色 / 深色: every page at once
    const [main, , soft, bright] = prefs.accent_colours || [];
    const dark = prefs.mode === 'dark';
    const colour = (dark ? bright : main) || main || '#2f6bff';
    const rgb = colour.replace('#', '').match(/../g).map((h) => parseInt(h, 16));
    const light = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) > 160; // a light accent takes dark text
    const root = document.documentElement.style;
    root.setProperty('--accent', colour);
    root.setProperty('--accent-soft', dark ? 'rgba(255,255,255,.12)' : soft || '#e8efff');
    root.setProperty('--on-accent', light ? '#151517' : '#ffffff');
    root.fontSize = { small: '14px', large: '18px' }[prefs.font_size] || '16px'; // every text size is in rem
  }, [prefs]);

  const loadChat = useCallback(async (b, id, current = () => true) => {
    const c = await b.chat(id);
    if (!current()) return c; // another chat was opened meanwhile: this answer (and its message box) is not for it
    setChat((old) => (old && JSON.stringify(old) === JSON.stringify(c) ? old : c));
    return c;
  }, []);

  useEffect(() => {
    if (!api) return undefined;
    clearTimeout(timer.current);
    if (view.page === 'home') {
      api.home().then(setHome);
      return undefined;
    }
    if (view.page !== 'chat') return undefined;
    let alive = true;
    const poll = async () => {
      const c = await loadChat(api, view.task_id, () => alive);
      if (alive) timer.current = setTimeout(poll, c && c.running ? 700 : 2500);
    };
    poll();
    return () => { alive = false; clearTimeout(timer.current); };
  }, [api, view, loadChat]);

  if (!api || !boot || !side) return <div className="booting" />;
  let main = null;
  if (view.page === 'home') {
    main = home && <Home api={api} home={home} setBox={(box) => setHome((h) => ({ ...h, box }))} />;
  } else if (view.page === 'chat') {
    main = chat && <Chat api={api} chat={chat} side={side} command={command} view={view}
      tools={(home && home.tools) || []} setBox={(box) => setChat((c) => ({ ...c, box }))} />;
  } else if (view.page === 'plugins') {
    main = <Plugins api={api} />;
  } else if (view.page === 'settings') {
    main = <Settings api={api} view={view} />;
  } else if (view.page === 'native') {
    main = <NativePage api={api} view={view} />;
  }
  const rail = narrow || collapsed;
  return (
    <Prefs.Provider value={prefs}>
      <Asks.Provider value={asks}>
      <Suspend.Provider value={overlay}>
        <div className={`app ${PREF_CLASS(prefs)}${rail ? ' railed' : ''}`}>
          <Sidebar api={api} side={side} view={view} collapsed={rail} setCollapsed={setCollapsed} mark={home && home.lumen} />
          {overlay && (
            <>
              <div className="scrim" onClick={() => setOverlay(false)} />
              <Sidebar api={api} side={side} view={view} collapsed={false} setCollapsed={() => setOverlay(false)} overlay mark={home && home.lumen} />
            </>
          )}
          <main className="main" key={view.page === 'native' ? `n-${view.key}` : view.page}>{main}</main>
          <ToolPane api={api} tool={tool} share={toolShare} setShare={setToolShare} />
          {welcome && boot.welcome && (
            <div className="welcome-over"><Welcome texts={boot.welcome} proceed={() => setWelcome(false)} still={!!prefs.reduced_motion} /></div>
          )}
          {docks.length > 0 && <RightPanel api={api} docks={docks} prefs={prefs} width={panelWidth} setWidth={setPanel} split={split} setSplit={setSplit} />}
        </div>
      </Suspend.Provider>
      </Asks.Provider>
    </Prefs.Provider>
  );
}
