import { useEffect, useRef, useState } from 'react';
import { Ask, Combo, Field, Modal, Segmented, Select, Switch } from './Controls.jsx';
import { Icon } from './icons.jsx';
import { Markdown } from './Markdown.jsx';
import { chinese, t } from './i18n.js';
import { CodePerms, ComputerPerms } from './Pages.jsx';

/* 设置: the services and their keys, which model each AI uses, memory, appearance and usage. Every control changes the
   real setting (desktop/web_settings.py): the user's own preferences at once, the project's configuration when 保存 is
   pressed (then Lumen opens again with it). A key typed here goes to Python once and is never shown again. */

const SECTIONS = () => [
  ['services', t('服务与密钥'), 'key', t('可以接入任意多个服务：只要兼容 OpenAI 接口或 Anthropic 接口就行。密钥只保存在 Windows 凭据管理器，不写进配置文件。')],
  ['agent_models', t('AI 模型'), 'grid', t('每个 AI 用哪个服务的哪个模型、想得多深，出错时换用哪些备用模型。模型完全由你决定。')],
  ['memory', t('长期记忆'), 'think', t('每个成员都有自己的记忆。这里的设置作用于这个项目的所有 AI。')],
  ['appearance', t('外观'), 'edit', t('只属于你自己的偏好，改了立刻生效，不用保存。')],
  ['usage', t('用量'), 'info', t('这个项目里所有 AI 的回答加起来。新用量是真正新产生的；缓存重读约为新用量价格的十分之一。')],
  ['code', t('自动测试'), 'edit', t('系统在开工前、每处修改后、交差前自动跑测试（不花 token），谁改坏了原来能过的测试，当场指出。')],
  ['computer', t('电脑操作'), 'info', t('截屏、鼠标键盘、开关程序、终端，所有窗口都能用。要不要先问你，在输入框下面的“批准方式”里选。')],
  // not in the list: opened from 长期记忆, and from 功能手册 below the list (F1)
  ['knowledge', t('结论与记忆'), 'think', t('AI 提交的结论（经过监督者独立复查才算“成立”）和它们写下的长期记忆。全部保存在本机，不受模型上下文压缩影响。'), 'memory'],
  ['book', t('功能手册'), 'info', t('Lumen 能做的每一件事，用你选的语言写。'), ''],
];
const LISTED = ['services', 'agent_models', 'memory', 'code', 'computer', 'appearance', 'usage'];
let token = 0;

/* A test that takes a while: the answer comes later through the bridge's `probed` signal. */
function useProbe(api) {
  const waiting = useRef({});
  useEffect(() => api.on('probed', (r) => {
    const done = waiting.current[r.token];
    if (done) { delete waiting.current[r.token]; done(r); }
  }), [api]);
  return (what, data) => new Promise((resolve) => {
    token += 1;
    const id = `p${token}`;
    waiting.current[id] = resolve;
    api.settingsProbe(what, data, id);
  });
}

function Result({ r }) {
  if (!r) return null;
  return <p className={`result ${r.busy ? 'busy' : r.ok ? 'good' : 'bad'}`}>{r.busy ? <span className="spin" /> : <Icon name={r.ok ? 'check' : 'warn'} size={14} />}<span>{r.text}</span></p>;
}

/* ---- 服务与密钥 ------------------------------------------------------------------------------------------------- */

