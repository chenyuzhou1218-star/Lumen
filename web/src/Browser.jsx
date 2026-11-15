import { useEffect, useRef, useState } from 'react';
import { Icon } from './icons.jsx';
import { Markdown } from './Markdown.jsx';
import { Menu } from './Menu.jsx';
import { Slot } from './Slot.jsx';
import { t } from './i18n.js';

/* The browser on the right: tabs (when there is more than one), the address bar, the start page of an empty tab and
   what Ray found, all drawn here in the window's light or dark; the web pages themselves are Chromium, lying over the
   room left for them (desktop/browser.py keeps the tabs, the pages, Ray's tab and the bookmarks). */

function Tabs({ api, b }) {
  if (b.tabs.length < 2) return null;
  return (
    <div className="b-tabs" role="tablist">
      {b.tabs.map((tab, i) => (
        <div key={i} role="tab" aria-selected={i === b.current} className={`b-tab${i === b.current ? ' on' : ''}${tab.agent ? ' agent' : ''}`}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); api.browserClose(i); } }} title={tab.url || tab.title}>
          <button className="b-tab-title" onClick={() => api.browserTab(i)}>{tab.agent && <i className="live-dot" />}<span>{tab.title}</span></button>
          <button className="b-tab-x" onClick={() => api.browserClose(i)} aria-label={t('关闭标签页')} title={t('关闭标签页')}><Icon name="close" size={11} /></button>
        </div>
      ))}
      <button className="b-btn" onClick={() => api.browserAct('new')} title={t('新标签页')} aria-label={t('新标签页')}><Icon name="plus" size={14} /></button>
    </div>
  );
}

function Address({ api, b }) {
  const [text, setText] = useState(b.url);
  const [editing, setEditing] = useState(false);
  const [marks, setMarks] = useState(null);
  const input = useRef(null);
  useEffect(() => { if (!editing) setText(b.url); }, [b.url, editing]);
  const go = () => { if (text.trim()) { api.browserGo(text.trim()); input.current.blur(); } };
  const openMarks = async (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const list = await api.browserMarks();
    setMarks({ x: r.right, y: r.bottom, list });
  };
  return (
    <div className="b-bar">
      <button className="b-btn" disabled={!b.back} onClick={() => api.browserAct('back')} title={t('后退')} aria-label={t('后退')}><Icon name="back" size={15} /></button>
      <button className="b-btn" disabled={!b.forward} onClick={() => api.browserAct('forward')} title={t('前进')} aria-label={t('前进')}><Icon name="back" size={15} className="flip" /></button>
      <button className="b-btn" disabled={b.blank} onClick={() => api.browserAct(b.loading ? 'stop' : 'reload')} title={b.loading ? t('停止') : t('刷新')} aria-label={t('刷新')}>
        <Icon name={b.loading ? 'close' : 'redo'} size={14} />
      </button>
      <label className={`b-address${b.loading ? ' loading' : ''}`}>
        {b.url.startsWith('https://') ? <Icon name="lock" size={12} /> : <Icon name="globe" size={13} />}
        <input ref={input} value={text} placeholder={t('输入网址，或者要搜索的内容')} spellCheck={false}
          onChange={(e) => setText(e.target.value)} onFocus={(e) => { setEditing(true); e.target.select(); }} onBlur={() => setEditing(false)}
          onKeyDown={(e) => { if (e.key === 'Enter') go(); if (e.key === 'Escape') { setText(b.url); e.currentTarget.blur(); } }} />
      </label>
      <button className="b-btn" disabled={b.blank} onClick={() => api.browserAct('to_chat')} title={t('把这一页发给 Lumen')} aria-label={t('把这一页发给 Lumen')}><Icon name="send" size={14} /></button>
      <button className={`b-btn${b.starred ? ' on' : ''}`} disabled={b.blank} onClick={() => api.browserAct('star')} title={b.starred ? t('取消收藏') : t('收藏这一页')}
        aria-label={t('收藏这一页')}><Icon name={b.starred ? 'starOn' : 'star'} size={15} /></button>
      <button className="b-btn" onClick={openMarks} title={t('收藏夹')} aria-label={t('收藏夹')}><Icon name="bookmarks" size={15} /></button>
      {b.tabs.length < 2 && <button className="b-btn" onClick={() => api.browserAct('new')} title={t('新标签页')} aria-label={t('新标签页')}><Icon name="plus" size={14} /></button>}
      {marks && (
        <Menu at={marks} close={() => setMarks(null)} items={marks.list.length
          ? marks.list.map((m) => ({ icon: 'globe', label: m.title || m.url, note: m.url, act: () => api.browserGo(m.url) }))
          : [{ label: t('还没有收藏：点地址栏旁边的星星'), act: () => {} }]} />
      )}
    </div>
  );
}

function StartPage({ api }) {
  const [text, setText] = useState('');
  const input = useRef(null);
  useEffect(() => { if (input.current) input.current.focus(); }, []);
  return (
    <div className="b-start">
      <h2>{t('Lumen 浏览器')}</h2>
      <label className="b-search">
        <Icon name="search" size={17} />
        <input ref={input} value={text} onChange={(e) => setText(e.target.value)} placeholder={t('搜索，或者输入网址')} spellCheck={false}
          onKeyDown={(e) => { if (e.key === 'Enter' && text.trim()) { api.browserGo(text.trim()); setText(''); } }} />
      </label>
    </div>
  );
}

function Ray({ api, ray }) {
  if (!ray || !ray.task) return null;
  return (
    <section className="b-ray">
      <header>
        <span className={`b-ray-dot${ray.done ? ' done' : ''}`} /><b>{ray.state}</b><span className="grow" />
        <button className="b-btn" onClick={() => api.browserAct('ray_chat')} title={t('在聊天里查看')} aria-label={t('在聊天里查看')}><Icon name="expand" size={14} /></button>
        <button className="b-btn" onClick={() => api.browserAct('ray_close')} title={t('关闭')} aria-label={t('关闭')}><Icon name="close" size={12} /></button>
      </header>
      {ray.answer && <div className="b-ray-answer"><Markdown text={ray.answer} api={api} /></div>}
    </section>
  );
}

export function Browser({ api, style }) {
  const [b, setB] = useState(null);
  useEffect(() => {
    let alive = true;
    api.browserState().then((s) => alive && setB(s));
    const off = api.on('browser', (s) => alive && setB(s));
    return () => { alive = false; off(); };
  }, [api]);
  if (!b) return <div className="b-frame" style={style}><div className="page-wait"><span className="spin" /></div></div>;
  return (
    <div className="b-frame" style={style}>
      <Tabs api={api} b={b} />
      <Address api={api} b={b} />
      {b.blank ? <StartPage api={api} /> : <Slot api={api} name="browser" className="browser-slot"><div className="page-wait"><span className="spin" /></div></Slot>}
      <Ray api={api} ray={b.ray} />
    </div>
  );
}
