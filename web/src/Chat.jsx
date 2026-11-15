import { useContext, useEffect, useRef, useState } from 'react';
import { Composer } from './Composer.jsx';
import { Markdown } from './Markdown.jsx';
import { Icon } from './icons.jsx';
import { Menu } from './Menu.jsx';
import { Slot } from './Slot.jsx';
import { chinese, t } from './i18n.js';
import { Details } from './Details.jsx';
import { Prefs } from './prefs.js';

const STEP_ICON = { tool: 'tool', thought: 'think', test: 'test', error: 'warn', note: 'info' };

function Avatar({ src, colour, name, size = 30 }) {
  return src ? <img className="avatar" src={src} width={size} height={size} alt="" />
    : <span className="avatar letter" style={{ width: size, height: size, background: colour || 'var(--ink)' }}>{(name || 'L')[0]}</span>;
}

function clock(at) {
  if (!at) return '';
  const d = new Date(String(at).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return '';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function Steps({ steps, running, elapsed, open: initial }) {
  const [open, setOpen] = useState(initial);
  useEffect(() => { if (running && initial) setOpen(true); }, [running, initial]);
  if (!steps.length && !running) return null;
  const tools = steps.filter((s) => s.kind === 'tool').length;
  const head = [running ? t('正在工作') : t('已完成'), tools ? t('{0} 步', tools) : '', elapsed || ''].filter(Boolean).join(' · ');
  return (
    <div className={`steps${open ? ' open' : ''}`}>
      <button className="steps-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        {running ? <span className="spin" /> : <Icon name="check" size={14} className="ok" />}
        <span>{head}</span>
        <Icon name="chev" size={13} className="chev" />
      </button>
      <div className="steps-body">
        <div>
          <ol>
            {steps.map((s, i) => (
              <li key={i} className={`k-${s.kind}${s.ok === false ? ' bad' : ''}`}>
                <Icon name={STEP_ICON[s.kind] || 'tool'} size={14} />
                <span>{s.text}</span>
                {s.kind === 'tool' && s.ok === false && <em>{t('没成')}</em>}
              </li>
            ))}
            {running && <li className="k-now"><span className="dots"><i /><i /><i /></span><span>{t('正在想下一步')}</span></li>}
          </ol>
        </div>
      </div>
    </div>
  );
}

function Member({ m, api }) {
  const running = m.state !== 'finished';
  return (
    <div className="member">
      {!m.review && <div className="ask"><b>{m.from} → {m.name}</b><p>{m.ask}</p></div>}
      <div className="member-head">
        <Avatar src={m.avatar} colour={m.colour} name={m.name} size={26} />
        <b>{m.name}</b><span className="cn">{chinese() ? `${t(m.cn)} · ` : ''}{m.review ? t('自动复查') : m.job}</span>
        <span className={`state ${running ? 'live' : m.outcome === 'done' ? 'done' : 'other'}`}>{m.status}</span>
      </div>
      <div className="member-body">
        <Steps steps={m.steps} running={running} open={false} />
        {m.answer && <Markdown text={m.answer} api={api} />}
      </div>
    </div>
  );
}

function Turn({ t: turn, api, last, chat, opened }) {
  const prefs = useContext(Prefs);
  const running = turn.state !== 'finished';
  const [copied, setCopied] = useState(false);
  const [details, setDetails] = useState(opened);
  const [kept, setKept] = useState('');
  const [sendErr, setSendErr] = useState('');
  // 省略: a finished turn with a long process can be folded to its answer; what the user chose is kept for this turn for good
  const process = !turn.chat && (turn.steps.length > 0 || turn.members.length > 0);
  const long = turn.steps.length >= 8 || turn.members.length >= 2;
  const [choice, setChoice] = useState(turn.fold === undefined ? null : turn.fold);
  const folded = !running && process && (choice !== null ? choice : prefs.auto_fold !== false && long);
  const fold = () => { setChoice(!folded); api.foldTurn(turn.id, !folded); };
  const again = async (text) => { // not sent: say why, never nothing
    const r = await api.send('chat', text);
    setSendErr(r && r.ok === false ? (r.why || t('没有发出去。')) : '');
  };
  useEffect(() => { if (opened) setDetails(true); }, [opened]);
  const remember = async () => {
    const r = await api.remember(turn.id, turn.answer);
    setKept(r.ok ? 'ok' : r.error || 'bad');
  };
  const putBack = () => window.dispatchEvent(new CustomEvent('lumen:put', { detail: turn.question })); // 改一改再问: into the box
  return (
    <section className="turn">
      <div className="q">
        <div className="bubble">{turn.question}</div>
        {prefs.show_times && clock(turn.at) && <time>{clock(turn.at)}</time>}
      </div>
      <div className="a">
        <div className="who"><Avatar src={chat.lumen} name="Lumen" size={24} /><b>Lumen</b><span>{turn.who}</span>
          {!running && process && <button className="fold-btn" onClick={fold}>{folded ? t('展开过程') : t('省略')}</button>}
          {running && prefs.spend_limit > 0 && (
            <em className={`spend${turn.tokens > prefs.spend_limit * 0.8 ? ' near' : ''}`} title={t('这个问题所有 AI 用掉的新 token（缓存重读不算），到上限会停下来问你')}>
              {t('已用 {0} / 上限 {1}', turn.tokens.toLocaleString(), prefs.spend_limit.toLocaleString())}</em>
          )}
        </div>
        {!turn.chat && !folded && <Steps steps={turn.steps} running={running} elapsed={turn.elapsed} open={running && prefs.expand_steps !== false} />}
        {turn.members.length > 0 && !folded && <div className="team">{turn.members.map((m) => <Member key={m.id} m={m} api={api} />)}</div>}
        {turn.needs.length > 0 && <div className="need"><Icon name="warn" size={14} />{t('需要你处理：')}{turn.needs.join('、')}</div>}
        {turn.over && (
          <div className="need over">
            <Icon name="stop" size={14} />
            <span>{t('这个问题已经用了 {0} 个新 token，到了你设的上限 {1}，所以停下了。', turn.over.tokens.toLocaleString(), turn.over.limit.toLocaleString())}</span>
            <span className="grow" />
            {last && <button className="btn small" onClick={() => again(t('接着做，从停下的地方继续。'))}>{t('接着做')}</button>}
            <button className="btn small ghost" onClick={() => api.go('usage')}>{t('改上限')}</button>
          </div>
        )}
        {turn.answer ? <Markdown text={turn.answer} api={api} /> : running ? <div className="thinking"><span className="shimmer">{t('正在思考')}</span></div>
          : <p className="faint">{turn.status}</p>}
        {turn.answer && (
          <div className="answer-tools">
            <button onClick={() => { api.copy(turn.answer); setCopied(true); setTimeout(() => setCopied(false), 1400); }}>
              <Icon name={copied ? 'check' : 'copy'} size={14} />{copied ? t('已复制') : t('复制')}
            </button>
            <button onClick={remember} disabled={kept === 'ok'} title={kept && kept !== 'ok' ? kept : t('存进这个项目的长期记忆，以后的 AI 都会看到')}>
              <Icon name={kept === 'ok' ? 'check' : 'think'} size={14} />{kept === 'ok' ? t('已记住') : kept ? t('没有记住') : t('记住')}
            </button>
            {!turn.chat && <button className={details ? 'on' : ''} onClick={() => setDetails(!details)} title={t('结论、改动清单和完整记录')}>
              <Icon name="expand" size={14} />{t('详细')}</button>}
            {last && <button onClick={() => again(turn.question)} title={t('同一个问题再问一次')}><Icon name="redo" size={14} />{t('再答一次')}</button>}
            {last && <button onClick={putBack} title={t('把问题放回输入框，改一改再发')}><Icon name="edit" size={14} />{t('改一改再问')}</button>}
            {last && chat.resumable && <button onClick={() => api.resume()}><Icon name="redo" size={14} />{t('继续执行')}</button>}
            {sendErr && <span className="meta bad-text">{sendErr}</span>}
            <span className="meta">{turn.status}{prefs.show_tokens && turn.tokens ? ` · token ${turn.tokens.toLocaleString()}` : ''}</span>
          </div>
        )}
        {details && !turn.chat && <Details api={api} taskId={turn.id} running={running} />}
      </div>
    </section>
  );
}

/* An @ tool's own window on the right, half the screen (2026-11-13): its tabs when two are asked for, the row asking to let it
   work in this project, a word while it starts or why it did not; under them the room its own window is laid in (a real
   program, web_chat.WebChat.place); a wide bar on its left edge to make it wider or narrower (remembered); x puts it away. */
export function ToolPane({ api, tool, share, setShare }) {
  const pane = useRef(null);
  if (!tool.on) return null;
  const tools = tool.tools || [];
  const drag = (e) => {
    e.preventDefault();
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const whole = pane.current.parentElement.getBoundingClientRect();
    const mine = pane.current.getBoundingClientRect();
    const main = pane.current.previousElementSibling; // the chat beside it keeps 360px, the tool keeps 420px
    const most = mine.width + (main ? main.getBoundingClientRect().width : 0) - 360;
    document.body.classList.add('dragging-x');
    const move = (ev) => {
      const w = Math.max(420, Math.min(most, whole.right - ev.clientX));
      setShare(Math.round((w / whole.width) * 1000) / 1000);
    };
    const up = () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointercancel', up);
      el.removeEventListener('lostpointercapture', up);
      document.body.classList.remove('dragging-x');
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    el.addEventListener('lostpointercapture', up);
  };
  return (
    <aside className="tool-pane" ref={pane} style={{ width: `${share * 100}%` }}>
      <div className="tool-handle" onPointerDown={drag} title={t('拖动来调整大小')}><i /></div>
      <div className="tool-area">
        <header className="tool-bar">
          {tools.length > 1 ? (
            <div className="tool-tabs">
              {tools.map((x) => (
                <button key={x.key} className={x.key === tool.current ? 'on' : ''} onClick={() => api.pickTool(x.key)}>{x.name}</button>
              ))}
            </div>
          ) : (
            <><span className="tool-mark">{tool.name.slice(4, 5) || tool.name[0]}</span><b>{tool.name}</b></>
          )}
          {tool.state === 'starting' && <span className="tool-state"><span className="spin" />{t('正在打开……')}</span>}
          <button className="tool-close" onClick={() => api.closeTool()} title={t('关闭')} aria-label={t('关闭')}><Icon name="close" size={14} /></button>
        </header>
        <Slot api={api} name="tool" className="tool-slot">
          {tool.state !== 'ready' && (
            <div className={`tool-wait${tool.state === 'failed' ? ' failed' : ''}`}>
              {tool.state === 'failed' ? <><Icon name="warn" size={16} /><span>{tool.why}</span></> : <><span className="spin" /><span>{t('正在打开 {0}……', tool.name)}</span></>}
            </div>
          )}
        </Slot>
      </div>
    </aside>
  );
}

export function Home({ api, home, setBox }) {
  const warn = home.warnings || [];
  return (
    <div className="home">
      <div className="home-body">
        <div className="hello">
          {home.lumen ? <img className="hello-mark" src={home.lumen} alt="" /> : <span className="hello-mark letter">L</span>}
          <h1>{t('今天想做点什么？')}</h1>
        </div>
        {warn.map((w, i) => (
          <div key={w.text} className="warning">
            <Icon name="warn" size={15} /><span>{w.text}</span>
            {w.act && <button onClick={() => api.warningAction(i)}>{w.act}</button>}
          </div>
        ))}
        <Composer where="home" box={home.box} setBox={setBox} api={api} tools={home.tools} autoFocus draft={home.draft} keepDraft />
        <p className="foot">{t('Lumen 在这台电脑上工作。回答可能出错，重要的事请核对。')}</p>
      </div>
    </div>
  );
}

function FindBar({ api, close }) {
  const [text, setText] = useState('');
  const [found, setFound] = useState(null);
  const input = useRef(null);
  useEffect(() => { input.current && input.current.focus(); }, []);
  useEffect(() => api.on('found', setFound), [api]);
  useEffect(() => {
    const timer = setTimeout(() => api.find(text, false), 120);
    return () => clearTimeout(timer);
  }, [text, api]);
  const shut = () => { api.find('', false); close(); };
  return (
    <div className="findbar">
      <Icon name="search" size={14} />
      <input ref={input} value={text} onChange={(e) => setText(e.target.value)} placeholder={t('在这个聊天里查找')} spellCheck={false}
        onKeyDown={(e) => { if (e.key === 'Enter') api.find(text, e.shiftKey); if (e.key === 'Escape') shut(); }} />
      <span className="count">{text && found ? (found.count ? `${found.at}/${found.count}` : t('没有')) : ''}</span>
      <button onClick={() => api.find(text, true)} disabled={!text} title={t('上一个')} aria-label={t('上一个')}><Icon name="up" size={14} /></button>
      <button onClick={() => api.find(text, false)} disabled={!text} title={t('下一个')} aria-label={t('下一个')}><Icon name="chev" size={14} /></button>
      <button onClick={shut} title={t('关闭')} aria-label={t('关闭')}><Icon name="close" size={13} /></button>
    </div>
  );
}

function ChatHead({ api, chat, side, finding, setFinding }) {
  const prefs = useContext(Prefs);
  const [menu, setMenu] = useState(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(chat.title);
  const pinned = side && side.pins.includes(chat.chat_id);
  const tokens = chat.turns.reduce((n, x) => n + (x.tokens || 0), 0);
  const save = () => {
    setEditing(false);
    if (name.trim() !== chat.title) api.rename(chat.chat_id, name.trim());
  };
  return (
    <header className="chat-head">
      {editing ? (
        <input className="title-edit" autoFocus value={name} onChange={(e) => setName(e.target.value)} onBlur={save} maxLength={120}
          onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setEditing(false); setName(chat.title); } }} />
      ) : (
        <h2 title={t('点一下重命名')} onClick={() => { setName(chat.title); setEditing(true); }}>{chat.title}</h2>
      )}
      <span className={`state ${chat.running ? 'live' : 'done'}`}>{chat.running ? t('进行中') : t('完成')}</span>
      {prefs.show_tokens && tokens > 0 && <span className="tokens">token {tokens.toLocaleString()}</span>}
      <span className="grow" />
      {finding ? <FindBar api={api} close={() => setFinding(false)} /> : (
        <button className="head-btn" onClick={() => setFinding(true)} title={t('在这个聊天里查找') + ' · Ctrl+F'} aria-label={t('查找')}><Icon name="search" /></button>
      )}
      <button className="head-btn" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMenu({ x: r.right, y: r.bottom }); }}
        title={t('更多')} aria-label={t('更多')}><Icon name="more" /></button>
      {menu && (
        <Menu at={menu} close={() => setMenu(null)} items={[
          { icon: 'pin', label: pinned ? t('取消置顶') : t('置顶'), act: () => api.pin(chat.chat_id) },
          { icon: 'edit', label: t('重命名'), act: () => { setName(chat.title); setEditing(true); } },
          { icon: 'download', label: t('导出为 Markdown'), act: () => api.exportChat(chat.chat_id) },
          { icon: 'expand', label: t('详细'), act: () => api.details(chat.task_id), note: t('结论、改动清单和完整记录') },
        ]} />
      )}
    </header>
  );
}