function ServiceForm({ api, s, existing, close, act }) {
  const probe = useProbe(api);
  const [f, setF] = useState(null);
  const [key, setKey] = useState('');
  const [fetched, setFetched] = useState([]);
  const [testModel, setTestModel] = useState('');
  const [result, setResult] = useState(null);
  const [why, setWhy] = useState('');
  useEffect(() => {
    if (existing) api.settingsForm(existing).then(setF);
    else {
      const p = s.presets[0];
      const taken = new Set(s.endpoints.map((e) => e.id));
      setF(fromPreset(p, taken));
    }
  }, [existing]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!f) return null;
  const set = (patch) => setF({ ...f, ...patch });
  const preset = (id) => {
    const p = s.presets.find((x) => x.id === id);
    const taken = new Set(s.endpoints.map((e) => e.id).filter((x) => x !== existing));
    setF(existing ? { ...f, provider: p.id, kind: p.kind, base_url: p.base_url, local: p.local } : fromPreset(p, taken));
    setFetched([]);
  };
  const models = [...new Set([...f.models.split('\n').map((m) => m.trim()).filter(Boolean), ...fetched])];
  const formData = () => ({ ...f, existing: existing || '', key, test_model: testModel });
  const run = async (withModel) => {
    setResult({ busy: true, text: withModel ? t('正在测试……') : t('正在读取模型列表……') });
    const r = await probe('endpoint', { form: formData(), with_model: withModel });
    if (r.models && r.models.length) setFetched(r.models);
    setResult(r);
  };
  const ok = async () => {
    const r = await act('endpoint', formData(), true);
    if (r && r.error) setWhy(r.error); else close();
  };
  const note = (s.presets.find((p) => p.id === f.provider) || {}).note;
  const keyHint = f.key_pending === 'typed' ? t('已填写，点页面上的“保存”后生效（留空表示不修改）')
    : f.key_pending === 'drop' ? t('保存后会删除已保存的密钥；在这里填写一个新密钥可以替换它')
      : f.key_saved ? t('已保存（留空表示不修改）') : t('粘贴你的 API 密钥');
  return (
    <Modal title={existing ? t('编辑服务') : t('添加服务')} close={close} width={600} footer={<>
      <button type="button" className="btn" onClick={close}>{t('取消')}</button>
      <button type="button" className="btn primary" onClick={ok}>{existing ? t('确定') : t('添加')}</button>
    </>}>
      <div className="form">
        <Field label={t('服务商')} note={note}>
          <Select value={f.provider} options={s.presets.map((p) => ({ value: p.id, label: p.name }))} onChange={preset} />
        </Field>
        <Field label={t('显示名称')}><input className="input" value={f.name} onChange={(e) => set({ name: e.target.value })} /></Field>
        <Field label={t('服务 ID')} note={existing ? t('已有的服务不能改 ID（AI 的配置引用它）') : t('小写字母、数字、- 或 _')}>
          <input className="input mono" value={f.id} disabled={!!existing} onChange={(e) => set({ id: e.target.value.toLowerCase() })} />
        </Field>
        <Field label={t('接口类型')}>
          <Segmented value={f.kind} onChange={(v) => set({ kind: v })}
            options={[{ value: 'openai_compatible', label: t('OpenAI 兼容接口') }, { value: 'anthropic', label: t('Anthropic 接口') }]} />
        </Field>
        <Field label={t('地址')}><input className="input mono" value={f.base_url} placeholder="https://…/v1" onChange={(e) => set({ base_url: e.target.value })} /></Field>
        <Switch on={f.local} label={t('本机或局域网里的服务')} note={t('例如 Ollama、LM Studio')}
          onChange={(v) => set({ local: v, data_class: !v && f.data_class === 'local_only' ? 'internal' : f.data_class })} />
        <Field label={t('API 密钥')}>
          <Segmented value={f.key_mode} onChange={(v) => set({ key_mode: v })}
            options={[{ value: 'keyring', label: t('凭据管理器') }, { value: 'env', label: t('环境变量') }, { value: 'none', label: t('不需要') }]} />
          {f.key_mode === 'keyring' && <input className="input mono" type="password" autoComplete="off" value={key} placeholder={keyHint} onChange={(e) => setKey(e.target.value)} />}
          {f.key_mode === 'env' && <input className="input mono" value={f.key_env} placeholder="OPENAI_API_KEY" onChange={(e) => set({ key_env: e.target.value.toUpperCase() })} />}
          <small className="hint">{f.key_mode === 'keyring' ? t('密钥只保存在本机的 Windows 凭据管理器，不写进配置文件和日志。') : f.key_mode === 'env' ? t('从这个环境变量读取密钥。') : ''}</small>
        </Field>
        <Field label={t('可发送的代码级别')}>
          <Select value={f.data_class} options={s.data_classes.filter((d) => f.local || d.value !== 'local_only')} onChange={(v) => set({ data_class: v })} />
        </Field>
        {f.kind === 'openai_compatible' && (
          <Switch on={f.text_calls !== false} label={t('兼容把工具调用写成文字的模型')} note={t('推荐保持打开')} onChange={(v) => set({ text_calls: v })} />
        )}
        <Field label={t('模型')} note={t('常用的模型名，一行一个')}>
          <textarea className="input mono" rows={3} value={f.models} onChange={(e) => set({ models: e.target.value })} />
          <div className="row-btns"><button type="button" className="btn small" onClick={() => run(false)}>{t('获取模型列表')}</button>
            {fetched.length > 0 && <button type="button" className="btn small ghost" onClick={() => set({ models: [...new Set([...models])].join('\n') })}>{t('全部加进来')}</button>}</div>
        </Field>
        <Field label={t('测试')} note={t('只发送一句固定的测试提示，不发送你的代码。')}>
          <div className="test-row">
            <Combo value={testModel} options={models} onCommit={setTestModel} placeholder={t('选择或填写一个模型')} />
            <button type="button" className="btn small" onClick={() => run(true)}>{t('测试连接与工具调用')}</button>
          </div>
          <Result r={result} />
        </Field>
        {why && <p className="result bad"><Icon name="warn" size={14} /><span>{why}</span></p>}
      </div>
    </Modal>
  );
}

