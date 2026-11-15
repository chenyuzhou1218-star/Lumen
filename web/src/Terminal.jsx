import { useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';
import { Icon } from './icons.jsx';
import { t } from './i18n.js';

/* The terminal on the right: PowerShell in a real console (desktop/conpty.py, run by web_dock.py), drawn by xterm.js -
   its own banner, prompt, colours, Tab completion and arrow keys, as in Windows Terminal. White in the light mode and
   black in the dark one, like every page; the size of its text is the user's (设置 → 外观). What the team ran is listed
   above it, apart from the user's own shell. */

const THEMES = {
  light: { background: '#ffffff', foreground: '#1d1d22', cursor: '#1d1d22', cursorAccent: '#ffffff', selectionBackground: '#cfdcff',
    black: '#1d1d22', red: '#c4313b', green: '#1f8a4c', yellow: '#9a6a00', blue: '#2458d6', magenta: '#9b3fc4', cyan: '#0e7f8c', white: '#6b6b74',
    brightBlack: '#77777f', brightRed: '#d9434d', brightGreen: '#23964f', brightYellow: '#a86f00', brightBlue: '#2f6bff', brightMagenta: '#a64bd1',
    brightCyan: '#13879a', brightWhite: '#3a3a40' },
  dark: { background: '#121214', foreground: '#dcdce2', cursor: '#e8e8ee', cursorAccent: '#121214', selectionBackground: '#2e4370',
    black: '#3a3a42', red: '#ef6b73', green: '#8fcf72', yellow: '#e5c07b', blue: '#61afef', magenta: '#c678dd', cyan: '#56b6c2', white: '#c8c8d0',
    brightBlack: '#7f7f8a', brightRed: '#ff7b84', brightGreen: '#a5e075', brightYellow: '#f0d28c', brightBlue: '#7cc0ff', brightMagenta: '#d793ec',
    brightCyan: '#6fcfd8', brightWhite: '#ffffff' },
};
const FONT = '"Cascadia Mono", "Cascadia Code", Consolas, "Microsoft YaHei UI", monospace';

export function Terminal({ api, prefs, close }) {
  const host = useRef(null);
  const term = useRef(null);
  const refit = useRef(() => {});
  const [ran, setRan] = useState([]);
  const [showRan, setShowRan] = useState(false);
  const [menu, setMenu] = useState(null);
  const mode = prefs.mode === 'dark' ? 'dark' : 'light';
  const size = prefs.term_font || 13;

  useEffect(() => {
    const x = new XTerm({ fontFamily: FONT, fontSize: size, lineHeight: 1.2, cursorBlink: true, cursorStyle: 'block', scrollback: 5000,
      theme: THEMES[mode], allowProposedApi: false, convertEol: false, rightClickSelectsWord: false, macOptionIsMeta: false });
    term.current = x;
    x.open(host.current);
    const fit = () => {
      const el = host.current;
      const cell = x._core && x._core._renderService && x._core._renderService.dimensions.css.cell;
      if (!el || !cell || !cell.width || !cell.height) return;
      const st = getComputedStyle(el); // the room inside the padding, less a scroll bar's width
      const w = el.clientWidth - parseFloat(st.paddingLeft) - parseFloat(st.paddingRight) - 12;
      const h = el.clientHeight - parseFloat(st.paddingTop) - parseFloat(st.paddingBottom);
      const cols = Math.max(20, Math.floor(w / cell.width));
      const rows = Math.max(5, Math.floor(h / cell.height));
      if (cols !== x.cols || rows !== x.rows) {
        x.resize(cols, rows);
        api.termResize(cols, rows);
      }
    };
    refit.current = fit;
    const ro = new ResizeObserver(() => fit());
    ro.observe(host.current);
    x.onData((data) => api.termInput(data));
    x.attachCustomKeyEventHandler((e) => {
      // Ctrl+C copies when something is selected (as Windows Terminal does); Ctrl+V pastes
      if (e.type === 'keydown' && e.ctrlKey && (e.key === 'c' || e.key === 'C') && x.hasSelection()) { api.copy(x.getSelection()); x.clearSelection(); return false; }
      if (e.type === 'keydown' && e.ctrlKey && (e.key === 'v' || e.key === 'V')) return false; // the browser's own paste event types it
      return true;
    });
    let alive = true;
    api.termState().then((s) => {
      if (!alive || !s) return;
      if (s.log) x.write(s.log);
      setRan(s.ran || []);
      fit();
      x.focus();
    });
    const off = api.on('term', (m) => {
      if (m.out) x.write(m.out);
      if (m.exit) x.write(`\r\n\x1b[2m${t('PowerShell 已退出。按任意键重新打开。')}\x1b[0m\r\n`);
      if (m.ran) setRan((r) => [...r, m.ran].slice(-50));
    });
    const first = setTimeout(fit, 30);
    return () => { alive = false; clearTimeout(first); off(); ro.disconnect(); x.dispose(); term.current = null; };
  }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const x = term.current;
    if (!x) return;
    x.options.theme = THEMES[mode];
    x.options.fontSize = size;
    const later = setTimeout(() => refit.current(), 30); // a new size of text: as many columns and rows as now fit
    return () => clearTimeout(later);
  }, [mode, size]);

  const picked = () => {
    const x = term.current;
    if (!x) return '';
    if (x.hasSelection()) return x.getSelection();
    const buf = x.buffer.active;
    const lines = [];
    for (let i = Math.max(0, buf.length - 40); i < buf.length; i += 1) lines.push(buf.getLine(i).translateToString(true));
    return lines.join('\n').replace(/\n+$/, '');
  };
  const last = ran[ran.length - 1];
  return (
    <section className={`term ${mode}`}>
      <header className="term-head">
        <Icon name="terminal" size={14} /><b>{t('终端')}</b><span>PowerShell</span>
        <span className="grow" />
        {last && (
          <button className="ran" onClick={() => setShowRan(!showRan)} title={t('AI 运行过的命令')}>
            <em>{last.who}</em><span>{last.command}</span><i>{ran.length}</i>
          </button>
        )}
        <button onClick={() => api.termToChat(picked())} title={t('把选中的（或最近的输出）发给 Lumen')} aria-label={t('发给 Lumen')}><Icon name="send" size={14} /></button>
        <button onClick={() => { term.current && term.current.clear(); api.termInput('\x1b'); api.termInput('cls\r'); }} title={t('清屏')} aria-label={t('清屏')}><Icon name="archive" size={14} /></button>
        <button onClick={() => api.termInterrupt()} title={t('停止正在运行的命令') + ' · Ctrl+C'} aria-label={t('停止')}><Icon name="stop" size={13} /></button>
        <button onClick={close} title={t('关闭终端')} aria-label={t('关闭终端')}><Icon name="close" size={13} /></button>
      </header>
      {showRan && ran.length > 0 && (
        <ol className="ran-list">
          {ran.slice().reverse().map((r, i) => <li key={i}><em>{r.who}</em><code>{r.command}</code></li>)}
        </ol>
      )}
      <div className="term-screen" ref={host} onContextMenu={(e) => { e.preventDefault(); setMenu({ x: e.clientX, y: e.clientY, text: picked() }); }} />
      {menu && (
        <div className="menu" style={{ left: Math.min(menu.x, window.innerWidth - 230), top: Math.min(menu.y, window.innerHeight - 110) }}
          onMouseLeave={() => setMenu(null)}>
          <button className="item" onClick={() => { api.copy(menu.text); setMenu(null); }}><Icon name="copy" size={15} /><span>{t('复制')}</span></button>
          <button className="item" onClick={() => { api.termToChat(menu.text); setMenu(null); }}><Icon name="send" size={15} /><span>{t('发给 Lumen')}</span></button>
        </div>
      )}
    </section>
  );
}
