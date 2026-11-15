import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './icons.jsx';
import { t } from './i18n.js';

/* The controls of the settings and the dialogs: drawn here, so that they look the same everywhere and nothing opens a
   window of the system's own. */

function useDismiss(open, refs, close) {
  useEffect(() => {
    if (!open) return undefined;
    const down = (e) => { if (!refs.some((r) => r.current && r.current.contains(e.target))) close(); };
    const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('mousedown', down, true);
    document.addEventListener('keydown', key, true);
    window.addEventListener('blur', close);
    return () => {
      document.removeEventListener('mousedown', down, true);
      document.removeEventListener('keydown', key, true);
      window.removeEventListener('blur', close);
    };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
}

/* A list under (or above, when there is no room below) its anchor, in the page's top layer. */
function Drop({ anchor, open, close, children, width }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  useDismiss(open, [ref, anchor], close);
  useLayoutEffect(() => {
    if (!open || !anchor.current) return;
    const place = () => {
      const r = anchor.current.getBoundingClientRect();
      const h = ref.current ? ref.current.offsetHeight : 240;
      const below = window.innerHeight - r.bottom - 12;
      const up = below < Math.min(h, 260) && r.top > below;
      const w = Math.max(width || 0, r.width);
      setPos({ left: Math.max(8, Math.min(r.left, window.innerWidth - w - 8)), width: w,
        top: up ? undefined : r.bottom + 4, bottom: up ? window.innerHeight - r.top + 4 : undefined,
        maxHeight: Math.max(140, (up ? r.top : below) - 12) });
    };
    place();
    const scroller = anchor.current.closest('.page, .modal-body');
    if (scroller) scroller.addEventListener('scroll', close, { once: true });
    window.addEventListener('resize', close);
    return () => window.removeEventListener('resize', close);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!open) return null;
  return createPortal(<div ref={ref} className="drop" style={pos || { visibility: 'hidden' }}>{children}</div>, document.body);
}

export function Select({ value, options, onChange, placeholder, disabled, className = '', width }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const cur = options.find((o) => o.value === value);
  return (
    <>
      <button ref={ref} type="button" className={`select${open ? ' open' : ''} ${className}`} disabled={disabled} onClick={() => setOpen(!open)}>
        <span className={cur ? '' : 'ph'}>{cur ? cur.label : placeholder || t('请选择')}</span>
        <Icon name="chev" size={14} />
      </button>
      <Drop anchor={ref} open={open} close={() => setOpen(false)} width={width}>
        {options.map((o) => (
          <button key={String(o.value)} type="button" className={`item${o.value === value ? ' current' : ''}`}
            onClick={() => { setOpen(false); if (o.value !== value) onChange(o.value); }}>
            <span className="two"><b>{o.label}</b>{o.note && <small>{o.note}</small>}</span>
            {o.value === value && <Icon name="check" className="ok" />}
          </button>
        ))}
      </Drop>
    </>
  );
}

/* Typed freely, with the names the service lists offered as one types. Changes are given on Enter or leaving the field. */
export function Combo({ value, options, onCommit, placeholder, disabled, className = '' }) {
  const [text, setText] = useState(value || '');
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => setText(value || ''), [value]);
  const q = text.trim().toLowerCase();
  const shown = options.filter((o) => !q || o.toLowerCase().includes(q) || o === value).slice(0, 80);
  const commit = (v) => {
    setOpen(false);
    if ((v || '').trim() !== (value || '')) onCommit((v || '').trim());
  };
  return (
    <div className={`combo ${className}`} ref={ref}>
      <input value={text} disabled={disabled} placeholder={placeholder} spellCheck={false}
        onChange={(e) => { setText(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
        onBlur={(e) => { if (!document.querySelector('.drop')?.contains(e.relatedTarget)) commit(text); }}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit(text); e.currentTarget.blur(); } if (e.key === 'Escape') { setText(value || ''); setOpen(false); } }} />
      {options.length > 0 && !disabled && (
        <button type="button" tabIndex={-1} className="combo-open" onMouseDown={(e) => { e.preventDefault(); setOpen(!open); }} aria-label={t('可选的模型')}>
          <Icon name="chev" size={14} />
        </button>
      )}
      <Drop anchor={ref} open={open && shown.length > 0} close={() => setOpen(false)}>
        {shown.map((o) => (
          <button key={o} type="button" className={`item${o === value ? ' current' : ''}`} onMouseDown={(e) => e.preventDefault()}
            onClick={() => { setText(o); commit(o); }}>
            <span className="mono">{o}</span>{o === value && <Icon name="check" className="ok" />}
          </button>
        ))}
      </Drop>
    </div>
  );
}

export function Switch({ on, onChange, label, note, disabled }) {
  return (
    <label className={`switch-row${disabled ? ' disabled' : ''}`}>
      <span className="two"><b>{label}</b>{note && <small>{note}</small>}</span>
      <button type="button" role="switch" aria-checked={on} className={`switch${on ? ' on' : ''}`} disabled={disabled} onClick={() => onChange(!on)}><i /></button>
    </label>
  );
}

export function Segmented({ value, options, onChange }) {
  return (
    <div className="segmented" role="radiogroup">
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={o.value === value} className={o.value === value ? 'on' : ''}
          onClick={() => o.value !== value && onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Field({ label, note, children, wide }) {
  return (
    <div className={`field${wide ? ' wide' : ''}`}>
      <div className="field-label"><b>{label}</b>{note && <small>{note}</small>}</div>
      <div className="field-control">{children}</div>
    </div>
  );
}

/* A dialog over the page: Escape or a click beside it closes it (unless busy). */
export function Modal({ title, children, footer, close, width = 520, busy }) {
  const ref = useRef(null);
  useEffect(() => {
    const key = (e) => { if (e.key === 'Escape' && !busy && !document.querySelector('.drop')) close(); };
    document.addEventListener('keydown', key);
    const first = ref.current && ref.current.querySelector('input:not([disabled]), textarea, button.primary');
    if (first) first.focus();
    return () => document.removeEventListener('keydown', key);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return createPortal(
    <div className="modal-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) close(); }}>
      <div className="modal" style={{ width: `min(${width}px, calc(100vw - 32px))` }} ref={ref} role="dialog" aria-modal="true">
        <header className="modal-head"><h3>{title}</h3>
          <button type="button" className="head-btn" onClick={close} disabled={busy} aria-label={t('关闭')} title={t('关闭')}><Icon name="close" size={14} /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>, document.body);
}

/* Asking before something that cannot be undone, or telling what happened. buttons: [{label, primary, danger, act}] */
export function Ask({ title, text, details, buttons, close }) {
  return (
    <Modal title={title} close={close} width={460} footer={buttons.map((b) => (
      <button key={b.label} type="button" className={`btn${b.primary ? ' primary' : ''}${b.danger ? ' danger' : ''}`}
        onClick={() => { close(); if (b.act) b.act(); }}>{b.label}</button>
    ))}>
      <p className="ask-text">{text}</p>
      {details && details.length > 0 && <ul className="ask-list">{details.map((d) => <li key={d}>{d}</li>)}</ul>}
    </Modal>
  );
}