function fromPreset(p, taken) {
  const base = p.id.replace(/[^a-z0-9_-]/g, '') || 'api';
  let id = base;
  for (let n = 2; taken.has(id); n += 1) id = `${base}-${n}`;
  return { id, name: p.name, provider: p.id, kind: p.kind, base_url: p.base_url, local: p.local, key_mode: p.local ? 'none' : 'keyring',
    key_env: p.key_env, data_class: p.local ? 'local_only' : 'internal', text_calls: true, models: '', key_saved: false, key_pending: '' };
}

function Services({ api, s, act, ask }) {
  const probe = useProbe(api);
  const [editing, setEditing] = useState(null); // endpoint id, '' for a new one
  const [tests, setTests] = useState({});
  const test = async (id) => {
    setTests((x) => ({ ...x, [id]: { busy: true, text: t('正在连接……') } }));
    const r = await probe('endpoint', { id });
    setTests((x) => ({ ...x, [id]: r }));
  };
  return (
    <>
      <div className="section-bar">
        <b>{t('已接入 {0} 个服务', s.endpoints.length)}</b>
        <span className="grow" />
        <button className="btn" onClick={() => s.endpoints.forEach((e) => test(e.id))}>{t('全部测试')}</button>
        <button className="btn primary" onClick={() => setEditing('')}><Icon name="plus" size={14} />{t('添加服务')}</button>
      </div>
      <div className="cards">
        {s.endpoints.map((e) => (
          <article key={e.id} className="card">
            <header>
              <h4 title={e.name}>{e.name}</h4>
              <span className="tag">{e.local ? t('本机') : t('云端')}</span>
              <span className={`tag ${e.pending === 'typed' ? 'warn' : e.pending === 'drop' || e.status === 'missing' ? 'bad' : e.status === 'not_needed' ? '' : 'good'}`}>
                {e.pending === 'typed' ? t('新密钥待保存') : e.pending === 'drop' ? t('保存后删除密钥') : e.status_text}
              </span>
            </header>
            <p className="meta mono" title={e.base_url}>{e.id} · {e.kind_text} · {e.base_url}</p>
            <p className="meta">{t('可接收：')}{e.data_class} · {t('使用它的 AI：')}<span title={e.used_by.join('、')}>{e.used_text}</span></p>
            {e.status === 'missing' && !e.pending && <p className="result bad"><Icon name="warn" size={14} /><span>{t('这个服务还没有密钥。点“编辑”填写。')}</span></p>}
            <Result r={tests[e.id]} />
            <footer>
              <button className="btn small" onClick={() => test(e.id)}>{t('测试连接')}</button>
              {e.editable && <button className="btn small" onClick={() => setEditing(e.id)}>{t('编辑')}</button>}
              {e.status === 'keyring' && !e.pending && (
                <button className="btn small ghost" onClick={() => ask({ title: t('删除密钥'), text: t('删除这个服务保存在 Windows 凭据管理器里的密钥？点“保存”后才会真正删除。'),
                  buttons: [{ label: t('取消') }, { label: t('删除密钥'), danger: true, act: () => act('drop_key', { id: e.id }) }] })}>{t('删除密钥')}</button>
              )}
              <span className="grow" />
              <button className="btn small ghost danger" onClick={() => ask({ title: t('删除服务'), text: t('删除服务“{0}”？点“保存”后，保存在凭据管理器里的密钥也会一起删除。', e.name),
                buttons: [{ label: t('取消') }, { label: t('删除'), danger: true, act: () => act('remove_endpoint', { id: e.id }) }] })}>{t('删除')}</button>
            </footer>
          </article>
        ))}
      </div>
      {editing !== null && <ServiceForm api={api} s={s} existing={editing} act={act} close={() => setEditing(null)} />}
    </>
  );
}

