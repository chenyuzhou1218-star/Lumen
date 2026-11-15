/* Sample answers for opening the page outside Lumen: the same shapes desktop/web_chat.py sends.
   ?page=home|chat|running|plugins|settings|details  &lang=en  &tool=1  &side=closed */
const q = new URLSearchParams(location.search);

const box = () => ({
  model: q.get('long') ? 'Claude Code · Opus 5.5 (1M context)' : 'Claude Code · Haiku 5.5', pick: { engine: 'claude_code', id: 'claude-haiku-5-5' }, level: q.get('long') ? 'high' : 'medium', approval: 'ask', computer: !!q.get('pc'),
  levels: [['low', '低'], ['medium', '中等'], ['high', '高'], ['xhigh', '超高'], ['max', '最高']].map(([key, name]) => ({ key, name })),
  models: [['Claude Code', 'Opus 5.5', 'claude-opus-5-5'], ['Claude Code', 'Sonnet 5.5', 'claude-sonnet-5-5'], ['Claude Code', 'Fable 5.2', 'claude-fable-5-2'],
    ['Claude Code', 'Haiku 5.5', 'claude-haiku-5-5'], ['Codex', 'GPT-5.6 Luna', 'gpt-5.6-luna']]
    .map(([group, label, id]) => ({ group, label, pick: { engine: group === 'Codex' ? 'codex' : 'claude_code', id, model: `${group} · ${label}` } })),
  mentions: [], files: [], running: false,
});

const steps = [
  { kind: 'thought', text: '先看看页面现在的结构，再决定改哪里。' },
  { kind: 'tool', tool: 'read_file', text: '读取 web/src/App.jsx', ok: true },
  { kind: 'tool', tool: 'search_text', text: '搜索 “composer”', ok: true },
  { kind: 'tool', tool: 'edit_file', text: '修改 web/src/Composer.jsx  （-12 +40 行）', ok: true },
  { kind: 'test', text: '系统自动跑测试：12 passed', ok: true },
];

const answer = `做好了。改了两处：

1. **输入框**：按 \`Enter\` 发送，\`Shift+Enter\` 换行；粘贴图片会变成附件。
2. **模型菜单**：分组显示，当前的打了勾。

\`\`\`js
function send(text) {
  if (!text.trim()) return;
  bridge.send('home', text);
}
\`\`\`

| 文件 | 改动 |
| --- | --- |
| Composer.jsx | +40 −12 |
| styles.css | +18 |

测试全部通过。`;

const chat = (running) => ({
  chat_id: 'c1', task_id: 't2', title: '把输入框改得顺手一点', running, resumable: false,
  box: { ...box(), running },
  turns: [
    { id: 't1', question: '把输入框改得顺手一点：回车发送，还要能选模型。', at: '2026-11-10T09:12:00', who: 'Claude Code · Haiku 5.5 · 中等', state: 'finished', outcome: 'done', status: '完成',
      answer, steps, members: [], elapsed: '1 分 12 秒', tokens: 18432, tools: [], needs: [] },
    { id: 't2', question: '再让 Prism 检查一遍有没有漏掉的地方。', at: '2026-11-10T09:15:00', who: 'Claude Code · Haiku 5.5 · 中等', state: running ? 'running' : 'finished', outcome: running ? null : 'done',
      status: running ? '进行中' : '完成', answer: running ? '' : '检查过了，没有发现问题。', elapsed: '24 秒', tokens: 5120, tools: [], needs: [],
      steps: steps.slice(0, 2),
      members: [{ id: 'm1', agent: 'prism', name: 'Prism', cn: '棱镜', job: '检查', colour: '#8B5CF6', avatar: '', from: 'Lumen',
        ask: '检查 web/src/Composer.jsx 的回车和输入法：中文输入时按回车不应该发送。', review: false, state: running ? 'running' : 'finished',
        outcome: running ? null : 'done', status: running ? '进行中' : '完成', answer: running ? '' : '输入法组字时按回车不会发送，已经处理了。', steps: steps.slice(1, 3) }] },
  ],
});

