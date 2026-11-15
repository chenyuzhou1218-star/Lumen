import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Button, Light, Mark, MenuButton, useSize } from './controls.jsx';

/* The bar at the top of every tool: its mark and name, the project, and the buttons. When the window gets narrow the
   buttons fold step by step - first to icons, then into a ⋯ menu - so nothing is ever cut off or pushed out.
     ghosts   [{key, label, icon, tip, act, on}]          quiet buttons (新建, 打开, 让 AI 做 ...)
     actions  [{key, label, icon, primary, act, disabled, busy}]   what the tool does (black when primary)
     opens    [{key, label, tip, act, disabled}]            files made, opened with the computer's own programs
     examples [{label, act}]                                the 例子 menu */
const LEVELS = 5; // 0 all words ... 4 everything that can fold is folded

export function ToolBar({ glyph, name, project, where, dirty, examples = [], ghosts = [], actions = [], opens = [], extra, running }) {
  const ref = useRef(null);
  const { w } = useSize(ref);
  const [level, setLevel] = useState(0);
  // the words can change under React's feet (the translation of the page is put in after it is drawn, and English is wider than 中文):
  // when a text on the bar changes by itself, fit it again
  const [words, setWords] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    let t = 0;
    const seen = new MutationObserver(() => { clearTimeout(t); t = setTimeout(() => setWords((n) => n + 1), 60); });
    seen.observe(el, { characterData: true, subtree: true });
    return () => { seen.disconnect(); clearTimeout(t); };
  }, []);
  // whenever the room or what is on the bar changes, start again from all words and fold until it fits (before paint)
  const sig = [w, words, project, dirty, running, opens.length, ghosts.length, actions.map((a) => a.label + (a.busy ? '*' : '')).join()].join('|');
  const lastSig = useRef(sig);
  useLayoutEffect(() => {
    if (sig !== lastSig.current) { lastSig.current = sig; if (level) { setLevel(0); return; } }
    const el = ref.current;
    const who = el && el.querySelector('.who');
    const over = el && (el.scrollWidth > el.clientWidth + 1 || (who && who.scrollWidth > who.clientWidth + 1));
    if (over && level < LEVELS - 1) setLevel(level + 1);
  });

  const compact = level >= 1;
  const foldTools = level >= 2;
  const foldActions = level >= 3;
  const tight = level >= 4;
  const primary = actions.filter((a) => a.primary);
  const others = actions.filter((a) => !a.primary);
  const folded = [
    ...(foldActions ? others.map((a) => ({ label: a.label, icon: a.icon || 'play', disabled: a.disabled, act: a.act })) : []),
    ...(foldActions && others.length && (foldTools && (ghosts.length || opens.length)) ? [null] : []),
    ...(foldTools ? ghosts.map((g) => ({ label: g.label, icon: g.icon, act: g.act, disabled: g.disabled })) : []),
    ...(foldTools && opens.length ? [...(ghosts.length ? [null] : []), ...opens.map((o) => ({ label: o.label, icon: 'open', disabled: o.disabled, act: o.act }))] : []),
  ];
  const spin = (a) => (a.busy ? <span className="spin" style={a.primary ? { borderTopColor: 'var(--on-ink)' } : undefined} /> : null);

  return (
    <header className="bar" ref={ref}>
      <div className="who">
        <Mark glyph={glyph} />
        <b>{name}</b>
        {project && !tight && <span className="crumb">/</span>}
        {project && !tight && <span className="project" title={where}>{project}</span>}
        {dirty && <span className="unsaved">· 未保存</span>}
        {examples.length > 0 && (
          <MenuButton items={[{ heading: '打开一个现成的例子' }, ...examples.map((e) => ({ icon: 'folder', ...e }))]} compact={foldTools}
            icon={foldTools ? 'grid' : undefined} tip="例子">例子</MenuButton>
        )}
      </div>
      <div className="tools">
        {extra}
        {!foldTools && ghosts.map((g) => <Button key={g.key || g.label} kind="ghost" icon={g.icon} compact={compact} tip={g.tip || g.label} disabled={g.disabled}
          className={g.on ? 'on' : ''} onClick={g.act}>{g.label}</Button>)}
        {!foldTools && ghosts.length > 0 && actions.length > 0 && <span className="vr" />}
        {!foldActions && others.map((a) => (
          <Button key={a.key || a.label} kind={a.kind || ''} icon={a.icon} compact={compact && !!a.icon} disabled={a.disabled} tip={a.tip || a.label} onClick={a.act}>
            {spin(a)}{a.label}
          </Button>
        ))}
        {primary.map((a) => (
          <Button key={a.key || a.label} kind="primary" disabled={a.disabled} icon={tight ? a.icon || 'play' : undefined} compact={tight} tip={a.tip || a.label} onClick={a.act}>
            {!tight && spin(a)}{a.label}
          </Button>
        ))}
        {!foldTools && opens.length > 0 && <span className="vr" />}
        {!foldTools && (!compact || opens.length < 2)
          && opens.map((o) => <Button key={o.key || o.label} kind="ghost" icon="open" compact={compact} tip={o.tip || o.label} disabled={o.disabled} onClick={o.act}>{o.label}</Button>)}
        {!foldTools && compact && opens.length > 1
          && <MenuButton icon="open" compact tip="打开做好的文件" align="right" items={opens.map((o) => ({ label: o.label, icon: 'open', disabled: o.disabled, act: o.act }))}>打开</MenuButton>}
        {folded.length > 0 && <MenuButton kind="icon" icon="more" chev={false} tip="更多" align="right" items={folded} />}
      </div>
    </header>
  );
}

/* The line at the bottom: a light (amber working, green done, red failed), what happened, where the project is. */
export function Foot({ status, where, children }) {
  return (
    <footer className="foot">
      <Light kind={status && status.kind} />
      <span className="status" title={status && status.text}>{status && status.text}</span>
      {children}
      {where && <span className="where" title={where}>{'‎' + where}</span>}
    </footer>
  );
}
