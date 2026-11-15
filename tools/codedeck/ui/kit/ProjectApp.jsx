import { useCallback, useEffect, useState } from 'react';
import { call, on } from './bridge.js';
import { CodeEditor, langOf } from './CodeEditor.jsx';
import { Asker, Button, Card, Empty, Notes, Pick, Split, ask, useSize } from './controls.jsx';
import { Foot, ToolBar } from './ToolBar.jsx';
import { AIPanel } from './AIPanel.jsx';

/* The page of a tool that is otherwise a command line (app_window.py): open a project, edit its file, press a button,
   see what came out. CodeGame, CodeDeck, CodeData, CodeCAD, CodeLab and CodeFilm all draw this page; what differs comes
   from Python in boot (the tool's Config). */

export function ProjectApp() {
  const [cfg, setCfg] = useState(null);
  const [st, setSt] = useState(null);
  const [text, setText] = useState('');
  const [dirty, setDirty] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [pic, setPic] = useState(0);
  const [zoom, setZoom] = useState(false);
  const [tab, setTab] = useState('pic');  // narrow: one card at a time, the picture first

  useEffect(() => {
    const offs = [
      on('state', (ev) => setSt((s) => ({ ...s, ...ev }))),
      on('code', (ev) => { setText(ev.text); setDirty(false); }),
      on('close_ask', async () => {
        const v = await ask.confirm('保存改动吗？', '代码还没有保存。', [
          { label: '取消', value: null }, { label: '不保存', value: 'drop' }, { label: '保存', value: 'save', kind: 'primary', focus: true }]);
        if (v) call('close_window', { save: v === 'save' });
      }),
    ];
    call('boot').then((b) => {
      setCfg(b.config);
      setSt(b.state);
      setText(b.code || '');
    });
    return () => offs.forEach((f) => f());
  }, []);

  useEffect(() => { setPic(0); }, [st && st.pictures_key]);

  const edit = useCallback((v) => {
    setText(v);
    call('edit', { text: v }).then((r) => r && setDirty(!!r.dirty));
  }, []);
  const save = useCallback(() => call('save').then((r) => r && setDirty(!!r.dirty)), []);

  useEffect(() => {
    const key = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && !e.defaultPrevented) { e.preventDefault(); save(); }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [save]);

  const size = useSize();
  if (!cfg || !st) return <div className="app" />;

  const opened = !!st.opened;
  const narrow = size.w < 760;
  const run = async (i) => {
    const a = cfg.actions[i];
    let values = {};
    if (a.asks && a.asks.length) {
      values = await ask.form(a.label, a.asks, { ok: a.ok || '开始', width: 520 });
      if (!values) return;
    }
    call('run', { index: i, values });
  };
  const newProject = async () => {
    let kind = 0;
    if (cfg.new_kinds.length) {
      kind = await ask.choose('新建', cfg.new_kinds.map((k, i) => ({ label: k, value: i, icon: i ? 'file' : cfg.glyph })), '要做哪一种？');
      if (kind === null) return;
    }
    call('new', { kind });
  };
  const openAI = () => {
    if (!opened) { call('say', { text: '先打开或新建一个项目。', kind: 'error' }); return; }
    setAiOpen(true);
  };

  const ghosts = cfg.log_mode
    ? [{ key: 'log', label: '打开日志', icon: 'folder', act: () => call('open_log') }]
    : [{ key: 'new', label: '新建', icon: 'plus', tip: '新建一个项目', act: newProject },
      { key: 'open', label: '打开', icon: 'folder', tip: '打开一个项目文件夹', act: () => call('open') },
      { key: 'ai', label: '让 AI 做', icon: 'spark', tip: '让 Lumen 的团队来写这个项目', act: openAI, on: aiOpen }];
  if (cfg.add_files) ghosts.push({ key: 'add', label: '加入文件', icon: 'file', tip: '把一个文件复制进项目', act: () => call('add_file') });
  const opens = (st.opens || []).map((o, i) => ({ key: `o${i}`, label: o.label, tip: `用电脑上的程序打开 ${o.rel}`, disabled: !o.ok, act: () => call('open_rel', { rel: o.rel }) }));
  const pictures = st.pictures || [];
  const shown = pictures[Math.min(pic, pictures.length - 1)];
  const lines = text ? text.split('\n').length : 0;

  const codeCard = (
    <Card title={st.file || (cfg.log_mode ? '日志' : '代码')} icon="code" chip={dirty ? '未保存' : lines > 1 ? `${lines} 行` : ''} chipKind={dirty ? 'warn' : ''}
      tools={opened && !cfg.log_mode && <Button kind="icon" icon="save" tip="保存 · Ctrl+S" onClick={save} />}>
      {opened
        ? <CodeEditor value={text} onChange={edit} readOnly={cfg.log_mode} language={langOf(st.file)} onSave={save} follow={cfg.log_mode} />
        : cfg.log_mode
          ? <Empty icon="file" title="还没有打开日志" hint="训练程序写的日志（.log .txt .csv），打开就能看曲线和问题">
              <Button kind="primary" icon="folder" onClick={() => call('open_log')}>打开日志</Button>
            </Empty>
          : <Empty icon="folder" title="还没有打开项目" hint="新建一个，或者打开已有的项目文件夹；右上角“例子”里有现成的">
              <Button kind="primary" icon="plus" onClick={newProject}>新建</Button>
              <Button icon="folder" onClick={() => call('open')}>打开</Button>
            </Empty>}
    </Card>
  );
  const pictureCard = (
    <Card title="画面" icon="image" chip={pictures.length > 1 ? `${pictures.length} 张` : ''}
      tools={pictures.length > 1 && <Pick value={Math.min(pic, pictures.length - 1)} tip="选一张"
        options={pictures.map((p, i) => ({ value: i, label: p.name }))} onChange={setPic} />}>
      {shown
        ? <div className={`picture${zoom ? ' wide' : ''}`}>
            <img src={shown.url} alt={shown.name} draggable={false} title={zoom ? '点一下放回框里' : '点一下按宽度看'} onClick={() => setZoom(!zoom)} />
          </div>
        : <Empty icon="image" title="还没有画面" hint="点上面的按钮运行一次，做出来的图会出现在这里" />}
    </Card>
  );
  const notesCard = (
    <Card title="说明" icon="list" chip={st.notes_chip || ''} chipKind="warn">
      <Notes items={st.notes} />
    </Card>
  );

  return (
    <div className="app">
      <ToolBar glyph={cfg.glyph} name={cfg.name} project={opened ? st.project : ''} where={st.where} dirty={dirty} running={st.running}
        examples={cfg.log_mode ? [] : (cfg.examples || []).map((e) => ({ label: e.name, act: () => call('example', { path: e.path }) }))}
        ghosts={ghosts} opens={opens}
        actions={cfg.actions.map((a, i) => ({ key: `a${i}`, label: a.label, primary: a.primary, disabled: !!st.running, busy: st.running === a.label, act: () => run(i) }))} />
      <main className="body">
        {size.h > 560 && cfg.blurb && <p className="blurb">{cfg.blurb}</p>}
        {narrow
          /* thin (Lumen's tool area can be 420 wide): the picture takes the room, the code and the notes are one tap away */
          ? <div className="narrow">
              <div className="seg" role="tablist">
                {[['pic', '画面'], ['code', cfg.log_mode ? '日志' : '代码'], ['notes', '说明']].map(([k, label]) => (
                  <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
                    {label}{k === 'notes' && st.notes_chip ? <i className="dot" /> : null}
                  </button>
                ))}
              </div>
              <div className="tabcard">{tab === 'pic' ? pictureCard : tab === 'code' ? codeCard : notesCard}</div>
            </div>
          : size.h < 540 && size.w >= 1100
            // low and wide (inside Lumen, above the chat): three columns, so each keeps the whole height
            ? <Split name={`${cfg.name}:low`} first={0.38} min={300} minSecond={520}>
                {codeCard}
                <Split name={`${cfg.name}:lowright`} first={0.62} min={260} minSecond={220}>
                  {pictureCard}
                  {notesCard}
                </Split>
              </Split>
          : <Split name={`${cfg.name}:main`} first={0.45} min={300} minSecond={320}>
              {codeCard}
              <Split vertical name={`${cfg.name}:right`} first={0.7} min={150} minSecond={110}>
                {pictureCard}
                {notesCard}
              </Split>
            </Split>}
      </main>
      <Foot status={st.status} where={st.where} />
      {aiOpen && <AIPanel name={cfg.name} project={st.project} sub={cfg.ai.sub} hint={cfg.ai.hint} close={() => setAiOpen(false)} />}
      <Asker />
    </div>
  );
}
