import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './icons.jsx';
import { t } from './i18n.js';
import { Menu } from './Menu.jsx';

/* The left side: 新聊天, 搜索聊天, 插件; the pinned chats; the projects as a tree, each with its chats; 设置 at the
   bottom; at the top the two small buttons for the browser and the terminal on the right. Put away (Ctrl+B, or the
   panel button), it is a narrow column of the same buttons. The chats' names, pins and what is put away are kept by
   Python (desktop/sidebar.py, chat_tools.py): every change goes there and the list comes back. */

function ChatRow({ c, api, side, current, onOpen, renaming, setRenaming, indent }) {
  const [menu, setMenu] = useState(null);
  const [name, setName] = useState(c.title);
  const input = useRef(null);
  const pinned = side.pins.includes(c.id);
  const editing = renaming === c.id;
  useEffect(() => {
    if (editing) {
      setName(c.title);
      setTimeout(() => input.current && (input.current.focus(), input.current.select()), 0);
    }
  }, [editing, c.title]);
  const done = (save) => {
    if (save && name.trim() !== c.title) api.rename(c.id, name.trim());
    setRenaming(null);
  };
  const open = (e) => {
    e.preventDefault();
    const r = e.currentTarget.closest('.chat-row').getBoundingClientRect();
    setMenu({ x: Math.min(r.right - 8, window.innerWidth - 8), y: e.type === 'contextmenu' ? e.clientY : r.bottom - 2 });
  };
  return (
    <div className={`chat-row${current ? ' on' : ''}${menu ? ' menu-open' : ''}${indent ? ' in' : ''}`} onContextMenu={c.local ? open : undefined}>
      {editing ? (
        <input ref={input} className="rename" value={name} onChange={(e) => setName(e.target.value)} maxLength={120}
          onKeyDown={(e) => { if (e.key === 'Enter') done(true); if (e.key === 'Escape') done(false); }} onBlur={() => done(true)}
          placeholder={t('留空就用回第一句话')} />
      ) : (
        <button className="chat-title" onClick={() => onOpen(c)} title={c.title}>
          <span>{c.title}</span>
        </button>
      )}
      {c.running && !editing && <span className="live-dot" title={t('进行中')} />}
      {c.local && !editing && (
        <button className="row-more" onClick={open} title={t('更多')} aria-label={t('更多')}><Icon name="more" size={16} /></button>
      )}
      {menu && (
        <Menu at={menu} close={() => setMenu(null)} items={[
          { icon: 'pin', label: pinned ? t('取消置顶') : t('置顶'), act: () => api.pin(c.id) },
          { icon: 'edit', label: t('重命名'), act: () => setRenaming(c.id) },
          { icon: 'download', label: t('导出为 Markdown'), act: () => api.exportChat(c.id) },
          null,
          { icon: 'archive', label: t('从列表里收起'), act: () => api.hideChat(c.id), note: t('不会删除，Ctrl+K 里可以放回') },
        ]} />
      )}
    </div>
  );
}

function Folder({ f, api, side, needle, open, toggle, chats, renaming, setRenaming }) {
  const [others, setOthers] = useState(null);
  useEffect(() => {
    if (!f.here && (open || needle) && others === null) api.folderChats(f.config).then(setOthers);
  }, [f, open, needle, others, api]);
  const match = (c) => !needle || c.title.toLowerCase().includes(needle);
  const list = f.here ? chats.filter((c) => !side.pins.includes(c.id) && match(c)) : (others || []).filter(match);
  const expanded = open || !!needle;
  if (needle && !f.here && others !== null && list.length === 0) return null; // searching: only folders with a match
  return (
    <div className={`folder${f.here ? ' here' : ''}`}>
      <div className="folder-row">
        <button className="folder-name" onClick={toggle} title={f.root}>
          <Icon name="chevRight" size={14} className={`twist${expanded ? ' down' : ''}`} />
          <Icon name="folder" size={16} />
          <span>{f.name}</span>
        </button>
        <button className="row-more show-on-hover" title={f.here ? t('在这里开始新聊天') : t('打开这个项目')}
          onClick={() => (f.here ? api.go('home') : api.openProject(f.config, ''))}><Icon name="compose" size={15} /></button>
      </div>
      {expanded && (
        <div className="folder-chats">
          {list.slice(0, 80).map((c) => (
            <ChatRow key={c.id} c={{ ...c, local: f.here }} api={api} side={side} indent current={f.here && side.selected === c.id}
              renaming={renaming} setRenaming={setRenaming}
              onOpen={(x) => (f.here ? api.openTask(x.open) : api.openProject(f.config, x.open))} />
          ))}
          {!f.here && others === null && <p className="empty">{t('正在读取……')}</p>}
          {list.length === 0 && (f.here || others !== null) && <p className="empty">{needle ? t('没有符合的聊天') : t('还没有聊天')}</p>}
        </div>
      )}
    </div>
  );
}

