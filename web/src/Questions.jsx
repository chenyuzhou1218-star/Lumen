import { createContext, useState } from 'react';
import { Icon } from './icons.jsx';
import { t } from './i18n.js';

/* What is waiting for the user, pushed by the program (desktop/web_chat.py asks_json): {approvals, questions}. Shared by the message
   boxes: a long button to approve or refuse, and the question panel lifted above the box. */
export const Asks = createContext({ approvals: [], questions: [] });

/* The question panel (agents/ask_user.py): one question at a time (the user, 2026-11-13: ten questions on one page is no way to
   ask), with 上一步, 跳过 and 下一步; on the last one, 提交答案. Each has its options (one or several) and the user's own words;
   a skipped question goes back as skipped. What they choose goes straight back to the agent, which goes on. */
export function AskPanel({ q, api }) {
  const n = q.items.length;
  const [step, setStep] = useState(0);
  const [picked, setPicked] = useState(() => q.items.map(() => []));
  const [other, setOther] = useState(() => q.items.map(() => ''));
  const [skipped, setSkipped] = useState(() => q.items.map(() => false));
  const [busy, setBusy] = useState(false);
  const i = Math.min(step, n - 1);
  const it = q.items[i];
  const last = i === n - 1;
  const toggle = (opt) => {
    setSkipped((s) => s.map((x, k) => (k === i ? false : x)));
    setPicked((p) => p.map((list, k) => {
      if (k !== i) return list;
      if (it.multi) return list.includes(opt) ? list.filter((x) => x !== opt) : [...list, opt];
      return list.includes(opt) ? [] : [opt];
    }));
  };
  const answered = (k) => picked[k].length > 0 || other[k].trim() !== '';
  const send = async (skips = skipped) => {
    setBusy(true);
    await api.answerAsk(q.id, q.items.map((_, k) => ({ choices: skips[k] ? [] : picked[k], other: skips[k] ? '' : other[k], skipped: skips[k] || !answered(k) })));
    setBusy(false);
  };
  const skip = () => {
    const skips = skipped.map((x, k) => (k === i ? true : x));
    setSkipped(skips);
    if (last) send(skips); else setStep(i + 1);
  };
  return (
    <div className="ask-panel" role="dialog" aria-label={t('{0} 想先问你几个问题', q.agent)}>
      <div className="ask-head">
        <Icon name="info" size={15} /><b>{t('{0} 想先问你几个问题', q.agent)}</b>
        {n > 1 && <span className="ask-count">{t('第 {0} / {1} 题', i + 1, n)}</span>}
      </div>
      {n > 1 && <div className="ask-dots">{q.items.map((_, k) => <i key={k} className={k === i ? 'on' : answered(k) ? 'done' : ''} />)}</div>}
      <fieldset key={i} className="ask-q">
        <legend>{it.question}{it.multi && <em>{t('可多选')}</em>}</legend>
        <div className="ask-opts">
          {it.options.map((o) => (
            <button key={o} type="button" className={`ask-opt${picked[i].includes(o) ? ' on' : ''}`} onClick={() => toggle(o)}>
              <span className={`ask-mark${it.multi ? ' box' : ''}`} />{o}
            </button>
          ))}
          <label className="ask-own">
            <span>{t('其他，自己写')}</span>
            <input className="input" value={other[i]} placeholder={t('写下你的想法')}
              onChange={(e) => { const v = e.target.value; setOther((o) => o.map((x, k) => (k === i ? v : x))); setSkipped((s) => s.map((x, k) => (k === i ? false : x))); }}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); if (last) send(); else setStep(i + 1); } }} />
          </label>
        </div>
      </fieldset>
      <div className="ask-foot">
        {i > 0 && <button className="btn" disabled={busy} onClick={() => setStep(i - 1)}>{t('上一步')}</button>}
        <span className="ask-gap" />
        <button className="btn" disabled={busy} onClick={skip}>{t('跳过')}</button>
        {last
          ? <button className="btn primary" disabled={busy} onClick={() => send()}>{t('提交答案')}</button>
          : <button className="btn primary" disabled={busy} onClick={() => setStep(i + 1)}>{t('下一步')}</button>}
      </div>
    </div>
  );
}

/* What the agent wants to do, waiting for the user: a small card at the bottom right, above the message box (the user,
   2026-11-14): one short line of what it is - who, and what, with no coordinates - and 同意 / 不同意. 不同意 skips just that
   one action; the agent goes on with the rest. Nothing waiting: nothing here. */
const COORDS = /\s*[（(]\s*-?\d+\s*[,，]\s*-?\d+\s*[)）]/g;
export function ApproveBar({ a, api }) {
  if (!a) return null;
  const line = `${a.name || a.who}：${String(a.text || '').replace(COORDS, '')}`;
  return (
    <div className="approve-card" role="alertdialog" aria-label={line}>
      <div className="approve-line"><Icon name="info" size={14} /><span title={line}>{line}</span></div>
      <div className="approve-actions">
        <button className="btn small deny-btn" onClick={() => api.decideAsk(a.id, false)}>{t('不同意')}</button>
        <button className="approve-btn" onClick={() => api.decideAsk(a.id, true)}><Icon name="check" size={14} /><span>{t('同意')}</span></button>
      </div>
    </div>
  );
}
