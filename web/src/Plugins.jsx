import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './icons.jsx';
import { t } from './i18n.js';

/* 插件: every tool beside Lumen on one page, the big ones first, then CodeTools' small plugins by group. A click opens
   it; a word in the box finds it. The list and the drawings come from Python (web_chat.plugins_json), so a plugin added
   to CodeTools appears here without anything changing in this file. */

function Glyph({ svg, size = 16, stroke = 1.5 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" dangerouslySetInnerHTML={{ __html: svg || '' }} />
  );
}

function Card({ name, about, mark, big, glyphs, onOpen }) {
  return (
    <button className={`pcard${big ? ' big' : ''}`} onClick={onOpen} title={about}>
      <span className="pmark"><Glyph svg={glyphs[mark]} size={16} /></span>
      <span className="pname">{name}</span>
      <Icon name="chevRight" size={14} className="pgo" />
      <span className="pabout">{about}</span>
    </button>
  );
}

export function Plugins({ api }) {
  const [data, setData] = useState(null);
  const [needle, setNeedle] = useState('');
  const box = useRef(null);
  useEffect(() => {
    let alive = true;
    api.plugins().then((d) => alive && setData(d));
    const off = api.on('plugins_ready', (d) => alive && setData(d));
    return () => { alive = false; off(); };
  }, [api]);
  useEffect(() => {
    const key = (e) => {
      if (e.key === '/' && document.activeElement !== box.current) { e.preventDefault(); box.current && box.current.focus(); }
    };
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  }, []);
  const q = needle.trim().toLowerCase();
  const has = (...words) => !q || words.join(' ').toLowerCase().includes(q);
  const sections = useMemo(() => {
    if (!data) return [];
    const out = [];
    const big = data.big.filter((b) => has(b.key, b.name, b.about));
    if (big.length) out.push({ title: t('大工具'), glyph: 'codepage', big: true, items: big.map((b) => ({ id: b.key, name: b.name, about: b.about, mark: b.key, open: () => api.openPlugin(b.key, '') })) });
    for (const g of data.groups) {
      const items = g.items.filter((p) => has(p.id, p.name, p.about));
      if (items.length) out.push({ title: g.name, glyph: g.glyph, big: false, items: items.map((p) => ({ ...p, mark: g.glyph, open: () => api.openPlugin('codetools', p.id) })) });
    }
    return out;
  }, [data, q]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!data) return <div className="page"><div className="page-inner"><h1 className="page-title">{t('插件')}</h1></div></div>;
  const total = data.big.length + data.groups.reduce((n, g) => n + g.items.length, 0);
  const shown = sections.reduce((n, s) => n + s.items.length, 0);
  return (
    <div className="page">
      <div className="page-inner wide">
        <header className="page-head">
          <h1 className="page-title">{t('插件')}</h1>
          <span className="count-chip">{q ? `${shown} / ${total}` : total}</span>
        </header>
        <p className="page-sub">{t('Lumen 旁边的每一个工具。点开就能用，聊天里也可以用 @ 叫它们来。')}</p>
        <label className="searchbox">
          <Icon name="search" size={15} />
          <input ref={box} value={needle} onChange={(e) => setNeedle(e.target.value)} placeholder={t('找一个插件')} spellCheck={false}
            onKeyDown={(e) => { if (e.key === 'Escape') setNeedle(''); }} />
          {needle && <button onClick={() => setNeedle('')} aria-label={t('清空')} title={t('清空')}><Icon name="close" size={13} /></button>}
        </label>
        {sections.map((s) => (
          <section key={s.title} className="psection">
            <h3><Glyph svg={data.glyphs[s.glyph]} size={14} stroke={1.4} /><span>{s.title}</span><em>{s.items.length}</em></h3>
            <div className="pgrid">
              {s.items.map((p) => <Card key={p.id} name={p.name} about={p.about} mark={p.mark} big={s.big} glyphs={data.glyphs} onOpen={p.open} />)}
            </div>
          </section>
        ))}
        {!data.done && <p className="loading-line"><span className="spin" />{t('正在列出小插件……')}</p>}
        {data.done && shown === 0 && <p className="empty-page">{q ? t('没有找到。换个词试试。') : t('还没有装插件。')}</p>}
      </div>
    </div>
  );
}