const titles = ['把输入框改得顺手一点', '首页的动画太慢了，帮我调快', '查一下为什么测试在 CI 上超时', '给设置页加一个“外观”分组',
  '把 README 翻译成英文', '整理一下 docs 目录', '修复深色模式下代码块看不清', '写一个导出 CSV 的脚本', '对比两个版本的性能',
  '帮我做一个 3D 的小台灯模型', '剪一段 30 秒的产品视频', '这个报错是什么意思：ECONNRESET'];

let mockLine = '';
const OB = { tagline: '顺着逻辑，找到真正要紧的问题。', skip: '跳过动画', enter: '进入 Lumen', lang_title: '选择语言', language: '语言', pick_ai_title: '选择用哪些 AI', pick_ai_sub: '可以选好几个；发问题时随时换。以后在设置里也能改。',
  engine_checking: '正在检查……', use_claude_code_sub: '用你自己的 Claude Code（你的 Claude 订阅）', use_codex_sub: '用你自己的 Codex（你的 ChatGPT 订阅）', use_api: '用 API 密钥',
  use_api_sub: 'DeepSeek、通义、OpenAI 等，按用量付费', service: '服务', address: '地址', api_key: 'API 密钥', key_hint: '密钥只保存在本机的 Windows 凭据管理器。',
  no_key_needed: '本机服务，不需要密钥。', model: '模型', model_hint: '点“测试”列出这个服务的模型', test: '测试', testing: '正在测试……', let_fix: '让 Agent 直接修改代码',
  let_fix_sub: '改动前会先拍快照，随时一键撤回。', default_ai: '由 {0} 来做（每次发问题都能换）', back: '上一步', next: '下一步', start_using: '开始使用', open_folder: '打开文件夹…', open_failed_any: '没能打开文件夹。' };

