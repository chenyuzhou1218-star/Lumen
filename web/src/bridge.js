/* The way to Python (desktop/web_chat.py): QWebChannel inside the window. Opened in an ordinary browser (to look at
   the page while making it), a stand-in answers with sample data instead, so nothing here depends on being in Lumen. */
import { mock } from './mock.js';

let ready = null;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = reject;
    document.head.append(s);
  });
}

export function bridge() {
  if (ready) return ready;
  ready = (async () => {
    if (window.qt && window.qt.webChannelTransport) {
      if (!window.QWebChannel) await loadScript('qrc:///qtwebchannel/qwebchannel.js');
      return new Promise((resolve) => {
        new window.QWebChannel(window.qt.webChannelTransport, (ch) => resolve(wrap(ch.objects.lumen)));
      });
    }
    return mock();
  })();
  return ready;
}

/* Slots answer through a callback; here every call is a promise, and JSON answers come back parsed. */
function wrap(obj) {
  const call = (name, ...args) => new Promise((resolve) => obj[name](...args, (r) => resolve(typeof r === 'string' && r ? JSON.parse(r) : r)));
  return {
    boot: () => call('boot'),
    sidebar: () => call('sidebar'),
    home: () => call('home'),
    chat: (id) => call('chat', id),
    send: (where, text) => call('send', where, text),
    estimate: (where) => call('estimate', where),
    setModel: (where, pick) => call('set_model', where, JSON.stringify(pick)),
    setLevel: (where, key) => call('set_level', where, key || ''),
    setApproval: (where, key, confirmed) => call('set_approval', where, key, !!confirmed),
    mention: (where, key, on) => call('mention', where, key, on),
    pickFiles: (where) => call('pick_files', where),
    dropFile: (where, i) => call('drop_file', where, i),
    warningAction: (i) => obj.warning_action(i),
    keepDraft: (text) => obj.keep_draft(text),
    stop: () => obj.stop(),
    resume: () => obj.resume(),
    details: (id) => obj.details(id),
    detailsJson: (id) => call('details_json', id),
    wsRows: (id, tab) => call('ws_rows', id, tab),
    wsDetail: (id, tab, i) => call('ws_detail', id, tab, i),
    wsUndo: (id) => call('ws_undo', id),
    remember: (id, text) => call('remember', id, text),
    openLink: (url) => obj.open_link(url),
    copy: (text) => obj.copy(text),
    voiceStart: () => call('voice_start'),
    voiceStop: (lang) => obj.voice_stop(lang),
    voiceCancel: () => obj.voice_cancel(),
    // the sidebar
    go: (key) => obj.go(key),
    openTask: (id) => obj.open_task(id),
    openProject: (config, task) => obj.open_project(config, task || ''),
    openFolder: () => obj.open_folder(),
    folderChats: (config) => call('folder_chats', config),
    pin: (id) => obj.pin(id),
    rename: (id, name) => obj.rename(id, name),
    hideChat: (id) => obj.hide_chat(id),
    exportChat: (id) => obj.export_chat(id),
    search: (needle) => call('search', needle),
    palette: () => obj.palette(),
    plugins: () => call('plugins'),
    settings: () => call('settings'),
    settingsForm: (id) => call('settings_form', id || ''),
    settingsAct: (action, data) => call('settings_act', action, JSON.stringify(data || {})),
    settingsSave: () => call('settings_save'),
    settingsRevert: () => call('settings_revert'),
    settingsProbe: (what, data, token) => obj.settings_probe(what, JSON.stringify(data || {}), token),
    settingsSection: (key) => obj.settings_section(key),
    knowledge: (tab, needle) => call('knowledge', tab, needle || ''),
    book: (lang) => call('book', lang || ''),
    restart: () => obj.restart(),
    replayWelcome: () => obj.replay_welcome(),
    openPlugin: (tool, id) => obj.open_plugin(tool, id || ''),
    // the browser on the right
    browserState: () => call('browser_state'),
    browserGo: (text) => obj.browser_go(text),
    browserAct: (what) => obj.browser_act(what),
    browserTab: (i) => obj.browser_tab(i),
    browserClose: (i) => obj.browser_close(i),
    browserMarks: () => call('browser_marks'),
    // the terminal on the right
    termState: () => call('term_state'),
    termInput: (text) => obj.term_input(text),
    termResize: (cols, rows) => obj.term_resize(cols, rows),
    termInterrupt: () => obj.term_interrupt(),
    termToChat: (text) => obj.term_to_chat(text),
    // room for the Qt parts, and the window's find
    slot: (name, r) => obj.slot(name, r.x, r.y, r.w, r.h),
    find: (text, back) => obj.find(text, !!back),
    back: () => obj.back(),
    closeTool: () => obj.close_tool(),
    asks: () => call('asks_now'),
    decideAsk: (id, ok) => obj.decide_ask(id, ok),
    answerAsk: (id, answers) => obj.answer_ask(id, JSON.stringify(answers)),
    foldTurn: (id, folded) => obj.fold_turn(id, folded),
    pickTool: (key) => obj.pick_tool(key),
    // before any window (desktop/web_onboarding.py)
    obCurrent: () => call('current'),
    obSetup: () => call('setup'),
    obLanguage: (code) => obj.language(code),
    obCheck: () => obj.check_engines(),
    obTest: (d) => obj.test(JSON.stringify(d)),
    obFinish: (d) => call('finish', JSON.stringify(d)),
    obProceed: () => obj.proceed(),
    obChoose: () => obj.choose_folder(),
    on: (signal, fn) => listen(obj, signal, fn),
  };
}

/* One connection per signal; pages come and go, so each listener can be taken off again. */
const listeners = {};
function listen(obj, signal, fn) {
  if (!listeners[signal]) {
    listeners[signal] = new Set();
    obj[signal].connect((text) => listeners[signal].forEach((f) => f(JSON.parse(text))));
  }
  listeners[signal].add(fn);
  return () => listeners[signal].delete(fn);
}
