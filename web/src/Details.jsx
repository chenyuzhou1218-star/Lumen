import { useEffect, useState } from 'react';
import { Ask, Modal, Segmented } from './Controls.jsx';
import { Icon } from './icons.jsx';
import { t } from './i18n.js';

/* 详细 under an answer: what the Qt task page showed around it - the escalations put plainly, the business
   investigation, the computer actions, the anomalies and the head's decisions, the change list with the system's test
   verdict (or the detail checklist), the findings with their reviews, the picture a making tool made - and the
   workspace overview (ADR 0013). All of it comes from what Lumen keeps permanently (desktop/web_details.py). */

function Chips({ chips }) {
  return (chips || []).map((c, i) => <span key={i} className={`tag ${c.tone || ''}`}>{c.text}</span>);
}

function Lines({ lines }) {
  return (lines || []).map((l, i) => <p key={i} className={`d-line ${l.tone || ''}`}>{l.text}</p>);
}

function Item({ it }) {
  const [open, setOpen] = useState(!it.folded);
  const more = (it.lines && it.lines.length > 0) || it.image;
  return (
    <div className={`d-item${open ? ' open' : ''}`}>
      <button className="d-item-head" onClick={() => more && setOpen(!open)} disabled={!more}>
        <span className="d-chips"><Chips chips={it.chips} /></span>
        <span className="d-title">{it.title}</span>
        {more && it.folded && <Icon name="chev" size={13} className="chev" />}
      </button>
      {it.sub && <p className="d-sub">{it.sub}</p>}
      {open && <Lines lines={it.lines} />}
      {open && it.image && <img className="d-shot" src={it.image} alt="" />}
    </div>
  );
}

export function Section({ s }) {
  const [more, setMore] = useState(false);
  return (
    <section className={`d-section d-${s.key}`}>
      <header><b>{s.title}</b><Chips chips={s.chips} /></header>
      {s.note && <p className="d-note">{s.note}</p>}
      {s.progress && <div className="d-progress"><i style={{ width: `${(100 * s.progress.done) / s.progress.total}%` }} /></div>}
      <Lines lines={s.lines} />
      {s.rows && s.rows.length > 0 && (
        <table className="d-rows"><tbody>
          {s.rows.map((r, i) => <tr key={i}>{r.cells.map((c, j) => <td key={j} className={`${c.tone || ''}${c.mono ? ' mono' : ''}`}>{c.text}</td>)}</tr>)}
        </tbody></table>
      )}
      {(s.items || []).map((it, i) => <Item key={i} it={it} />)}
      {s.more && (
        <div className="d-more">
          <button className="steps-head" onClick={() => setMore(!more)}><Icon name="chev" size={13} className={`chev${more ? ' down' : ''}`} />{s.more.head}</button>
          {more && <Lines lines={s.more.lines} />}
        </div>
      )}
    </section>
  );
}

const TABS = () => [['changes', t('改动')], ['timeline', t('时间线')], ['files', t('读过的文件')], ['commands', t('命令与操作')], ['findings', t('结论与记忆')]];