export function mock() {
  const listeners = {};
  const emit = (signal, value) => (listeners[signal] || []).forEach((fn) => fn(value));
  const page = q.get('page') || 'home';
  const side = {
    chats: titles.map((title, i) => ({ id: `c${i + 1}`, title, open: i === 0 ? 't2' : `t${i + 10}`, running: i === 2 })),
    pins: ['c2'], selected: page === 'chat' || page === 'running' ? 'c1' : null,
    folders: [{ name: 'my-site', config: 'D:/work/my-site/codedoctor.toml', root: 'D:/work/my-site', here: true },
      { name: 'shop-backend', config: 'D:/work/shop/codedoctor.toml', root: 'D:/work/shop', here: false },
      { name: '毕业论文', config: 'D:/docs/thesis/codedoctor.toml', root: 'D:/docs/thesis', here: false }],
    keys_missing: q.get('keys') ? ['DeepSeek'] : [], docks: (q.get('dock') || '').split(',').filter(Boolean),
  };
  const first = page === 'home' ? { page: 'home' } : page === 'chat' || page === 'running' ? { page: 'chat', task_id: 't2' }
    : page === 'details' ? { page: 'chat', task_id: 't2', details: 't2' } : page === 'plugins' ? { page: 'plugins' } : { page: 'native', key: page };
  setTimeout(() => {
    emit('show', first);
    if (q.get('tool')) emit('tool', { on: true, name: 'CodeCut', state: q.get('tool') === 'ask' ? 'starting' : q.get('tool'),
      ask: q.get('tool') === 'ask' ? 'CodeCut 要在这个项目里改文件、运行它自己的命令，才能替你做出来。允许以后窗口会重新打开一次。' : '', why: '这个工具没有打开（它的窗口没有出来）。' });
  }, 30);
  const b = box();
  const show = (v) => { side.selected = v.page === 'chat' ? 'c1' : null; emit('show', v); emit('side', { ...side }); };
  const sideChanged = () => emit('side', JSON.parse(JSON.stringify(side)));
  return {
    boot: async () => ({ texts: OB, welcome: { tagline: OB.tagline, skip: OB.skip, enter: OB.enter }, lang: q.get('lang') || 'zh', catalog: q.get('lang') === 'en' ? await fetch('../locale/en.json').then((r) => r.json()).catch(() => ({})) : {},
      prefs: { font_size: 'normal', corners: 'round', chat_width: 'normal', send_key: 'enter', show_times: true, expand_steps: true, show_tokens: true,
        reduced_motion: false, accent: 'amber', mode: q.get('mode') || 'light', term_font: 13, accent_colours: ['#ef8a17', '#d67708', '#fff2df', '#ffb454'] }, project: 'my-site' }),
    sidebar: async () => JSON.parse(JSON.stringify(side)),
    home: async () => ({ project: 'my-site', lumen: '../assets/team/lumen.png', warnings: q.get('keys') ? [{ text: 'DeepSeek 还没有 API 密钥，用到它的 Agent 调用模型时会停下并提示。', act: '' }] : [], box: b, draft: '',
      tools: ['CodePage', 'Code3D', 'CodeCut', 'CodeGame', 'CodeDeck'].map((name) => ({ key: name.toLowerCase(), name })) }),
    chat: async () => ({ ...chat(page === 'running'), lumen: '../assets/team/lumen.png' }),
    send: async () => ({ ok: true }), estimate: async () => ({ typical: 420000, count: 6, limit: 300000 }), setModel: async (w, pick) => ({ ...b, pick, model: pick.model }), setLevel: async (w, level) => ({ ...b, level }),
    setApproval: async (w, approval) => ({ ...b, approval }), mention: async () => b, pickFiles: async () => b, dropFile: async () => b,
    warningAction: () => {}, keepDraft: () => {},
    stop: () => {}, resume: () => {}, details: () => show({ page: 'chat', task_id: 't2', details: 't2' }), openLink: (u) => window.open(u),
    copy: (t) => navigator.clipboard && navigator.clipboard.writeText(t),
    voiceStart: async () => true, voiceStop: () => setTimeout(() => emit('heard', { text: '帮我做出来' }), 600), voiceCancel: () => {},
    go: (key) => {
      if (key === 'browser' || key === 'terminal') { side.docks = side.docks.includes(key) ? side.docks.filter((d) => d !== key) : [...side.docks, key]; sideChanged(); return; }
      show(key === 'home' ? { page: 'home' } : key === 'plugins' ? { page: 'plugins' } : { page: 'native', key: 'settings' });
    },
    openTask: () => show({ page: 'chat', task_id: 't2' }), openProject: () => {}, openFolder: () => {},
    folderChats: async (config) => (config.includes('shop') ? ['订单接口返回 500', '加一个优惠券表', '数据库迁移脚本'] : ['第三章的文献综述'])
      .map((title, i) => ({ id: `o${i}`, title, open: `o${i}`, running: false })),
    pin: (id) => { side.pins = side.pins.includes(id) ? side.pins.filter((p) => p !== id) : [id, ...side.pins]; sideChanged(); },
    rename: (id, name) => { const c = side.chats.find((x) => x.id === id); if (c && name.trim()) c.title = name.trim(); sideChanged(); },
    hideChat: (id) => { side.chats = side.chats.filter((c) => c.id !== id); sideChanged(); },
    exportChat: () => {},
    search: async (needle) => (needle.length < 2 ? [] : [{ task: 't2', title: '把输入框改得顺手一点', snippet: `……按 Enter 发送，${needle} 换行……` }]),
    palette: () => {},
    termState: async () => ({ log: 'Windows PowerShell 5.1\r\n版权所有 (C) Microsoft Corporation。保留所有权利。\r\n\r\nPS D:\work\my-site> ', alive: true,
      ran: [{ who: 'Spark', command: 'npm test' }] }),
    termInput: (data) => {
      const ls = '\r\n\r\n    目录: D:\work\my-site\r\n\r\nMode                 LastWriteTime         Length Name\r\n----                 -------------         ------ ----\r\nd-----        2026/11/10      9:12                src\r\n-a----        2026/11/10      9:15            412 index.html\r\n\r\n';
      mockLine = data === '\r' ? (setTimeout(() => emit('term', { out: (mockLine.trim() === 'ls' ? ls : '\r\n') + 'PS D:\work\my-site> ' }), 60), '') : mockLine + data;
      if (data !== '\r') emit('term', { out: data === '\x7f' ? '\b \b' : `\x1b[93m${data}\x1b[0m` });
    },
    termResize: () => {},
    termInterrupt: () => {}, termToChat: () => {},
    browserState: async () => (q.get('web') ? { tabs: [{ title: 'Qt for Python', url: 'https://doc.qt.io/qtforpython-6/', agent: false },
      { title: 'Ray 在用', url: 'https://www.bing.com/search?q=xterm.js', agent: true }], current: 0, url: 'https://doc.qt.io/qtforpython-6/', blank: false,
      back: true, forward: false, starred: true, loading: false,
      ray: { task: 't9', state: 'Ray 查完了', done: true, answer: 'xterm.js 是 **VS Code** 用的终端显示组件，[官网](https://xtermjs.org)。' } }
      : { tabs: [{ title: '新标签页', url: '', agent: false }], current: 0, url: '', blank: true, back: false, forward: false, starred: false, loading: false, ray: { task: null } }),
    knowledge: async (tab) => ({ stats: { supported: 3, proposed: 1, refuted: 0, notes: 12 }, total: 2, shown: 150, rows: tab === 'notes'
      ? [{ kind: '决定', text: '输入框按 Enter 发送，Shift+Enter 换行。', id: 'n1', meta: ['lumen', '项目共享', '2026-11-10 09:12'] }]
      : [{ status: 'supported', kind: '成立', level: '已复现', text: '断线重连后 settle 会被重放，奖励会重复发放。', id: 'c1', meta: ['prism', '证据 3 条', 't2'] },
        { status: 'proposed', kind: '待验证', level: '推断', text: 'CI 超时来自没有缓存 node_modules。', id: 'c2', meta: ['spark', '证据 1 条'] }] }),
    book: async (lang) => ({ lang: lang || 'zh', langs: [{ value: 'zh', label: '简体中文' }, { value: 'en', label: 'English' }],
      text: ['# Lumen 功能手册', '', '## 聊天', '', '- 按 **Enter** 发送', '- 用 `@` 叫工具', '', '## 浏览器和终端', '', '右边可以同时打开。'].join('\n') }),
    detailsJson: async () => ({ task_id: 't2', status: '完成 · 测试未全过', info: '1 分 12 秒 · token 18,432', cached: 120000, picture: '',
      escalations: ['审批被拒绝\n监督员拒绝了 git push：先跑完测试。'],
      sections: [
        { key: 'changes', title: '改动清单', chips: [{ text: '有 1 个测试没通过', tone: 'bad' }], note: 'test_composer_enter · 系统共跑了 3 次测试',
          rows: [{ cells: [{ text: 'web/src/Composer.jsx', mono: true }, { text: '+40', tone: 'good' }, { text: '-12', tone: 'bad' }, { text: 'spark' }] },
            { cells: [{ text: 'web/src/styles.css', mono: true }, { text: '+18', tone: 'good' }, { text: '-0', tone: 'bad' }, { text: 'spark' }] }], items: [] },
        { key: 'anomalies', title: '异常与首脑决策', chips: [{ text: '马上修 1', tone: 'bad' }, { text: '已解决 2', tone: 'good' }], note: '零遗漏：Agent 发现的任何异常都会写进首脑的收件箱；重大的立即唤醒首脑。',
          items: [{ chips: [{ text: '马上修', tone: 'bad' }, { text: '逻辑' }, { text: '重大', tone: 'bad' }], title: '中文输入法组字时按回车会发送', sub: '表面 小 · 耦合影响 大 → 马上修（P0） · 上报：prism', folded: true,
            lines: [{ text: '观察到：按回车时 isComposing 没有检查。' }, { text: '位置：web/src/Composer.jsx:72', tone: 'quiet' }] }] },
        { key: 'claims', title: '结论（2）', note: '只有“成立”是经过独立复查的事实', items: [
          { chips: [{ text: '成立', tone: 'good' }, { text: '已复现' }], title: '回车会在组字时提前发送。', sub: 'clm_01', lines: [{ text: '提出者 prism · 证据 3 条 · 复查：beacon 同意' }] },
          { chips: [{ text: '待验证', tone: 'warn' }, { text: '推断' }], title: '粘贴图片会变成附件。', sub: 'clm_02', lines: [{ text: '提出者 spark · 证据 1 条 · 复查：还没有独立复查' }] }] }] }),
    wsRows: async (id, tab) => ({ note: tab === 'changes' ? '调查开始以来（开始 → 结束）：新增 0、修改 2、删除 0 个文件。' : '', undo: tab === 'changes',
      rows: tab === 'changes' ? [{ text: 'web/src/Composer.jsx', mark: '~', tone: 'warn' }, { text: 'web/src/styles.css', mark: '~', tone: 'warn' }]
        : [{ text: 'spark  读取 web/src/App.jsx', mark: '✓', at: '09:12' }, { text: 'spark  修改 web/src/Composer.jsx', mark: '✓', at: '09:13' }] }),
    wsDetail: async () => ({ diff: '@@ -70,3 +70,4 @@\n   const key = (e) => {\n-    if (e.key === \'Enter\') {\n+    if (e.key !== \'Enter\' || e.nativeEvent.isComposing) return;\n+    send();' }),
    wsUndo: async () => ({ ok: true, restored: 2, removed: 0, skipped: 0, lines: [] }), remember: async () => ({ ok: true }),
    browserGo: () => {}, browserAct: () => {}, browserTab: () => {}, browserClose: () => {},
    browserMarks: async () => [{ title: 'Qt for Python', url: 'https://doc.qt.io/qtforpython-6/' }],
    plugins: async () => ({"big": [{"key": "codefilm", "name": "CodeFilm", "about": "把剧本、素材和配音做成一段成片"}, {"key": "codesound", "name": "CodeSound", "about": "写歌、配乐、做音效"}, {"key": "codepage", "name": "CodePage", "about": "做网页和小网站，边改边看"}, {"key": "codegame", "name": "CodeGame", "about": "做能玩的小游戏"}, {"key": "code3d", "name": "Code3D", "about": "用 Blender 做 3D 模型和场景"}, {"key": "codecut", "name": "CodeCut", "about": "剪视频：粗剪、字幕、配乐"}, {"key": "codedeck", "name": "CodeDeck", "about": "做演示文稿"}, {"key": "codedata", "name": "CodeData", "about": "表格和数据：清理、算、画图"}, {"key": "codecad", "name": "CodeCAD", "about": "做能打印的零件"}, {"key": "codelab", "name": "CodeLab", "about": "做实验、跑模拟"}], "groups": [{"name": "创作", "glyph": "创作", "items": [{"id": "logo", "name": "标志设计", "about": "从名字做出标志，SVG 和 PNG 都有"}, {"id": "anim", "name": "小动画", "about": "文字动画和会动的图表，出 GIF"}, {"id": "diagram", "name": "流程图和导图", "about": "用文字写，自动排版成图"}]}, {"name": "开发", "glyph": "开发", "items": [{"id": "apitest", "name": "接口测试", "about": "一行一个请求，查状态码和返回内容"}, {"id": "sqlite", "name": "数据库查看", "about": "只读打开 SQLite，看表、查询、导出 CSV"}, {"id": "logs", "name": "日志分析", "about": "把几万行日志归成几种错误，按时间画出来"}]}, {"name": "文件", "glyph": "文件", "items": [{"id": "images", "name": "批量修图", "about": "一次缩小、转格式、加水印，或拼成一页。原图不动"}, {"id": "pdf", "name": "PDF 工具", "about": "提取文字，转成图片，图片合成 PDF"}, {"id": "tidy", "name": "整理文件夹", "about": "先看计划再动手，随时能撤销，绝不删除"}]}, {"name": "科学", "glyph": "科学", "items": [{"id": "calc", "name": "精确计算", "about": "分数不丢精度，能画函数，能换单位"}, {"id": "circuit", "name": "电路计算", "about": "解直流电路的电压电流，算 RC 充电"}, {"id": "logic", "name": "逻辑验证", "about": "穷举所有情况，判断命题是否恒真，给出反例"}]}, {"name": "写作", "glyph": "写作", "items": [{"id": "book", "name": "写书助手", "about": "查长篇的人物、字数、重复，做成电子书"}, {"id": "subtitle", "name": "字幕工具", "about": "整体平移、查错、从台词生成字幕"}, {"id": "translate", "name": "译文检查", "about": "查漏译、术语不一致、数字和占位符丢失"}]}, {"name": "游戏", "glyph": "游戏", "items": [{"id": "world", "name": "世界地图", "about": "生成地形、河流和城市，给游戏用的高度图和数据"}, {"id": "balance", "name": "数值平衡", "about": "让兵种成千上万次对打，找出太强太弱；模拟经济曲线"}, {"id": "film", "name": "短片合成", "about": "图片加字幕加音乐，用 CodeCut 导出成 MP4"}]}], "done": true, "glyphs": {"codefilm": "<rect x=\"2\" y=\"2.6\" width=\"12\" height=\"10.8\" rx=\"1.4\"/><path d=\"M4.8 2.6v10.8M11.2 2.6v10.8M2 5.4h2.8M2 8h2.8M2 10.6h2.8M11.2 5.4H14M11.2 8H14M11.2 10.6H14\"/>", "codesound": "<path d=\"M6 12.2V3.4l7-1.4v8.6\"/><circle cx=\"4.4\" cy=\"12.2\" r=\"1.7\"/><circle cx=\"11.4\" cy=\"10.6\" r=\"1.7\"/>", "codepage": "<rect x=\"2.2\" y=\"2.2\" width=\"11.6\" height=\"11.6\" rx=\"1.4\"/><path d=\"M2.2 6h11.6M6.4 6v7.8\"/>", "codegame": "<rect x=\"1.8\" y=\"4.6\" width=\"12.4\" height=\"7.4\" rx=\"3.6\"/><path d=\"M5 7.4v2M4 8.4h2\"/><circle cx=\"10.6\" cy=\"7.8\" r=\".6\"/><circle cx=\"11.8\" cy=\"9.2\" r=\".6\"/>", "code3d": "<path d=\"m8 1.8 5.4 3.1v6.2L8 14.2l-5.4-3.1V4.9Z\"/><path d=\"m2.6 4.9 5.4 3.1 5.4-3.1M8 8v6.2\"/>", "codecut": "<circle cx=\"4.4\" cy=\"11.6\" r=\"2\"/><circle cx=\"11.6\" cy=\"11.6\" r=\"2\"/><path d=\"M5.7 10 11.8 2.4M10.3 10 4.2 2.4\"/>", "codedeck": "<rect x=\"1.8\" y=\"2.6\" width=\"12.4\" height=\"8.6\" rx=\"1.2\"/><path d=\"M8 11.2v2.4M5.6 13.6h4.8M4.6 8.4l2.2-2.2 1.6 1.4 2.6-2.6\"/>", "codedata": "<path d=\"M2.4 13.6h11.2\"/><rect x=\"3.4\" y=\"8\" width=\"2.2\" height=\"4.4\" rx=\".5\"/><rect x=\"6.9\" y=\"4.6\" width=\"2.2\" height=\"7.8\" rx=\".5\"/><rect x=\"10.4\" y=\"6.6\" width=\"2.2\" height=\"5.8\" rx=\".5\"/>", "codecad": "<rect x=\"1.8\" y=\"5.2\" width=\"12.4\" height=\"5.6\" rx=\"1\"/><path d=\"M4.4 5.2v2.2M7 5.2v3M9.6 5.2v2.2M12.2 5.2v3\"/>", "codelab": "<path d=\"M6 1.8h4M6.6 1.8v4.4L2.8 12.4c-.4.7.1 1.6.9 1.6h8.6c.8 0 1.3-.9.9-1.6L9.4 6.2V1.8\"/><path d=\"M4.4 10h7.2\"/>", "创作": "<path d=\"M8 1.8 9.4 6.6 14.2 8 9.4 9.4 8 14.2 6.6 9.4 1.8 8 6.6 6.6Z\"/>", "写作": "<path d=\"M10.6 2.6 13.4 5.4 6 12.8l-3.4.6.6-3.4Z\"/><path d=\"M9.2 4 12 6.8\"/>", "文件": "<path d=\"M1.8 4.4c0-.6.4-1 1-1h3.1l1.5 1.5h5.8c.6 0 1 .4 1 1v6.2c0 .6-.4 1-1 1H2.8c-.6 0-1-.4-1-1Z\"/>", "开发": "<path d=\"m5.4 4.6-3.4 3.4 3.4 3.4\"/><path d=\"m10.6 4.6 3.4 3.4-3.4 3.4\"/><path d=\"m9 2.8-2 10.4\"/>", "科学": "<path d=\"M6 1.8h4M6.6 1.8v4.4L2.8 12.4c-.4.7.1 1.6.9 1.6h8.6c.8 0 1.3-.9.9-1.6L9.4 6.2V1.8\"/><path d=\"M4.4 10h7.2\"/>", "游戏": "<rect x=\"1.8\" y=\"4.6\" width=\"12.4\" height=\"7.4\" rx=\"3.6\"/><path d=\"M5 7.4v2M4 8.4h2\"/><circle cx=\"10.6\" cy=\"7.8\" r=\".6\"/><circle cx=\"11.8\" cy=\"9.2\" r=\".6\"/>", "search": "<circle cx=\"7\" cy=\"7\" r=\"4.4\"/><path d=\"m10.3 10.3 3.3 3.3\"/>"}}),
    openPlugin: () => {},
    slot: () => {}, closeTool: () => {}, foldTurn: () => {}, pickTool: () => {}, find: (text) => setTimeout(() => emit('found', { count: text ? 3 : 0, at: text ? 1 : 0 }), 50), back: () => show({ page: 'chat', task_id: 't2' }),
    obCurrent: async () => ({ page: q.get('ob') || 'welcome', title: '没能打开 my-site。', why: 'PermissionError: [WinError 5] 拒绝访问。' }),
    obSetup: async () => ({ lang: 'zh', langs: [['zh', '简体中文'], ['en', 'English'], ['fr', 'Français'], ['es', 'Español'], ['pt', 'Português'],
      ['de', 'Deutsch'], ['ja', '日本語'], ['ko', '한국어'], ['ru', 'Русский'], ['it', 'Italiano']].map(([value, label]) => ({ value, label })),
      texts: OB, presets: [{ id: 'deepseek', name: 'DeepSeek', kind: 'openai_compatible', base_url: 'https://api.deepseek.com/v1', local: false },
        { id: 'ollama', name: 'Ollama（本机）', kind: 'openai_compatible', base_url: 'http://localhost:11434/v1', local: true }],
      engines: [{ name: 'claude_code', title: 'Claude Code', status: 'ready', text: '已安装，已登录' }, { name: 'codex', title: 'Codex', status: 'login', text: '已安装，还没登录：在终端运行 codex login 登录一次' }] }),
    obLanguage: () => {}, obCheck: () => {}, obTest: () => {}, obFinish: async () => ({ ok: true }), obProceed: () => {}, obChoose: () => {},
    on: (signal, fn) => { (listeners[signal] = listeners[signal] || []).push(fn); return () => { listeners[signal] = listeners[signal].filter((f) => f !== fn); }; },
  };
}