/* ---- AI 模型 ----------------------------------------------------------------------------------------------------- */

function AgentRow({ a, s, act }) {
  const ep = s.endpoints.find((e) => e.id === a.endpoint);
  const [fb, setFb] = useState(a.fallbacks);
  useEffect(() => setFb(a.fallbacks), [a.fallbacks]);
  return (
    <div className="agent">
      <div className="agent-who">
        {a.avatar ? <img src={a.avatar} alt="" /> : <span className="letter" style={{ background: a.colour || 'var(--ink3)' }}>{a.name[0].toUpperCase()}</span>}
        <span className="two"><b>{a.name}{a.cn && chinese() && <i style={{ color: a.colour }}> {t(a.cn)}</i>}</b><small title={a.meaning}>{a.job}</small></span>
      </div>
      <Select className="ep" value={a.endpoint} options={s.endpoints.map((e) => ({ value: e.id, label: e.name }))} onChange={(v) => act('agent', { id: a.id, field: 'endpoint', value: v })} />
      <Combo className={`model${a.model ? '' : ' empty'}`} value={a.model} options={ep ? ep.models : []} placeholder={t('选择模型')}
        onCommit={(v) => act('agent', { id: a.id, field: 'model', value: v })} />
      <Select className="think" value={a.think} options={s.levels} onChange={(v) => act('agent', { id: a.id, field: 'think', value: v })} />
      <input className="input mono fb" value={fb} placeholder={t('备用：服务ID/模型')} title={t('主模型出错时按顺序改用这些模型，例如 openai/gpt-x, ollama/qwen3:4b')}
        onChange={(e) => setFb(e.target.value)} onBlur={async () => { if (fb !== a.fallbacks) { const r = await act('agent', { id: a.id, field: 'fallbacks', value: fb }); if (r && r.error) setFb(a.fallbacks); } }}
        onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} />
      {a.removable ? <button className="head-btn" title={t('移除')} aria-label={t('移除')} onClick={() => act('remove_agent', { id: a.id }, false, t('移除 {0}？它的历史记忆会保留。', a.id))}><Icon name="close" size={13} /></button>
        : <span className="head-btn-space" />}
    </div>
  );
}

function Agents({ s, act }) {
  const team = s.agents.filter((a) => a.team);
  const others = s.agents.filter((a) => !a.team);
  const table = (rows) => (
    <div className="agents">
      <div className="agent head"><span>{t('AI')}</span><span>{t('服务')}</span><span>{t('模型')}</span><span>{t('思考')}</span><span>{t('备用模型')}</span><span /></div>
      {rows.map((a) => <AgentRow key={a.id} a={a} s={s} act={act} />)}
    </div>
  );
  return (
    <>
      {team.length > 0 && (
        <>
          <div className="section-bar"><b>{t('Lumen 团队')}</b></div>
          <p className="muted">{t('你只跟 Lumen 说话；专门的活它会交给最合适的成员，几个人可以同时干。每个成员用你选的模型，可以在下面单独换。')}</p>
          {table(team)}
        </>
      )}
      {others.length > 0 && (
        <>
          <div className="section-bar"><b>{team.length ? t('其他模式的 AI（{0} 个）', others.length) : t('{0} 个 AI', others.length)}</b><span className="grow" />
            {s.mode === 'advanced' && <button className="btn" onClick={() => act('add_pair', {})}><Icon name="plus" size={14} />{t('添加一对 执行者 + 监督者')}</button>}</div>
          {table(others)}
        </>
      )}
    </>
  );
}

/* ---- 长期记忆 ---------------------------------------------------------------------------------------------------- */

/* What the AI remembers of the user (memory/digest.py): theirs to read, change and clear. A part is saved when the box loses
   focus; an empty box clears that part. */
