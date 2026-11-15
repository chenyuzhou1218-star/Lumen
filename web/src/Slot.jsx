import { createContext, useContext, useLayoutEffect, useRef } from 'react';

/* Room for a part that stays Qt: an @ tool's own window, or a page not drawn here yet. The page only leaves the room
   and says where it is (Bridge.slot); Python puts the widget there, over the page. While something of the page's own
   must lie over that room (the sidebar opened over a narrow window), the room is given up for the time. */
export const Suspend = createContext(false);

export function Slot({ api, name, className = '', style, children }) {
  const ref = useRef(null);
  const suspended = useContext(Suspend);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    let last = '';
    const report = () => {
      const r = el.getBoundingClientRect();
      const rect = suspended ? { x: 0, y: 0, w: 0, h: 0 } : { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
      const was = last ? JSON.parse(last) : null;
      // a change under 2px is not told (0.5px of layout noise moved the native window and repainted everything)
      if (was && Math.max(Math.abs(was.x - rect.x), Math.abs(was.y - rect.y), Math.abs(was.w - rect.w), Math.abs(was.h - rect.h)) < 2
        && (rect.w > 0) === (was.w > 0)) return;
      const key = JSON.stringify(rect);
      if (key !== last) { last = key; api.slot(name, rect); }
    };
    const ro = new ResizeObserver(report);
    ro.observe(el);
    ro.observe(document.body);
    window.addEventListener('resize', report);
    const timer = setInterval(report, 500); // a move without a resize (the sidebar put away) is caught as well
    report();
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', report);
      clearInterval(timer);
      api.slot(name, { x: 0, y: 0, w: 0, h: 0 });
    };
  }, [api, name, suspended]);
  return <div ref={ref} className={`slot ${className}`} style={style}>{children}</div>;
}
