import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Icon } from './icons.jsx';

/* A small menu at a point (a right click, or under a ⋯ button): kept inside the window, closed by a click elsewhere,
   Escape, or choosing. items: {icon, label, act, note, danger} or null for a line. */
export function Menu({ at, items, close, align = 'right' }) {
  const ref = useRef(null);
  const [pos, setPos] = useState({ left: -9999, top: -9999 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    let left = align === 'right' ? at.x - w : at.x;
    let top = at.y + 4;
    if (top + h > window.innerHeight - 8) top = Math.max(8, at.y - h - 4);
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    setPos({ left, top });
  }, [at, align]);
  useEffect(() => {
    const down = (e) => { if (ref.current && !ref.current.contains(e.target)) close(); };
    const key = (e) => { if (e.key === 'Escape') close(); };
    const away = () => close();
    document.addEventListener('mousedown', down, true);
    document.addEventListener('keydown', key);
    window.addEventListener('blur', away);
    window.addEventListener('resize', away);
    return () => {
      document.removeEventListener('mousedown', down, true);
      document.removeEventListener('keydown', key);
      window.removeEventListener('blur', away);
      window.removeEventListener('resize', away);
    };
  }, [close]);
  return (
    <div className="menu" ref={ref} style={pos} role="menu">
      {items.map((it, i) => (it ? (
        <button key={i} role="menuitem" className={`item${it.danger ? ' danger' : ''}`} onClick={() => { close(); it.act(); }}>
          {it.icon && <Icon name={it.icon} size={15} />}
          <span className="two"><b>{it.label}</b>{it.note && <small>{it.note}</small>}</span>
        </button>
      ) : <hr key={i} />))}
    </div>
  );
}