function Known({ k, act }) {
  const [about, setAbout] = useState(k.about);
  const [project, setProject] = useState(k.project);
  useEffect(() => { setAbout(k.about); setProject(k.project); }, [k.about, k.project]);
  const empty = !k.about && !k.project;
  return (
    <>
      <div className="section-bar"><b>{t('AI 对你的记忆')}</b><span className="muted-inline">{t('所有对话共用')}</span></div>
      <p className="muted">{t('每次新对话开始前，AI 会回顾以前的对话，把要点压缩在这里，新对话一开始就带着它。你可以直接改；改错的地方它以后会照你改的来。')}</p>
      <div className="panel">
        <Field label={t('关于你')} note={t('所有项目共用：你是谁、怎么说话、喜欢什么、立过的规矩')}>
          <textarea className="input known-text" rows={6} value={about} spellCheck={false} placeholder={t('还没有。聊过几次以后这里会有内容。')}
            onChange={(e) => setAbout(e.target.value)} onBlur={() => about !== k.about && act('known_text', { part: 'about', text: about })} />
        </Field>
        <Field label={t('这个项目')} note={t('这个项目里做过什么、定了什么、做到哪一步')}>
          <textarea className="input known-text" rows={10} value={project} spellCheck={false} placeholder={t('还没有。聊过几次以后这里会有内容。')}
            onChange={(e) => setProject(e.target.value)} onBlur={() => project !== k.project && act('known_text', { part: 'project', text: project })} />
        </Field>
        <Field label={t('清空记忆')} note={t('两部分都删掉；以前的对话不会再被拿来重新整理')}>
          <button className="btn" disabled={empty} onClick={() => act('known_clear', {}, false,
            t('AI 对你的记忆会全部删掉，以前的对话也不会再被拿来重新整理。删掉后不能恢复。'))}>{t('清空')}</button>
        </Field>
      </div>
    </>
  );
}

function Memory({ api, s, act, go }) {
  const probe = useProbe(api);
  const m = s.memory;
  const e = m.embedding;
  const [result, setResult] = useState(null);
  const ep = e.endpoints.find((x) => x.value === e.endpoint);
  return (
    <>
      <div className="panel">
        <Switch on={m.recall} label={t('回忆以前的记忆')} note={t('打开后回答会慢一些')} onChange={(x) => act('memory', { recall: x })} />
        <Field label={t('所有记忆和结论')}><button className="btn" onClick={() => go('knowledge')}>{t('查看所有记忆和结论')}<Icon name="chevRight" size={14} /></button></Field>
      </div>
      <Known k={s.known} act={act} />
      <div className="section-bar"><b>{t('按意思回忆')}</b><span className="muted-inline">{t('可选')}</span></div>
      <p className="muted">{t('选一个嵌入模型后，AI 能想起意思相近、但用词不同的旧结论。不选就只按文字和耦合关系回忆。笔记只会发给数据级别允许的服务。')}</p>
      <div className="panel">
        <Field label={t('嵌入模型的服务')}>
          <Select value={e.endpoint} options={[{ value: '', label: t('不使用') }, ...e.endpoints]} onChange={(v) => { setResult(null); act('embedding', { endpoint: v, model: '' }); }} />
        </Field>
        {e.endpoint && (
          <Field label={t('嵌入模型')}>
            <div className="test-row">
              <Combo value={e.model} options={ep ? ep.models : []} placeholder={t('例如 bge-m3、text-embedding-3-small')}
                onCommit={(v) => { setResult(null); act('embedding', { endpoint: e.endpoint, model: v }); }} />
              <button className="btn small" onClick={async () => { setResult({ busy: true, text: t('正在测试（只发送两句固定的测试文字）……') }); setResult(await probe('embedding', { endpoint: e.endpoint, model: e.model })); }}>{t('测试')}</button>
            </div>
            <Result r={result} />
          </Field>
        )}
      </div>
    </>
  );
}

/* ---- 外观 -------------------------------------------------------------------------------------------------------- */

