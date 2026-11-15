import { useEffect, useRef, useState } from 'react';
import { call, on } from './bridge.js';
import { Button, Light, Mark } from './controls.jsx';

/* 让 AI 做: a panel on the right that asks Lumen's team to work on this project (ai_panel.py runs
   `codedoctor fix --with <tool> --no-window "<request>"`). Its log, light and buttons come from Python as "ai" events,
   so closing and opening the panel again keeps what happened. */
export function AIPanel({ name, project, sub, hint, close }) {
  const [ai, setAi] = useState({ log: [], status: 'Ctrl+Enter 交给 AI', light: '', busy: false, can_open: false });
  const [text, setText] = useState('');
  const logRef = useRef(null);
  const boxRef = useRef(null);

  useEffect(() => {
    call('ai_state').then((s) => s && setAi(s));
    return on('ai', (ev) => setAi((a) => ({ ...a, ...ev, log: ev.add ? [...a.log, ...ev.add] : ev.log || a.log })));
  }, []);
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [ai.log.length]);
  useEffect(() => { if (boxRef.current) boxRef.current.focus(); }, []);
  useEffect(() => {
    const key = (e) => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [close]);

  const send = () => {
    const t = text.trim();
    if (!t || ai.busy) return;
    call('ai_send', { text: t }).then((r) => { if (r && r.ok) setText(''); });
  };

  return (
    <>
      <div className="drawer-scrim" onMouseDown={close} />
      <aside className="drawer" role="dialog" aria-label="让 AI 帮你做">
        <div className="drawer-head">
          <Mark glyph="spark" size={28} />
          <span className="two"><b>让 AI 帮你做</b><small>{project ? `${name} · ${project}` : name}</small></span>
          <Button kind="icon" icon="close" tip="收起 · Esc" onClick={close} />
        </div>
        <p className="drawer-sub">{sub}</p>
        <div className="console" ref={logRef}>
          {ai.log.length ? ai.log.map((l, i) => <div key={i} className={l.me ? 'me' : ''}>{l.text}</div>) : <span className="ph">AI 的每一步会显示在这里。</span>}
        </div>
        <div className="askbox">
          <textarea ref={boxRef} value={text} placeholder={hint} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } }} />
          <div className="row">
            <Light kind={ai.light} />
            <span className="faint" title={ai.status}>{ai.status}</span>
            {ai.busy && <Button kind="ghost" small icon="stop" onClick={() => call('ai_stop')}>停止</Button>}
            {ai.can_open && <Button kind="ghost" small icon="open" onClick={() => call('ai_open_lumen')}>打开 Lumen</Button>}
            <Button kind="primary" small icon="spark" disabled={ai.busy || !text.trim()} onClick={send}>交给 AI</Button>
          </div>
        </div>
      </aside>
    </>
  );
}