export function Chat({ api, chat, setBox, tools, side, command, view }) {
  const end = useRef(null);
  const scroller = useRef(null);
  const [stuck, setStuck] = useState(true);
  const [finding, setFinding] = useState(false);
  useEffect(() => { if (stuck && end.current) end.current.scrollIntoView({ block: 'end' }); }, [chat, stuck]);
  useEffect(() => { if (command && command.do === 'find') setFinding(true); }, [command]);
  const scroll = () => {
    const el = scroller.current;
    if (el) setStuck(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  };
  if (chat.error) return <div className="chat"><p className="faint pad">{chat.error}</p></div>;
  if (chat.missing) return <div className="chat"><p className="faint pad">{t('这个聊天已经不在了。')}</p></div>;
  return (
    <div className="chat">
      <ChatHead key={chat.chat_id} api={api} chat={chat} side={side} finding={finding} setFinding={setFinding} />
      <div className="stream" ref={scroller} onScroll={scroll}>
        <div className="column">
          {chat.turns.map((x, i) => <Turn key={x.id} t={x} api={api} chat={chat} last={i === chat.turns.length - 1} opened={!!view && view.details === x.id} />)}
          <div ref={end} />
        </div>
      </div>
      {!stuck && <button className="to-end" onClick={() => setStuck(true)} title={t('回到最新')} aria-label={t('回到最新')}><Icon name="chev" /></button>}
      <div className="dock">
        <Composer key={chat.chat_id} where="chat" box={chat.box} setBox={setBox} api={api} tools={tools} placeholder={t('接着说……')} />
      </div>
    </div>
  );
}