function Appearance({ api, s, act, ask }) {
  const v = s.appearance.values;
  const c = s.appearance.choices;
  const set = (key, value) => act('appearance', { key, value });
  const accents = { amber: '#ef8a17', blue: '#2f6bff', violet: '#7c5cf0', green: '#1f9d6b', rose: '#e5487a', ink: '#26241f' };
  return (
    <>
      <div className="section-bar"><b>{t('样子')}</b></div>
      <div className="panel">
        <Field label={t('界面颜色')} note={t('浅色或深色：所有页面一起变，终端也跟着变')}><Segmented value={v.mode} options={c.mode} onChange={(x) => set('mode', x)} /></Field>
        <Field label={t('强调色')}>
          <div className="swatches">
            {c.accent.map((o) => (
              <button key={o.value} type="button" className={`swatch${v.accent === o.value ? ' on' : ''}`} title={o.label} aria-label={o.label} onClick={() => set('accent', o.value)}>
                <i style={{ background: accents[o.value] }} />
              </button>
            ))}
            <span className="muted-inline">{(c.accent.find((o) => o.value === v.accent) || {}).label}</span>
          </div>
        </Field>
        <Field label={t('字号')}><Segmented value={v.font_size} options={c.font_size} onChange={(x) => set('font_size', x)} /></Field>
        <Field label={t('聊天宽度')}><Segmented value={v.chat_width} options={c.chat_width} onChange={(x) => set('chat_width', x)} /></Field>
        <Field label={t('终端字号')}><Select value={v.term_font} options={c.term_font} onChange={(x) => set('term_font', x)} /></Field>
        <Switch on={v.reduced_motion} label={t('减少动态效果')} note={t('页面不做入场动画')} onChange={(x) => set('reduced_motion', x)} />
        <Switch on={v.figure_motion} label={t('让小人轻轻浮动')} note={t('新聊天页上的 Lumen')} onChange={(x) => set('figure_motion', x)} />
        <Field label={t('开场动画')}><button className="btn" onClick={() => api.replayWelcome()}>{t('播放一次开场动画')}</button></Field>
      </div>
      <div className="section-bar"><b>{t('用起来')}</b></div>
      <div className="panel">
        <Field label={t('界面语言')}>
          <Select value={v.language} options={c.language} onChange={(x) => set('language', x)} />
        </Field>
        <Field label={t('发送消息')}><Select value={v.send_key} options={c.send_key} onChange={(x) => set('send_key', x)} /></Field>
        <Field label={t('浏览器搜索')}><Select value={v.search_engine} options={c.search_engine} onChange={(x) => set('search_engine', x)} /></Field>
        <Switch on={v.show_times} label={t('在消息下面显示时间')} onChange={(x) => set('show_times', x)} />
        <Switch on={v.expand_steps} label={t('回答时展开每一步')} onChange={(x) => set('expand_steps', x)} />
        <Switch on={v.auto_fold} label={t('长回答自动省略过程')} note={t('关掉后，回答的过程一直展开')} onChange={(x) => set('auto_fold', x)} />
        <Switch on={v.notify_done} label={t('回答做完时提醒我')} note={t('窗口不在最前面时')} onChange={(x) => set('notify_done', x)} />
        <Switch on={v.show_tokens} label={t('在聊天顶部显示 token 用量')} onChange={(x) => set('show_tokens', x)} />
      </div>
    </>
  );
}

/* ---- 用量 -------------------------------------------------------------------------------------------------------- */

function Usage({ s, act }) {
  const u = s.usage;
  const top = Math.max(1, ...u.days.map((d) => d.value));
  const v = s.appearance.values;
  return (
    <>
      <div className="panel limit">
        <Field label={t('每个问题最多用多少新 token')} note={t('所有 AI 加在一起，缓存重读不算。到了就停下来问你要不要接着做；发问题前，以往同类问题花得比这个多也会先告诉你。')}>
          <Segmented value={v.spend_limit} options={s.appearance.choices.spend_limit} onChange={(x) => act('appearance', { key: 'spend_limit', value: x })} />
        </Field>
      </div>
      <div className="tiles three">
        {u.tiles.map((x) => (
          <div key={x.key} className="tile"><small>{x.title}</small><b>{x.value}</b>
            <span>{t('缓存重读 {0} · {1} 次回答', x.cached, x.answers)}{x.cost ? ` · $${x.cost.toFixed(2)}` : ''}</span></div>
        ))}
      </div>
      <div className="section-bar"><b>{t('最近 {0} 天的新用量', u.days.length)}</b></div>
      <div className="panel">
        <div className="bars">
          {u.days.map((d, i) => (
            <div key={d.day} className="bar" title={`${d.day}  ${d.short}`}>
              <span className="val">{d.value && (d.value === top || u.days.length <= 7) ? d.short : ''}</span>
              <i style={{ height: `${d.value ? Math.max(4, (d.value / top) * 100) : 3}%` }} className={d.value ? '' : 'zero'} />
              <small>{i % 2 === 0 || i === u.days.length - 1 ? d.day.slice(5).replace('-', '/') : ''}</small>
            </div>
          ))}
        </div>
      </div>
      <div className="section-bar"><b>{t('谁用得最多')}</b></div>
      <div className="panel list">
        {u.who.length ? u.who.map((w) => (
          <div key={w.who} className="who-row"><b>{w.who}</b><span>{w.fresh}</span><small>{t('{0} 次', w.answers)}{w.cost ? ` · $${w.cost.toFixed(2)}` : ''}</small></div>
        )) : <p className="muted">{t('还没有用量。问一个问题之后这里就有了。')}</p>}
      </div>
    </>
  );
}

