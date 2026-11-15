import { useContext, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Icon } from './icons.jsx';
import { language, t } from './i18n.js';
import { Prefs } from './prefs.js';
import { ThinkSlider } from './ThinkSlider.jsx';
import { Ask } from './Controls.jsx';
import { Asks, ApproveBar, AskPanel } from './Questions.jsx';

const APPROVALS = [ // 批准方式, kept for each chat
  ['ask', '全部问我', '除了聊天，其余所有动作都先问你：改文件、运行命令、鼠标和键盘、删文件。'],
  ['auto', '帮我审查', '只有删文件，和用电脑操作控制鼠标键盘时才问你，其余直接做。'],
  ['full', '完全放开', '不用批准，全部自动做。'],
];

function useOutside(ref, open, close) {
  useEffect(() => {
    if (!open) return undefined;
    const down = (e) => { if (ref.current && !ref.current.parentElement.contains(e.target)) close(); };
    const key = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('mousedown', down);
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key); };
  }, [open, ref, close]);
}

/* A menu above its button. It never reaches into an @ tool's window above the chat (that window lies over the page
   and would hide it): it gets the height there is, and scrolls. */
function Pop({ open, close, children, className = '' }) {
  const ref = useRef(null);
  const [room, setRoom] = useState(null);
  useOutside(ref, open, close);
  useLayoutEffect(() => {
    if (!open || !ref.current) return;
    const anchor = ref.current.parentElement.getBoundingClientRect();
    const slot = document.querySelector('.tool-slot');
    const ceiling = slot ? slot.getBoundingClientRect().bottom : 0;
    setRoom(Math.max(160, anchor.top - ceiling - 16));
  }, [open]);
  if (!open) return null;
  return <div className={`pop ${className}`} ref={ref} style={room ? { maxHeight: room } : undefined}>{children}</div>;
}

/* The message box: the words, the @ tools and files going with them, and along the bottom the choices that go with
   the message (files, tools, computer use, model and level) and send. Enter sends (or Ctrl+Enter, as set in 外观);
   Shift+Enter, or Enter while an input method is composing, does not. */
