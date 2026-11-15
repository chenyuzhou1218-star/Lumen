import { forwardRef, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './icons.jsx';

/* The pieces every tool's page is made of. Drawn here so that they look the same in every tool and nothing opens a
   window of its own: menus, choices and questions are all in the page. */

/* kind: '' (outlined), 'primary' (black), 'ghost' (no border), 'icon' (square). With `compact` only the icon shows
   (the words become the tooltip): what a narrow window does with its bar. */
export const Button = forwardRef(function Button({ kind = '', icon, children, tip, onClick, disabled, compact, small, className = '', chev, ...rest }, ref) {
  const words = compact && icon ? null : children;
  const title = tip || (compact && typeof children === 'string' ? children : undefined);
  return (
    <button ref={ref} type="button" className={`btn ${kind}${small ? ' small' : ''}${!words && kind !== 'icon' ? ' only' : ''} ${className}`} title={title}
      aria-label={typeof children === 'string' ? children : tip} onClick={onClick} disabled={disabled} {...rest}>
      {icon && <Icon name={icon} size={kind === 'icon' ? 16 : 15} />}
      {words}
      {chev && <Icon name="chev" size={13} className="chev" />}
    </button>
  );
});

export function Mark({ glyph, size = 26 }) {
  return <span className="mark" style={{ width: size, height: size, borderRadius: Math.round(size * 0.3) }}><Icon name={glyph} size={Math.round(size * 0.62)} stroke={1.6} /></span>;
}

export function Light({ kind }) {
  return <i className={`light ${kind || ''}`} />;
}

export function Card({ title, icon, chip, chipKind, tools, children, className = '', style }) {
  return (
    <section className={`card ${className}`} style={style}>
      <header className="card-head">
        {icon && <Icon name={icon} size={15} />}
        <b title={typeof title === 'string' ? title : undefined}>{title}</b>
        {chip ? <span className={`chip ${chipKind || ''}`}>{chip}</span> : null}
        <div className="tools">{tools}</div>
      </header>
      <div className="card-body">{children}</div>
    </section>
  );
}

export function Empty({ icon = 'dot', title, hint, children }) {
  return (
    <div className="empty">
      <span className="box"><Icon name={icon} size={22} stroke={1.25} /></span>
      <b>{title}</b>
      {hint && <p>{hint}</p>}
      {children && <div className="row">{children}</div>}
    </div>
  );
}

/* What came out of a run, one line each: warnings in amber, errors in red, the rest quiet. items: [{text, kind}] */
export function Notes({ items, empty = '运行一次，结果写在这里。' }) {
  return (
    <div className="notes">
      {items && items.length ? items.map((n, i) => (
        <div key={i} className={`note ${n.kind || ''}`}><i /><span>{n.text}</span></div>
      )) : <div className="none">{empty}</div>}
    </div>
  );
}

/* --- menus ------------------------------------------------------------------------------------------------------ */

function useDismiss(open, refs, close) {
  useEffect(() => {
    if (!open) return undefined;
    const down = (e) => { if (!refs.some((r) => r.current && r.current.contains(e.target))) close(); };
    const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    const away = () => close();
    document.addEventListener('mousedown', down, true);
    document.addEventListener('keydown', key, true);
    window.addEventListener('blur', away);
    window.addEventListener('resize', away);
    return () => {
      document.removeEventListener('mousedown', down, true);
      document.removeEventListener('keydown', key, true);
      window.removeEventListener('blur', away);
      window.removeEventListener('resize', away);
    };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
}

/* A list under (or above, when there is no room below) its anchor, kept inside the window.
   items: [{icon, label, note, act, disabled, current, danger}] | null for a line | {heading} for a small title */
export function Menu({ anchor, open, close, items, align = 'left', width }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  useDismiss(open, [ref, anchor], close);
  useLayoutEffect(() => {
    if (!open || !anchor.current) { setPos(null); return; }
    const r = anchor.current.getBoundingClientRect();
    const el = ref.current;
    const w = Math.max(width || 0, el ? el.offsetWidth : 200);
    const h = el ? el.offsetHeight : 200;
    const below = window.innerHeight - r.bottom - 8;
    const up = below < h && r.top > below;
    let left = align === 'right' ? r.right - w : r.left;
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    setPos({ left, top: up ? Math.max(8, r.top - h - 4) : r.bottom + 4, minWidth: width, maxHeight: Math.max(120, (up ? r.top : below) - 8) });
  }, [open, items && items.length]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!open) return null;
  return createPortal(
    <div ref={ref} className="menu" role="menu" style={pos || { left: -9999, top: -9999, minWidth: width }}>
      {items.map((it, i) => {
        if (!it) return <hr key={i} />;
        if (it.heading) return <div key={i} className="label">{it.heading}</div>;
        return (
          <button key={i} type="button" role="menuitem" disabled={it.disabled} className={`item${it.current ? ' current' : ''}${it.danger ? ' danger' : ''}`}
            onClick={() => { close(); it.act(); }} title={it.tip}>
            {it.icon && <Icon name={it.icon} size={15} />}
            <span className="two"><b>{it.label}</b>{it.note && <small>{it.note}</small>}</span>
            {it.current && <Icon name="check" size={15} className="check" />}
          </button>
        );
      })}
    </div>, document.body);
}

/* A button that opens a menu. */
export function MenuButton({ items, children, icon, kind = 'ghost', compact, align, tip, chev = true, disabled, className, width }) {
  const ref = useRef(null);
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      <Button ref={ref} kind={kind} icon={icon} compact={compact} tip={tip} chev={chev && !compact} disabled={disabled}
        className={`${open ? 'on' : ''} ${className || ''}`} onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>{children}</Button>
      <Menu anchor={ref} open={open} close={close} items={items} align={align} width={width} />
    </>
  );
}

/* A quiet picker (which picture, which page): its current choice and a menu of the others. options: [{value, label}] */
export function Pick({ value, options, onChange, tip }) {
  const ref = useRef(null);
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const cur = options.find((o) => o.value === value);
  return (
    <>
      <button ref={ref} type="button" className="pick" title={tip} onClick={() => setOpen(!open)}>
        <span>{cur ? cur.label : ''}</span><Icon name="chev" size={13} />
      </button>
      <Menu anchor={ref} open={open} close={close} align="right" items={options.map((o) => ({ label: o.label, current: o.value === value, act: () => onChange(o.value) }))} />
    </>
  );
}

/* A field that chooses one of a few: looks like an input, opens a list drawn by the page (never the system's own). */
export function Select({ value, options, onChange, placeholder = '请选择', autoFocus }) {
  const ref = useRef(null);
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const cur = options.find((o) => o.value === value);
  useEffect(() => { if (autoFocus && ref.current) ref.current.focus(); }, [autoFocus]);
  return (
    <>
      <button ref={ref} type="button" className={`input select${open ? ' open' : ''}`} onClick={() => setOpen(!open)}
        onKeyDown={(e) => {
          if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
          e.preventDefault();
          const i = Math.max(0, options.findIndex((o) => o.value === value));
          const n = options[(i + (e.key === 'ArrowDown' ? 1 : options.length - 1)) % options.length];
          if (n) onChange(n.value);
        }}>
        <span className={cur ? '' : 'ph'}>{cur ? cur.label : placeholder}</span>
        <Icon name="chev" size={14} />
      </button>
      <Menu anchor={ref} open={open} close={close} width={ref.current ? ref.current.offsetWidth : undefined}
        items={options.map((o) => ({ label: o.label, note: o.note, current: o.value === value, act: () => onChange(o.value) }))} />
    </>
  );
}

/* --- dialogs ---------------------------------------------------------------------------------------------------- */

export function Modal({ title, sub, children, foot, onClose, width }) {
  useEffect(() => {
    const key = (e) => { if (e.key === 'Escape' && onClose) { e.stopPropagation(); onClose(); } };
    document.addEventListener('keydown', key, true);
    return () => document.removeEventListener('keydown', key, true);
  }, [onClose]);
  return createPortal(
    <div className="scrim" onMouseDown={(e) => { if (e.target === e.currentTarget && onClose) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" style={width ? { width } : undefined}>
        <div className="modal-head"><b>{title}</b>{sub && <p>{sub}</p>}</div>
        {children && <div className="modal-body">{children}</div>}
        {foot && <div className="modal-foot">{foot}</div>}
      </div>
    </div>, document.body);
}

/* One question at a time, asked from anywhere: await ask.choose(...) / ask.confirm(...) / ask.form(...).
   <Asker /> is put once in the page. */
let pushAsk = null;
export function Asker() {
  const [q, setQ] = useState(null);
  useEffect(() => { pushAsk = setQ; return () => { pushAsk = null; }; }, []);
  if (!q) return null;
  const done = (v) => { setQ(null); q.resolve(v); };
  if (q.kind === 'choose') {
    return (
      <Modal title={q.title} sub={q.sub} onClose={() => done(null)} foot={<Button onClick={() => done(null)}>取消</Button>}>
        <div className="choices">
          {q.options.map((o, i) => (
            <button key={i} type="button" className="choice" onClick={() => done(o.value)} autoFocus={i === 0}>
              {o.icon && <Icon name={o.icon} size={18} />}
              <span><b>{o.label}</b>{o.note && <small>{o.note}</small>}</span>
            </button>
          ))}
        </div>
      </Modal>
    );
  }
  if (q.kind === 'confirm') {
    return (
      <Modal title={q.title} sub={q.sub} onClose={() => done(null)}
        foot={<>{q.buttons.map((b, i) => <Button key={i} kind={b.kind || ''} onClick={() => done(b.value)} autoFocus={!!b.focus}>{b.label}</Button>)}</>} />
    );
  }
  return <FormAsk q={q} done={done} />;
}

function FormAsk({ q, done }) {
  const [vals, setVals] = useState(() => Object.fromEntries(q.fields.map((f) => [f.key, f.value ?? ''])));
  const missing = q.fields.some((f) => f.required && !String(vals[f.key] || '').trim());
  const submit = () => { if (!missing) done(vals); };
  return (
    <Modal title={q.title} sub={q.sub} onClose={() => done(null)} width={q.width}
      foot={<><Button onClick={() => done(null)}>取消</Button><Button kind="primary" disabled={missing} onClick={submit}>{q.ok || '好'}</Button></>}>
      {q.fields.map((f, i) => (
        <label key={f.key} className="lbl" onClick={f.options ? (e) => e.preventDefault() : undefined}>
          {f.label}
          {f.options
            ? <Select value={vals[f.key]} options={f.options} autoFocus={i === 0} onChange={(v) => setVals({ ...vals, [f.key]: v })} />
            : f.type === 'number'
            ? <input className="input" type="number" min={f.min} max={f.max} step={f.step} value={vals[f.key]} autoFocus={i === 0}
                onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter') submit(); }} />
            : f.multiline
            ? <textarea className="area" value={vals[f.key]} placeholder={f.placeholder} autoFocus={i === 0}
                onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey) submit(); }} />
            : <input className="input" value={vals[f.key]} placeholder={f.placeholder} autoFocus={i === 0}
                onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter') submit(); }} />}
        </label>
      ))}
    </Modal>
  );
}

function open(q) {
  return new Promise((resolve) => { if (pushAsk) pushAsk({ ...q, resolve }); else resolve(null); });
}
export const ask = {
  choose: (title, options, sub) => open({ kind: 'choose', title, options, sub }),
  confirm: (title, sub, buttons) => open({ kind: 'confirm', title, sub, buttons }),
  form: (title, fields, opts = {}) => open({ kind: 'form', title, fields, ...opts }),
};

/* --- sizes ------------------------------------------------------------------------------------------------------ */

/* The size of an element (or of the window when no ref is given), kept up to date. */
export function useSize(ref) {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight });
  useLayoutEffect(() => {
    if (!ref) {
      const f = () => setSize({ w: window.innerWidth, h: window.innerHeight });
      window.addEventListener('resize', f);
      return () => window.removeEventListener('resize', f);
    }
    const el = ref.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

function remembered(key, fallback) {
  try { const v = parseFloat(localStorage.getItem(key)); return Number.isFinite(v) ? v : fallback; } catch { return fallback; }
}

/* Two panes side by side (or one above the other with vertical) and a grip between them. `first` is the first pane's
   share (0..1), remembered under `name`; each pane keeps at least `min` pixels. */
export function Split({ vertical, first = 0.5, min = 220, minSecond, name, children }) {
  const ref = useRef(null);
  const key = name ? `split:${name}` : '';
  const [share, setShare] = useState(() => (key ? remembered(key, first) : first));
  const [drag, setDrag] = useState(false);
  const size = useSize(ref);
  const total = vertical ? size.h : size.w;
  const room = Math.max(0, total - 10);
  const lo = Math.min(min, room / 2);
  const hi = Math.max(lo, room - Math.min(minSecond ?? min, room / 2));
  const px = Math.max(lo, Math.min(hi, share * room));
  const startDrag = (e) => {
    e.preventDefault();
    const r = ref.current.getBoundingClientRect();
    setDrag(true);
    const move = (ev) => {
      const at = vertical ? ev.clientY - r.top : ev.clientX - r.left;
      const s = Math.max(lo, Math.min(hi, at - 5)) / Math.max(1, room);
      setShare(s);
      if (key) try { localStorage.setItem(key, String(s)); } catch { /* the page still works without it */ }
    };
    const up = () => { setDrag(false); window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };
  const [a, b] = children;
  return (
    <div ref={ref} className={`split${vertical ? ' v' : ''}`}>
      <div className="pane" style={vertical ? { height: px, flex: 'none' } : { width: px, flex: 'none' }}>{a}</div>
      <div className={`grip${drag ? ' dragging' : ''}`} onMouseDown={startDrag} role="separator" aria-orientation={vertical ? 'horizontal' : 'vertical'} />
      <div className="pane" style={{ flex: 1 }}>{b}</div>
    </div>
  );
}