/* ---- 结论与记忆, 功能手册 ----------------------------------------------------------------------------------------------- */

function Knowledge({ api }) {
  const [tab, setTab] = useState('claims');
  const [needle, setNeedle] = useState('');
  const [k, setK] = useState(null);
  useEffect(() => {
    const timer = setTimeout(() => api.knowledge(tab, needle).then(setK), needle ? 220 : 0);
    return () => clearTimeout(timer);
  }, [api, tab, needle]);
  if (!k) return null;
  const tiles = [['supported', t('成立（已独立复查）'), 'good'], ['proposed', t('待验证'), 'warn'], ['refuted', t('被推翻'), k.stats.refuted ? 'bad' : ''], ['notes', t('长期记忆'), '']];
  return (
    <>
      <div className="tiles four">{tiles.map(([key, title, tone]) => <div key={key} className={`tile ${tone}`}><small>{title}</small><b>{k.stats[key]}</b></div>)}</div>
      <div className="section-bar">
        <Segmented value={tab} onChange={setTab} options={[{ value: 'claims', label: t('结论') }, { value: 'notes', label: t('长期记忆') }]} />
        <span className="grow" />
        <label className="searchbox small"><Icon name="search" size={14} />
          <input value={needle} onChange={(e) => setNeedle(e.target.value)} placeholder={t('搜索文字、路径、ID……')} spellCheck={false} /></label>
      </div>
      <div className="records">
        {k.rows.map((r) => (
          <article key={r.id} className="record">
            <div className="record-head">
              <span className={`tag ${r.status === 'supported' ? 'good' : r.status === 'refuted' ? 'bad' : r.status ? 'warn' : ''}`}>{r.kind}</span>
              {r.level && <span className="tag">{r.level}</span>}
            </div>
            <p>{r.text}</p>
            <small className="mono">{[...r.meta, r.id].join(' · ')}</small>
          </article>
        ))}
        {k.rows.length === 0 && <p className="muted">{needle ? t('没有匹配的记录。') : t('还没有记录。')}</p>}
        {k.total > k.shown && <p className="muted">{t('只显示最近的 {0} 条，共 {1} 条；用搜索缩小范围。', k.shown, k.total)}</p>}
      </div>
    </>
  );
}

function Book({ api }) {
  const [b, setB] = useState(null);
  useEffect(() => { api.book('').then(setB); }, [api]);
  if (!b) return null;
  return (
    <>
      <div className="section-bar"><span className="grow" /><span className="muted-inline">{t('手册语言')}</span>
        <Select value={b.lang} options={b.langs} onChange={(lang) => api.book(lang).then(setB)} width={200} className="narrow" /></div>
      <article className="book"><Markdown text={b.text} api={api} /></article>
    </>
  );
}

/* ---- the page ---------------------------------------------------------------------------------------------------- */