function Search({ api, needle, setNeedle, close }) {
  const input = useRef(null);
  useEffect(() => { input.current && input.current.focus(); }, []);
  return (
    <div className="side-search">
      <Icon name="search" size={15} />
      <input ref={input} value={needle} onChange={(e) => setNeedle(e.target.value)} placeholder={t('搜索聊天')}
        onKeyDown={(e) => { if (e.key === 'Escape') close(); }} spellCheck={false} />
      <button onClick={close} title={t('关闭搜索')} aria-label={t('关闭搜索')}><Icon name="close" size={13} /></button>
    </div>
  );
}

export function Sidebar({ api, side, view, collapsed, setCollapsed, overlay, mark }) {
  const [searching, setSearching] = useState(false);
  const [needle, setNeedle] = useState('');
  const [said, setSaid] = useState([]);
  const [renaming, setRenaming] = useState(null);
  const [open, setOpen] = useState(() => new Set());
  const lower = needle.trim().toLowerCase();
  useEffect(() => {
    if (lower.length < 2) { setSaid([]); return undefined; }
    const timer = setTimeout(() => api.search(needle.trim()).then((r) => setSaid(r || [])), 260);
    return () => clearTimeout(timer);
  }, [lower, needle, api]);
  const here = side.folders.find((f) => f.here);
  const isOpen = (f) => (f.here ? !open.has(f.config) : open.has(f.config)); // this folder starts open, the others closed
  const toggle = (f) => setOpen((s) => { const n = new Set(s); n.has(f.config) ? n.delete(f.config) : n.add(f.config); return n; });
  const pinned = useMemo(() => side.chats.filter((c) => side.pins.includes(c.id) && (!lower || c.title.toLowerCase().includes(lower))),
    [side, lower]);
  const extra = said.filter((s) => !side.chats.some((c) => c.title.toLowerCase().includes(lower) && (c.open === s.task || c.id === s.task)));
  const page = view.page === 'native' ? view.key : view.page;
  const go = (key) => { api.go(key); if (overlay) setCollapsed(true); };
  const closeSearch = () => { setSearching(false); setNeedle(''); };
  const keyTip = side.keys_missing.length ? t('{0} 还没有 API 密钥', side.keys_missing.join('、')) : t('设置');

  if (collapsed) {
    return (
      <nav className="rail">
        <button className="rail-btn" onClick={() => setCollapsed(false)} title={t('显示聊天列表') + ' · Ctrl+B'}><Icon name="panel" size={18} /></button>
        <span className="rail-gap" />
        <button className={`rail-btn${page === 'home' ? ' on' : ''}`} onClick={() => go('home')} title={t('新聊天') + ' · Ctrl+N'}><Icon name="compose" size={18} /></button>
        <button className="rail-btn" onClick={() => { setCollapsed(false); setSearching(true); }} title={t('搜索聊天')}><Icon name="search" size={18} /></button>
        <button className={`rail-btn${page === 'plugins' ? ' on' : ''}`} onClick={() => go('plugins')} title={t('插件')}><Icon name="grid" size={18} /></button>
        <span className="rail-gap" />
        <button className={`rail-btn${side.docks.includes('browser') ? ' on' : ''}`} onClick={() => api.go('browser')} title={t('浏览器') + ' · Ctrl+Shift+B'}><Icon name="globe" size={18} /></button>
        <button className={`rail-btn${side.docks.includes('terminal') ? ' on' : ''}`} onClick={() => api.go('terminal')} title={t('终端') + ' · Ctrl+J'}><Icon name="terminal" size={18} /></button>
        <span className="grow" />
        <button className={`rail-btn${page === 'settings' ? ' on' : ''}`} onClick={() => go('settings')} title={keyTip}>
          <Icon name="gear" size={18} />{side.keys_missing.length > 0 && <i className="alert-dot" />}
        </button>
      </nav>
    );
  }

  return (
    <nav className={`side${overlay ? ' overlay' : ''}`}>
      <div className="side-top">
        <div className="brand">{mark ? <img src={mark} alt="" /> : <span className="brand-mark" aria-hidden="true" />}<b>Lumen</b></div>
        <span className="grow" />
        <button className={`mini${side.docks.includes('browser') ? ' on' : ''}`} onClick={() => api.go('browser')} title={t('浏览器') + ' · Ctrl+Shift+B'}
          aria-label={t('浏览器')}><Icon name="globe" size={16} /></button>
        <button className={`mini${side.docks.includes('terminal') ? ' on' : ''}`} onClick={() => api.go('terminal')} title={t('终端') + ' · Ctrl+J'}
          aria-label={t('终端')}><Icon name="terminal" size={16} /></button>
        <button className="mini" onClick={() => setCollapsed(true)} title={t('收起聊天列表') + ' · Ctrl+B'} aria-label={t('收起聊天列表')}><Icon name="panel" size={16} /></button>
      </div>

      <div className="side-nav">
        <button className={`nav${page === 'home' ? ' on' : ''}`} onClick={() => go('home')}>
          <Icon name="compose" /><span>{t('新聊天')}</span><kbd>Ctrl N</kbd>
        </button>
        {searching ? <Search api={api} needle={needle} setNeedle={setNeedle} close={closeSearch} /> : (
          <button className="nav" onClick={() => setSearching(true)}><Icon name="search" /><span>{t('搜索聊天')}</span><kbd>Ctrl K</kbd></button>
        )}
        <button className={`nav${page === 'plugins' ? ' on' : ''}`} onClick={() => go('plugins')}><Icon name="grid" /><span>{t('插件')}</span></button>
      </div>

      <div className="side-list">
        {pinned.length > 0 && (
          <section>
            <h4>{t('置顶')}</h4>
            {pinned.map((c) => (
              <ChatRow key={c.id} c={{ ...c, local: true }} api={api} side={side} current={side.selected === c.id} renaming={renaming} setRenaming={setRenaming}
                onOpen={(x) => { api.openTask(x.open); if (overlay) setCollapsed(true); }} />
            ))}
          </section>
        )}
        <section>
          <h4 className="with-btn">{t('项目')}
            <button onClick={() => api.openFolder()} title={t('新建项目或打开文件夹')} aria-label={t('新建项目或打开文件夹')}><Icon name="folderPlus" size={15} /></button>
          </h4>
          {side.folders.map((f) => (
            <Folder key={f.config || f.name} f={f} api={api} side={side} needle={lower} open={isOpen(f)} toggle={() => toggle(f)}
              chats={side.chats} renaming={renaming} setRenaming={setRenaming} />
          ))}
        </section>
        {lower.length >= 2 && extra.length > 0 && (
          <section>
            <h4>{t('聊天内容里提到')}</h4>
            {extra.map((s) => (
              <button key={s.task} className="said" onClick={() => api.openTask(s.task)} title={s.title}>
                <b>{s.title}</b><span>{s.snippet}</span>
              </button>
            ))}
          </section>
        )}
        {!here && <p className="empty">{t('还没有聊天')}</p>}
      </div>

      <div className="side-foot">
        <button className={`nav${page === 'settings' ? ' on' : ''}`} onClick={() => go('settings')} title={keyTip}>
          <span className="gear"><Icon name="gear" />{side.keys_missing.length > 0 && <i className="alert-dot" />}</span>
          <span>{t('设置')}</span>
          {side.keys_missing.length > 0 && <em className="warn-note">{t('缺少密钥')}</em>}
          <kbd>Ctrl ,</kbd>
        </button>
      </div>
    </nav>
  );
}