function Workspace({ api, taskId, close }) {
  const [tab, setTab] = useState('changes');
  const [data, setData] = useState(null);
  const [at, setAt] = useState(-1);
  const [detail, setDetail] = useState(null);
  const [ask, setAsk] = useState(null);
  const load = () => { setData(null); setAt(-1); setDetail(null); api.wsRows(taskId, tab).then(setData); };
  useEffect(load, [api, taskId, tab]); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (i) => { setAt(i); setDetail(null); api.wsDetail(taskId, tab, i).then(setDetail); };
  const undo = () => setAsk({ title: t('撤回修改'), text: t('把这次调查改动过的 {0} 个文件恢复到调查开始时的样子？调查结束后又被改过的文件会跳过，不会覆盖你的修改。', data.rows.length),
    buttons: [{ label: t('取消') }, { label: t('撤回'), danger: true, act: async () => {
      const r = await api.wsUndo(taskId);
      setAsk(r.ok ? { title: t('已撤回'), text: t('恢复 {0} 个、删除 {1} 个、跳过 {2} 个文件。', r.restored, r.removed, r.skipped), details: r.lines, buttons: [{ label: t('知道了'), primary: true }] }
        : { title: t('撤回失败'), text: r.error, buttons: [{ label: t('知道了'), primary: true }] });
      load();
    } }] });
  return (
    <Modal title={t('工作区一览')} close={close} width={1040}>
      <p className="muted">{t('来自永久保存的日志和记录，不受模型上下文压缩影响。')}</p>
      <div className="section-bar">
        <Segmented value={tab} onChange={setTab} options={TABS().map(([v, l]) => ({ value: v, label: l }))} />
        <span className="grow" />
        {tab === 'changes' && data && data.undo && <button className="btn small danger" onClick={undo}>{t('撤回这次调查的所有修改')}</button>}
      </div>
      {data && data.note && <p className="muted">{data.note}</p>}
      <div className="ws">
        <ol className="ws-list">
          {!data && <li className="muted"><span className="spin" /></li>}
          {data && data.rows.length === 0 && <li className="muted">{t('这里还没有内容。')}</li>}
          {data && data.rows.map((r, i) => (
            <li key={i}>
              <button className={`ws-row${i === at ? ' on' : ''}`} onClick={() => pick(i)}>
                {r.mark && <i className={r.tone || ''}>{r.mark}</i>}
                <span><b className={r.text.startsWith('$') ? 'mono' : ''}>{r.text}</b>{(r.sub || r.at) && <small>{[r.at, r.sub].filter(Boolean).join(' · ')}</small>}</span>
              </button>
            </li>
          ))}
        </ol>
        <div className="ws-detail">
          {at < 0 && <p className="muted">{t('点左边的一行看详情。')}</p>}
          {at >= 0 && !detail && <span className="spin" />}
          {detail && detail.diff && <pre className="diff">{detail.diff.split('\n').map((l, i) => <span key={i} className={l.startsWith('+') ? 'add' : l.startsWith('-') ? 'del' : l.startsWith('@@') ? 'hunk' : ''}>{l}{'\n'}</span>)}</pre>}
          {detail && detail.text !== undefined && <pre>{detail.text}</pre>}
        </div>
      </div>
      {ask && <Ask {...ask} close={() => setAsk(null)} />}
    </Modal>
  );
}

export function Details({ api, taskId, running }) {
  const [d, setD] = useState(null);
  const [ws, setWs] = useState(false);
  useEffect(() => {
    let alive = true;
    let timer = null;
    const load = async () => {
      const r = await api.detailsJson(taskId);
      if (!alive) return;
      setD(r);
      if (running) timer = setTimeout(load, 2000);
    };
    load();
    return () => { alive = false; clearTimeout(timer); };
  }, [api, taskId, running]);
  if (!d) return <div className="details"><span className="spin" /></div>;
  if (d.error || d.missing) return <div className="details"><p className="muted">{d.error || t('这个聊天已经不在了。')}</p></div>;
  return (
    <div className="details">
      <div className="d-head">
        <span className="tag">{d.status}</span><span className="muted-inline" title={d.cached ? t('另有 {0} 是缓存重读，价格约十分之一，没有算在里面。', d.cached) : ''}>{d.info}</span>
        <span className="grow" />
        <button className="btn small" onClick={() => setWs(true)}><Icon name="panel" size={14} />{t('工作区一览')}</button>
      </div>
      {d.picture && <img className="d-picture" src={d.picture} alt="" />}
      {d.escalations.map((e) => <div key={e} className="need column"><Icon name="warn" size={14} /><span><b>{t('需要你处理')}</b>{` · ${e}`}</span></div>)}
      {d.sections.map((s) => <Section key={s.key} s={s} />)}
      {d.sections.length === 0 && d.escalations.length === 0 && !d.picture && <p className="muted">{t('这个回答没有结论、异常、改动或电脑操作要列出来。完整记录在“工作区一览”。')}</p>}
      {ws && <Workspace api={api} taskId={taskId} close={() => setWs(false)} />}
    </div>
  );
}