export function Settings({ api, view }) {
  const [s, setS] = useState(null);
  const [section, setSection] = useState(view.section || 'services');
  const [dialog, setDialog] = useState(null);
  const [toast, setToast] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.settings().then(setS); if (view.section) setSection(view.section); }, [api, view]); // what Python holds now
  const go = (key) => { setSection(key); api.settingsSection(key); api.settings().then(setS); };
  const say = (text) => { setToast(text); setTimeout(() => setToast(''), 3200); };
  // one change; with confirm, asked first. A refusal is shown and nothing changes.
  const act = async (action, data, quiet, confirm) => {
    if (confirm) {
      setDialog({ title: t('请确认'), text: confirm, buttons: [{ label: t('取消') }, { label: t('确定'), danger: true, act: () => act(action, data) }] });
      return null;
    }
    const r = await api.settingsAct(action, data);
    if (r.error) { if (!quiet) setDialog({ title: t('没有改成'), text: r.error, buttons: [{ label: t('知道了'), primary: true }] }); return r; }
    setS(r);
    if (r.note) say(r.note);
    return r;
  };
  const save = async () => {
    setBusy(true);
    const r = await api.settingsSave();
    setBusy(false);
    if (!r.ok) { setDialog({ title: t('没有保存'), text: r.error, buttons: [{ label: t('知道了'), primary: true }] }); return; }
    setS(await api.settings());
    setDialog({ title: t('已保存'), text: t('配置已保存（旧版本备份为 .bak）。重启 Lumen 后，新的服务、AI 和模型才会生效。'),
      details: [...(r.problems || []), ...(r.warnings || [])],
      buttons: [{ label: t('稍后') }, { label: t('立即重启'), primary: true, act: () => api.restart() }] });
  };
  const revert = async () => { setS(await api.settingsRevert()); say(t('已放弃修改')); };
  if (!s) return <div className="page" />;
  const cur = SECTIONS().find((x) => x[0] === section) || SECTIONS()[0];
  const needsConfig = ['services', 'agent_models', 'memory', 'code', 'computer'].includes(cur[0]) && !s.editable;
  return (
    <div className="settings">
      <nav className="settings-nav">
        <h2>{t('设置')}</h2>
        {LISTED.map((key) => { const [, title, icon] = SECTIONS().find((x) => x[0] === key); return (
          <button key={key} className={`nav${key === cur[0] ? ' on' : ''}`} onClick={() => go(key)}><Icon name={icon} /><span>{title}</span></button>
        ); })}
        <span className="grow" />
        <button className={`nav quiet${cur[0] === 'book' ? ' on' : ''}`} onClick={() => go('book')}><Icon name="info" /><span>{t('功能手册')}</span><kbd>F1</kbd></button>
      </nav>
      <div className="page settings-page">
        <div className="page-inner settings-inner">
          {cur[4] && <button className="back crumb" onClick={() => go(cur[4])}><Icon name="back" size={14} />{SECTIONS().find((x) => x[0] === cur[4])[1]}</button>}
          <h1 className="page-title">{cur[1]}</h1>
          <p className="page-sub">{cur[3]}</p>
          {needsConfig ? <p className="muted">{t('这个窗口没有从配置文件启动，不能在这里修改。')}</p> : (
            <>
              {cur[0] === 'services' && <Services api={api} s={s} act={act} ask={setDialog} />}
              {cur[0] === 'agent_models' && <Agents s={s} act={act} />}
              {cur[0] === 'memory' && <Memory api={api} s={s} act={act} go={go} />}
              {cur[0] === 'appearance' && <Appearance api={api} s={s} act={act} ask={setDialog} />}
              {cur[0] === 'usage' && <Usage s={s} act={act} />}
              {cur[0] === 'code' && <CodePerms s={s} act={act} />}
              {cur[0] === 'computer' && <ComputerPerms s={s} act={act} />}
              {cur[0] === 'knowledge' && <Knowledge api={api} />}
              {cur[0] === 'book' && <Book api={api} />}
            </>
          )}
        </div>
        {s.dirty && (
          <div className="save-bar">
            <Icon name="info" size={15} /><span>{t('有未保存的修改。保存后重启 Lumen 生效。')}</span>
            <span className="grow" />
            <button className="btn" onClick={revert} disabled={busy}>{t('放弃修改')}</button>
            <button className="btn primary" onClick={save} disabled={busy}>{busy ? t('正在保存……') : t('保存')}</button>
          </div>
        )}
        {toast && <div className="toast">{toast}</div>}
      </div>
      {dialog && <Ask {...dialog} close={() => setDialog(null)} />}
    </div>
  );
}