export function Composer({ where, box, setBox, api, tools, placeholder, onSent, autoFocus, draft, keepDraft }) {
  const prefs = useContext(Prefs);
  const asks = useContext(Asks);
  const [text, setText] = useState(draft || '');
  const [menu, setMenu] = useState(null); // 'tools' | 'model' | 'approval'
  const [voice, setVoice] = useState(null); // null | {since} | 'writing'
  const [tick, setTick] = useState(0);
  const [why, setWhy] = useState('');
  const [ask, setAsk] = useState(null); // 这类问题以往要花的比上限多: asked before it goes
  const area = useRef(null);
  const frame = useRef(null);
  const [narrow, setNarrow] = useState(false);
  const running = box && box.running;

  useEffect(() => { if (draft) setText((now) => now || draft); }, [draft]);
  useEffect(() => { if (autoFocus && area.current) area.current.focus(); }, [autoFocus]);
  const fit = () => {
    const el = area.current;
    if (!el) return;
    el.style.height = '';
    if (el.value) el.style.height = `${Math.min(el.scrollHeight, 260)}px`;
  };
  useEffect(fit, [text]);
  useEffect(() => {
    const el = frame.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(() => { setNarrow(el.clientWidth < 520); fit(); });
    ro.observe(el);
    return () => ro.disconnect();
  }, [!!box]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!keepDraft) return undefined;
    const timer = setTimeout(() => api.keepDraft(text), 400);
    return () => clearTimeout(timer);
  }, [text, keepDraft, api]);
  useEffect(() => {
    if (!voice || voice === 'writing') return undefined;
    const timer = setInterval(() => setTick((n) => n + 1), 200);
    return () => clearInterval(timer);
  }, [voice]);
  useEffect(() => {
    const offHeard = api.on('heard', (r) => {
      setVoice(null);
      if (r.text) setText((x) => (x ? `${x} ${r.text}` : r.text));
      if (r.error) setWhy(t('没有听写成：') + r.error);
      if (area.current) area.current.focus();
    });
    const offPut = api.on('put', (r) => { // from the browser or the terminal: into the box, nothing sent
      setText((x) => (x.trim() ? `${x}\n\n${r.text}` : r.text));
      if (area.current) area.current.focus();
    });
    const local = (e) => { setText(e.detail || ''); if (area.current) area.current.focus(); }; // 改一改再问 under an answer
    if (where === 'chat') window.addEventListener('lumen:put', local);
    return () => { offHeard(); offPut(); window.removeEventListener('lumen:put', local); };
  }, [api]);

  if (!box) return null;
  const close = () => setMenu(null);
  const send = async (checked) => {
    const words = text.trim();
    if (!words || voice) return;
    if (checked !== true) { // before it goes: what questions like it used here before, against the user's limit
      const est = await api.estimate(where);
      if (est && est.limit && est.typical > est.limit) {
        setAsk({ title: t('这类问题以往花得比上限多'), text: t('这个项目里同类问题以往大约用 {0} 个新 token（{1} 次的中位数），你设的上限是 {2}。照样发出去，用到上限会停下来问你；也可以先去设置里改上限。',
          est.typical.toLocaleString(), est.count, est.limit.toLocaleString()),
          buttons: [{ label: t('先不发') }, { label: t('照样发'), primary: true, act: () => send(true) }] });
        return;
      }
    }
    setText('');
    setWhy('');
    const r = await api.send(where, words);
    if (r && r.ok === false) { // not sent: the words come back, and why
      setText((now) => now || words);
      if (r.box) setBox(r.box);
      if (r.why) setWhy(r.why);
      return;
    }
    if (onSent) onSent(words);
  };
  const ctrlEnter = prefs.send_key === 'ctrl_enter';
  const key = (e) => {
    if (e.key !== 'Enter' || e.nativeEvent.isComposing) return;
    if (ctrlEnter ? e.ctrlKey : !e.shiftKey && !e.ctrlKey) {
      e.preventDefault();
      send();
    }
  };
  const change = (e) => {
    const v = e.target.value;
    if (v.endsWith('@') && !text.endsWith('@') && tools.length) setMenu('tools');
    setText(v);
  };
  const pickTool = async (k) => {
    if (text.endsWith('@')) setText(text.slice(0, -1));
    setBox(await api.mention(where, k, true));
    close();
    if (area.current) area.current.focus();
  };
  const startVoice = async () => {
    if (await api.voiceStart()) { setVoice({ since: Date.now() }); setTick(0); } else setWhy(t('这台电脑上还不能语音输入。'));
  };
  const level = (box.levels.find((l) => l.key === box.level) || {}).name;
  const groups = [...new Set(box.models.map((m) => m.group))];
  const secs = voice && voice.since ? Math.floor((Date.now() - voice.since) / 1000) : 0;
  const approval = APPROVALS.find((a) => a[0] === box.approval) || APPROVALS[0];

  return (
    <div ref={frame} className={`composer${running ? ' busy' : ''}`}>
      {asks.questions.length > 0 && <AskPanel key={asks.questions[0].id} q={asks.questions[0]} api={api} />}
      {(box.mentions.length > 0 || box.files.length > 0) && (
        <div className="chips">
          {box.mentions.map((m) => (
            <button key={m.key} className="chip tool" onClick={async () => setBox(await api.mention(where, m.key, false))} title={t('不用它了')}>
              <span>@ {m.name}</span><Icon name="close" size={12} />
            </button>
          ))}
          {box.files.map((f, i) => (
            <button key={f + i} className="chip" onClick={async () => setBox(await api.dropFile(where, i))} title={t('拿掉这个文件')}>
              <Icon name="file" size={13} /><span>{f}</span><Icon name="close" size={12} />
            </button>
          ))}
        </div>
      )}
      {voice ? (
        <div className="voice">
          <span className="rec" />
          <div className="wave">{Array.from({ length: 28 }, (_, i) => <i key={i} style={{ height: `${voice === 'writing' ? 4 : 6 + Math.abs(Math.sin((i + tick) * 0.9)) * 18}px` }} />)}</div>
          <span className="secs">{voice === 'writing' ? t('正在写成文字…') : `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`}</span>
          <button className="ghost" onClick={() => { api.voiceCancel(); setVoice(null); }} disabled={voice === 'writing'}>{t('取消')}</button>
          <button className="dark" onClick={() => { setVoice('writing'); api.voiceStop(language()); }} disabled={voice === 'writing'}>{t('完成')}</button>
        </div>
      ) : (
        <textarea ref={area} rows={1} value={text} onChange={change} onKeyDown={key}
          placeholder={placeholder || (narrow ? t('交给 Lumen……') : t('交给 Lumen：写代码、查问题、剪视频、上网查……'))} spellCheck={false} />
      )}
      {why && <div className="why">{why}</div>}
      <div className="row">
        <button className="icon" title={t('加文件')} aria-label={t('加文件')} onClick={async () => setBox(await api.pickFiles(where))}><Icon name="plus" /></button>
        {tools.length > 0 && (
          <div className="anchor">
            <button className={`icon${menu === 'tools' ? ' on' : ''}`} title={t('叫一个工具来（@）')} aria-label={t('叫一个工具来（@）')}
              onClick={() => setMenu(menu === 'tools' ? null : 'tools')}><Icon name="at" /></button>
            <Pop open={menu === 'tools'} close={close} className="up left">
              <div className="pop-head">{t('叫一个工具来')}</div>
              {tools.map((x) => (
                <button key={x.key} className="item" onClick={() => pickTool(x.key)}>
                  <span className="tool-mark">{x.name.slice(4, 5) || x.name[0]}</span><span>{x.name}</span>
                  {box.mentions.some((m) => m.key === x.key) && <Icon name="check" className="ok" />}
                </button>
              ))}
            </Pop>
          </div>
        )}
        <div className="anchor shrink">
          <button className={`pill approval${menu === 'approval' ? ' on' : ''}`} onClick={() => setMenu(menu === 'approval' ? null : 'approval')}
            title={`${t('批准方式')} · ${t(approval[1])}`}>
            <Icon name="hand" size={14} /><span>{t(approval[1])}</span>
          </button>
          <Pop open={menu === 'approval'} close={close} className="up left wide">
            <div className="pop-head">{t('批准方式')}</div>
            {APPROVALS.map(([k, name, note]) => (
              <button key={k} className="item" onClick={async () => {
                close();
                if (k === 'full' && box.approval !== 'full') {
                  setAsk({ title: t('完全放开'), text: t('选了它以后，AI 改文件、运行命令、操作鼠标和键盘、删文件都不再问你。确定吗？'),
                    buttons: [{ label: t('取消') }, { label: t('确定'), primary: true, act: async () => setBox(await api.setApproval(where, k, true)) }] });
                  return;
                }
                setBox(await api.setApproval(where, k));
              }}>
                <span className="two"><b>{t(name)}</b><small>{t(note)}</small></span>
                {box.approval === k && <Icon name="check" className="ok" />}
              </button>
            ))}
          </Pop>
        </div>
        <ApproveBar a={asks.approvals[0]} api={api} />
        <span className="grow" />
        <div className="anchor shrink model-anchor">
          <button className={`pill model${menu === 'model' ? ' on' : ''}${box.model ? '' : ' unset'}`} onClick={() => setMenu(menu === 'model' ? null : 'model')}
            title={box.model ? `${box.model}${level ? ` · ${level}` : ''} — ${t('换模型和思考档位')}` : t('先选一个模型')}>
            <span className="m">{box.model || t('选择模型')}</span>{level && <span className="lv">{level}</span>}<Icon name="chev" size={13} />
          </button>
          <Pop open={menu === 'model'} close={close} className="up right models">
            {box.levels.length > 0 && (
              <ThinkSlider levels={box.levels} value={box.level} onChange={async (k) => setBox(await api.setLevel(where, k))} />
            )}
            <div className="scroll">
              {groups.map((g) => (
                <div key={g}>
                  <div className="pop-head">{t(g)}</div>
                  {box.models.filter((m) => m.group === g).map((m) => {
                    const on = box.pick && JSON.stringify(m.pick) === JSON.stringify(box.pick);
                    return (
                      <button key={g + m.label} className={`item${on ? ' current' : ''}`} onClick={async () => { setBox(await api.setModel(where, m.pick)); close(); }}>
                        <span>{m.label}</span>{on && <Icon name="check" className="ok" />}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </Pop>
        </div>
        {!voice && <button className="icon" title={t('说话输入')} aria-label={t('说话输入')} onClick={startVoice}><Icon name="mic" /></button>}
        {running && !text.trim() ? (
          <button className="send stop" title={t('停下来')} aria-label={t('停下来')} onClick={() => api.stop()}><Icon name="stop" size={14} /></button>
        ) : (
          <button className="send" title={ctrlEnter ? t('发送 · Ctrl+Enter') : t('发送 · Enter')} aria-label={t('发送')}
            disabled={!text.trim() || !!voice} onClick={() => send()}><Icon name="send" /></button>
        )}
      </div>
      {ask && <Ask {...ask} close={() => setAsk(null)} />}
    </div>
  );
}
