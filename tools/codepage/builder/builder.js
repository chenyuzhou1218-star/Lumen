/* The builder: components on the left, the page in the middle, what is selected on the right.
   The canvas is an iframe, so that phone widths really trigger the page's own rules. Dragging is done by hand with mouse events:
   a browser's built-in drag does not cross into an iframe the same way in every engine. */
'use strict';

const $ = (id) => document.getElementById(id);
const canvas = $('canvas');
let page = null;
let selected = null;   // a node id
let history = [];
let future = [];
let bridge = null;     // the Python window, when there is one (editor.py)
let imageTarget = null;
let lastSaved = '';
let dirty = false;     // changes the file does not have yet
let tab = 'parts';
const shut = new Set();       // component groups folded away
const shutSecs = new Set();   // inspector sections folded away

const STORE = 'codepage-work';
const FOLD = 'codepage-folds';

/* Small line icons for each kind of component, drawn the same way as the builder's own. */
const KIND = {
  layout: '<rect x="2.2" y="2.6" width="11.6" height="10.8" rx="1.4"/><path d="M8 2.6v10.8"/>',
  nav: '<path d="M2.4 4.4h11.2M2.4 8h11.2M2.4 11.6h7"/>',
  search: '<circle cx="7" cy="7" r="4.2"/><path d="m10.2 10.2 3.2 3.2"/>',
  hero: '<rect x="2.2" y="2.6" width="11.6" height="10.8" rx="1.4"/><path d="M5 6.4h6M6 9.2h4"/>',
  text: '<path d="M3.2 3.6h9.6M8 3.6v9"/>',
  button: '<rect x="2" y="5" width="12" height="6" rx="3"/>',
  media: '<rect x="2" y="2.6" width="12" height="10.8" rx="1.4"/><circle cx="5.8" cy="6.2" r="1.1"/><path d="m2.4 12 3.6-3.3 2.4 2.1 2-1.7 3.2 2.8"/>',
  card: '<rect x="2.6" y="2.2" width="10.8" height="11.6" rx="1.4"/><path d="M2.6 7.4h10.8M4.8 10h4.4"/>',
  form: '<rect x="2.2" y="3" width="11.6" height="3.6" rx="1"/><rect x="2.2" y="9.4" width="7" height="3.6" rx="1"/>',
  more: '<circle cx="4" cy="8" r="1"/><circle cx="8" cy="8" r="1"/><circle cx="12" cy="8" r="1"/>',
  footer: '<rect x="2.2" y="2.6" width="11.6" height="10.8" rx="1.4"/><path d="M2.2 10h11.6"/>',
  feature: '<rect x="2.2" y="3" width="3.2" height="3.2" rx=".8"/><rect x="6.4" y="3" width="3.2" height="3.2" rx=".8"/><rect x="10.6" y="3" width="3.2" height="3.2" rx=".8"/><path d="M2.4 10h3M6.6 10h3M10.8 10h3M2.4 12.4h2.2M6.6 12.4h2.2M10.8 12.4h2.2"/>',
  stat: '<path d="M2.6 13.4h10.8M4.6 11V8M8 11V4.6M11.4 11V6.6"/>',
  content: '<rect x="2" y="3.4" width="5.6" height="9.2" rx="1"/><path d="M9.6 5h4.4M9.6 7.8h4.4M9.6 10.6h3"/>',
  proof: '<path d="M3 4.2h10v6.4H7.4L4.6 13v-2.4H3z"/>',
  team: '<circle cx="6" cy="6" r="2.2"/><path d="M2.4 13c.4-2.2 1.8-3.4 3.6-3.4s3.2 1.2 3.6 3.4"/><circle cx="11.2" cy="6.4" r="1.7"/><path d="M11.2 9.8c1.4 0 2.3.9 2.6 2.6"/>',
  price: '<path d="M8.6 2.4H13.6v5L7.4 13.6 2.4 8.6z"/><circle cx="10.8" cy="5.2" r=".9"/>',
  faq: '<circle cx="8" cy="8" r="5.6"/><path d="M6.4 6.4a1.7 1.7 0 1 1 2.3 1.6c-.5.2-.7.6-.7 1.1v.3M8 11.3v.1"/>',
  step: '<circle cx="3.6" cy="8" r="1.4"/><circle cx="8" cy="8" r="1.4"/><circle cx="12.4" cy="8" r="1.4"/><path d="M5 8h1.6M9.4 8H11"/>',
  cta: '<rect x="2" y="5" width="12" height="6" rx="3"/><path d="m8.6 6.6 1.4 1.4-1.4 1.4"/>',
  contact: '<path d="M2.6 4.2h10.8v7.6H2.6z"/><path d="m2.8 4.6 5.2 4 5.2-4"/>',
  play: '<circle cx="8" cy="8" r="5.6"/><path d="m6.8 5.8 3.4 2.2-3.4 2.2z"/>',
  logo: '<circle cx="4.6" cy="8" r="2"/><rect x="8.6" y="6" width="5" height="4" rx="1"/>',
  notice: '<path d="M4.4 11V7.4a3.6 3.6 0 0 1 7.2 0V11l1 1H3.4z"/><path d="M6.8 13.6h2.4"/>',
  slides: '<rect x="2" y="3.2" width="12" height="7.6" rx="1.2"/><path d="M8 10.8v2.4M5.6 13.6h4.8"/>',
};
const kindOf = {};  // component id -> category id

function icon(name) {
  return `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

function kindIcon(cat) {
  return `<svg viewBox="0 0 16 16" aria-hidden="true">${KIND[cat] || KIND.more}</svg>`;
}

function blankPage() {
  const t = CP.lib.themes[0];
  return { title: '我的网页', lang: 'zh-CN', description: '', theme: { ...t, radius: 10, font: CP.lib.fonts[0].css }, blocks: [] };
}

function newId() {
  return 'n' + Math.random().toString(36).slice(2, 9);
}

function makeNode(type) {
  const item = CP.byId[type];
  const values = {};
  for (const f of item.fields || []) values[f.key] = f.value;
  const node = { id: newId(), type, values, style: {} };
  if (item.slides) node.children = (item.kids || [[]]).map((ids) => ids.filter((t) => CP.byId[t]).map(makeNode));  // a deck starts with its slides filled in
  else if (item.slots) node.children = Array.from({ length: item.slots }, () => []);
  return node;
}

/* --- finding things ---------------------------------------------------------------------------------------------------- */

function findNode(id, list = page.blocks) {
  for (let i = 0; i < list.length; i++) {
    if (list[i].id === id) return { node: list[i], list, index: i };
    for (const inner of list[i].children || []) {
      const hit = findNode(id, inner);
      if (hit) return hit;
    }
  }
  return null;
}

function listOf(slot) {
  if (!slot) return page.blocks;
  const [id, i] = slot.split(':');
  const hit = findNode(id);
  return hit ? hit.node.children[Number(i)] : page.blocks;
}

function contains(node, id) {
  if (node.id === id) return true;
  return (node.children || []).some((list) => list.some((n) => contains(n, id)));
}

function countBlocks(list = page.blocks) {
  let n = 0;
  for (const b of list) {
    n += 1;
    for (const inner of b.children || []) n += countBlocks(inner);
  }
  return n;
}

function nameOf(node) {
  return (CP.byId[node.type] || {}).name || node.type;
}

function hintOf(node) {
  /* The first words a person typed into the block: how they tell two blocks of the same kind apart. */
  const item = CP.byId[node.type] || {};
  for (const f of item.fields || []) {
    if (f.type !== 'text' && f.type !== 'lines') continue;
    const v = String((node.values || {})[f.key] || '').split('\n')[0].split('|').find((p) => p.trim() && !/^[#@]|^https?:/.test(p.trim()));
    if (v) return v.trim();
  }
  return '';
}

/* --- changes and history ----------------------------------------------------------------------------------------------- */

function remember() {
  dirty = true;
  history.push(JSON.stringify(page));
  /* whole pages with pictures inside are big: keep 100 steps, but no more than about 40 MB of them */
  let bytes = history.reduce((n, h) => n + h.length, 0);
  while (history.length > 100 || (bytes > 40e6 && history.length > 1)) bytes -= history.shift().length;
  future = [];
}

function changed() {
  draw();
  panel();
  fillLayers();
  clearTimeout(changed.keep);
  changed.keep = setTimeout(() => {
    try { localStorage.setItem(STORE, JSON.stringify(page)); } catch (e) { /* a big picture does not fit: the file still saves */ }
  }, 800);
  buttons();
}

function buttons() {
  $('undo').disabled = !history.length;
  $('redo').disabled = !future.length;
  const s = $('saved');
  if (bridge) {
    s.textContent = dirty ? '未保存' : (lastSaved ? '已保存' : '');
    s.classList.toggle('dirty', dirty);
  } else {
    s.textContent = '自动存在这个浏览器里';
    s.classList.remove('dirty');
  }
  const n = countBlocks();
  $('stageCount').textContent = n ? `${n} 个组件` : '';
}

function undo() {
  if (!history.length) return;
  future.push(JSON.stringify(page));
  page = JSON.parse(history.pop());
  dirty = true;
  if (selected && !findNode(selected)) selected = null;  // what was selected stays selected, if it is still there
  changed();
}

function redo() {
  if (!future.length) return;
  history.push(JSON.stringify(page));
  page = JSON.parse(future.pop());
  dirty = true;
  if (selected && !findNode(selected)) selected = null;
  changed();
}

/* --- the canvas -------------------------------------------------------------------------------------------------------- */

const TOOL_ICON = {
  up: '<path d="M8 12.8V3.4M4.3 7 8 3.3 11.7 7"/>',
  down: '<path d="M8 3.2v9.4M4.3 9 8 12.7 11.7 9"/>',
  copy: '<rect x="5.4" y="5.4" width="8" height="8" rx="1.3"/><path d="M10.6 3.3a.8.8 0 0 0-.8-.7H3.4a.8.8 0 0 0-.8.8v6.4c0 .4.3.8.7.8"/>',
  del: '<path d="M2.6 4.4h10.8M6.4 2.5h3.2M4 4.4l.7 8.3c0 .5.5.8 1 .8h4.6c.5 0 1-.3 1-.8l.7-8.3"/>',
  parent: '<path d="M6 12.6V5.4h7.2"/><path d="M9.8 2.2 13.2 5.4 9.8 8.6"/>',
};

function toolSvg(name) {
  return `<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">${TOOL_ICON[name]}</svg>`;
}

/* i18n.py puts window.__tr in (the words in Lumen's language); the canvas is a page of its own, so its few words go through it here */
const TR = (s) => (window.__tr ? window.__tr(s) : s);
const trWords = (html) => html.replace(/>([^<>]*[\u4e00-\u9fff][^<>]*)</g, (m, t) => `>${TR(t)}<`);
const trContent = (css) => css.replace(/content:'([^']*[\u4e00-\u9fff][^']*)'/g, (m, t) => `content:'${TR(t)}'`).replace(/' ([\u4e00-\u9fff]+)'/g, (m, t) => `' ${TR(t)}'`);

window.addEventListener('i18n', () => { try { const d = doc(); if (d && d.getElementById('cp-tools-css')) { d.getElementById('cp-tools-css').textContent = trContent(CANVAS_CSS); } draw(); } catch (e) { /* the canvas is not there yet */ } });

const CANVAS_CSS = `
.cp-block{position:relative}
[data-node]:hover{outline:1px solid rgba(47,107,255,.42);outline-offset:-1px}
[data-node].cp-sel{outline:1.5px solid #2f6bff;outline-offset:-1.5px}
[data-node].cp-sel:hover{outline:1.5px solid #2f6bff}
[data-slot]{min-height:64px}
[data-slot]:empty{border:1px dashed #c4cfef;border-radius:10px;background:rgba(47,107,255,.03)}
[data-slot]:empty:after{content:'把组件拖到这里';display:block;text-align:center;color:#8d97b3;font:500 12.5px/1.4 "Segoe UI Variable Text","Microsoft YaHei UI","PingFang SC",sans-serif;padding:22px 8px}
.cp-empty{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;padding:30px;font-family:"Segoe UI Variable Text","Microsoft YaHei UI","PingFang SC",sans-serif;background:#fff}
.cp-empty-in{text-align:center;max-width:340px}
.cp-empty-ic{width:52px;height:52px;margin:0 auto 18px;border-radius:14px;border:1px dashed #cfcfd6;display:flex;align-items:center;justify-content:center;color:#9a9aa2}
.cp-empty b{display:block;font-size:15px;color:#111113;font-weight:600;letter-spacing:-.01em}
.cp-empty span{display:block;font-size:13px;color:#8a8a92;margin-top:6px}
.cp-empty-btns{display:flex;gap:8px;justify-content:center;margin-top:20px}
.cp-empty-btns button{font:500 12.5px "Segoe UI Variable Text","Microsoft YaHei UI","PingFang SC",sans-serif;height:32px;padding:0 14px;border-radius:8px;border:1px solid #e3e3e6;background:#fff;color:#111113;cursor:pointer;box-shadow:0 1px 2px rgba(17,17,19,.05)}
.cp-empty-btns button:hover{border-color:#cfcfd4}
.cp-empty-btns button.dark{background:#111113;border-color:#111113;color:#fff}
#cp-line{position:absolute;height:2px;background:#2f6bff;border-radius:2px;z-index:9999;pointer-events:none;display:none;box-shadow:0 0 0 3px rgba(47,107,255,.12)}
#cp-line:before,#cp-line:after{content:'';position:absolute;top:-3px;width:8px;height:8px;border-radius:50%;background:#fff;border:2px solid #2f6bff;box-sizing:border-box}
#cp-line:before{left:-4px}#cp-line:after{right:-4px}
#cp-tag{position:absolute;z-index:9997;display:none;height:20px;padding:0 7px;border-radius:5px 5px 0 0;background:#2f6bff;color:#fff;font:600 11px/20px "Segoe UI Variable Text","Microsoft YaHei UI","PingFang SC",sans-serif;white-space:nowrap;pointer-events:none;letter-spacing:.01em}
#cp-tag.in{border-radius:0 0 5px 0}
#cp-tools{position:absolute;z-index:9998;display:none;gap:1px;padding:3px;border-radius:9px;background:#fff;box-shadow:0 0 0 1px rgba(17,17,19,.08),0 6px 20px rgba(17,17,19,.14)}
#cp-tools button{width:26px;height:26px;border:none;border-radius:6px;background:none;color:#3c3c42;display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0}
#cp-tools button:hover{background:#f2f2f4;color:#111113}
#cp-tools button.del:hover{background:#fdf0ef;color:#c8322b}
#cp-tools button:disabled{color:#c9c9ce;background:none;cursor:default}
#cp-tools i{width:1px;height:16px;background:#ececee;margin:5px 2px}
.cp-grip{position:absolute;background:#fff;border:1.5px solid #2f6bff;border-radius:5px;z-index:9998;display:none;box-shadow:0 1px 4px rgba(47,107,255,.25);box-sizing:border-box}
.cp-grip:hover,.cp-grip.on{background:#2f6bff}
#cp-grip{width:8px;height:30px;margin-top:-15px;cursor:ew-resize}
#cp-grip-b{width:30px;height:8px;margin-left:-15px;margin-top:-4px;cursor:ns-resize}
#cp-grip-c{width:12px;height:12px;margin:-6px 0 0 -6px;border-radius:3px;cursor:nwse-resize}
#cp-size{position:absolute;z-index:9999;display:none;height:22px;padding:0 8px;border-radius:6px;background:#111113;color:#fff;font:600 11px/22px "Segoe UI Variable Text","Microsoft YaHei UI","PingFang SC",sans-serif;white-space:nowrap;pointer-events:none;font-variant-numeric:tabular-nums}
.cp-slide:before{content:'第 ' counter(cp-sl) ' 页';position:absolute;left:10px;top:10px;z-index:6;height:20px;padding:0 9px;border-radius:99px;background:rgba(17,17,19,.62);color:#fff;font:600 11px/20px "Segoe UI Variable Text","Microsoft YaHei UI","PingFang SC",sans-serif;pointer-events:none}
.cp-slide [data-slot]:empty{border-radius:0;border-width:0;background:repeating-linear-gradient(45deg,rgba(47,107,255,.025) 0 10px,transparent 10px 20px)}
`;
const GRIPS = '<div id="cp-grip" class="cp-grip" title="拖动改宽度"></div><div id="cp-grip-b" class="cp-grip" title="拖动改高度"></div><div id="cp-grip-c" class="cp-grip" title="拖动同时改宽度和高度"></div><div id="cp-size"></div>';

function doc() {
  return canvas.contentDocument;
}

function startCanvas() {
  canvas.srcdoc = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style id="cp-css"></style><style id="cp-tools-css"></style></head><body></body></html>';
  canvas.addEventListener('load', () => {
    const d = doc();
    d.getElementById('cp-tools-css').textContent = trContent(CANVAS_CSS);
    d.addEventListener('mousedown', canvasDown, true);
    d.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); }, true);
    d.addEventListener('submit', (e) => e.preventDefault(), true);
    d.addEventListener('mousemove', (e) => { const r = canvas.getBoundingClientRect(); dragMove(e.clientX + r.left, e.clientY + r.top); });
    d.addEventListener('mouseup', () => dragEnd());
    d.addEventListener('keydown', keys);
    d.addEventListener('scroll', () => mark(), { passive: true });
    d.defaultView.addEventListener('resize', () => mark());
    draw();
  });
}

const EMPTY = `<div class="cp-empty"><div class="cp-empty-in">
<div class="cp-empty-ic"><svg viewBox="0 0 16 16" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3.2v9.6M3.2 8h9.6"/></svg></div>
<b>从左边拖一个组件到这里</b><span>或者挑一个模板，在它上面改</span>
<div class="cp-empty-btns"><button data-empty="starts">看模板</button><button class="dark" data-empty="nav-left">先放一个导航栏</button></div>
</div></div>`;

function draw() {
  const d = doc();
  if (!d || !d.getElementById('cp-css')) return;
  const top = d.documentElement.scrollTop;
  d.getElementById('cp-css').textContent = cpCss(page).css;
  d.body.innerHTML = (page.blocks.length ? cpBody(page, true) : trWords(EMPTY)) + '<div id="cp-line"></div>' + GRIPS + '<div id="cp-tag"></div><div id="cp-tools"></div>';
  d.documentElement.scrollTop = top;
  if (document.activeElement !== $('pageTitle')) $('pageTitle').value = page.title;
  fitTitle();
  mark();
}

function fitTitle() {
  /* The title box is as wide as the title, so that what follows it sits next to it. */
  const box = $('pageTitle');
  const ctx = fitTitle.ctx || (fitTitle.ctx = document.createElement('canvas').getContext('2d'));
  ctx.font = `500 13px ${getComputedStyle(document.body).fontFamily}`;
  box.style.width = `${Math.ceil(Math.min(280, Math.max(96, ctx.measureText(box.value || box.placeholder).width + 22)))}px`;
}

function mark() {
  const d = doc();
  if (!d || !d.body) return;
  d.querySelectorAll('.cp-sel').forEach((e) => e.classList.remove('cp-sel'));
  const grip = d.getElementById('cp-grip');
  const gripB = d.getElementById('cp-grip-b');
  const gripC = d.getElementById('cp-grip-c');
  const tag = d.getElementById('cp-tag');
  const tools = d.getElementById('cp-tools');
  for (const x of [grip, gripB, gripC, tag, tools, d.getElementById('cp-size')]) if (x) x.style.display = 'none';
  if (!selected) return;
  const el = d.querySelector(`[data-node="${selected}"]`);
  const hit = findNode(selected);
  if (!el || !hit) return;
  el.classList.add('cp-sel');
  const r = el.getBoundingClientRect();
  const sx = d.documentElement.scrollLeft;
  const sy = d.documentElement.scrollTop;
  const vw = d.documentElement.clientWidth;
  if (tag) {
    tag.textContent = nameOf(hit.node);
    tag.style.display = 'block';
    const inside = r.top < 22;
    tag.classList.toggle('in', inside);
    tag.style.left = (Math.max(0, r.left) + sx) + 'px';
    tag.style.top = (inside ? Math.max(r.top, 0) + sy : r.top + sy - 20) + 'px';
  }
  if (tools) {
    const parent = parentOf(selected);
    tools.innerHTML = `<button data-act="up" title="上移 · Alt+↑" ${hit.index === 0 ? 'disabled' : ''}>${toolSvg('up')}</button>`
      + `<button data-act="down" title="下移 · Alt+↓" ${hit.index === hit.list.length - 1 ? 'disabled' : ''}>${toolSvg('down')}</button>`
      + (parent ? `<button data-act="parent" title="选外面那层">${toolSvg('parent')}</button>` : '')
      + `<i></i><button data-act="copy" title="复制一份 · Ctrl+D">${toolSvg('copy')}</button>`
      + `<button data-act="del" class="del" title="删除 · Delete">${toolSvg('del')}</button>`;
    tools.style.display = 'flex';
    const w = tools.offsetWidth || 140;
    const left = Math.min(Math.max(r.right - w - 8, r.left + 8), vw - w - 8);
    const above = r.top > 44;
    tools.style.left = (left + sx) + 'px';
    tools.style.top = ((above ? r.top - 40 : r.top + 8) + sy) + 'px';
    if (!above && tag && !tag.classList.contains('in')) tools.style.top = (r.top + 26 + sy) + 'px';
  }
  const right = Math.min(r.right - 4, vw - 12);  // on a full-width block the grips sit just inside the edge, so it can still be pulled in
  if (grip) {
    grip.style.display = 'block';
    grip.style.left = (right + sx) + 'px';
    grip.style.top = (r.top + sy + r.height / 2) + 'px';
  }
  if (gripB) {  // the bottom edge: the height
    gripB.style.display = 'block';
    gripB.style.left = (r.left + r.width / 2 + sx) + 'px';
    gripB.style.top = (r.bottom - 4 + sy) + 'px';
  }
  if (gripC) {
    gripC.style.display = 'block';
    gripC.style.left = (right + sx) + 'px';
    gripC.style.top = (r.bottom - 6 + sy) + 'px';
  }
  if (drag && drag.kind === 'resize') sizeLabel(el, r, sx, sy);
}

function sizeLabel(el, r, sx, sy) {
  /* While a grip is held: how wide and how tall, next to the hand. */
  const d = doc();
  const box = d.getElementById('cp-size');
  const s = (findNode(selected) || {}).node;
  if (!box || !s) return;
  const st = s.style || {};
  box.textContent = `宽 ${st.width || 100}%  ·  高 ${st.minHeight ? `${st.minHeight}px` : `自动 ${Math.round(r.height)}px`}`;
  box.style.display = 'block';
  box.style.left = (Math.min(r.right, d.documentElement.clientWidth - 10) - box.offsetWidth - 8 + sx) + 'px';
  box.style.top = (r.bottom + 10 + sy) + 'px';
}

function parentOf(id) {
  let found = null;
  const walk = (list, owner) => {
    for (const n of list) {
      if (n.id === id) { found = owner; return true; }
      for (const inner of n.children || []) if (walk(inner, n)) return true;
    }
    return false;
  };
  walk(page.blocks, null);
  return found;
}

function select(id) {
  selected = id;
  mark();
  panel();
  if (tab === 'layers') fillLayers();
}

/* --- dragging ---------------------------------------------------------------------------------------------------------- */

let drag = null;   // {kind: 'new'|'move'|'resize', ...}
let clipboard = null;  // a block copied with Ctrl+C

function partDown(e, type) {
  if (e.button !== 0) return;
  e.preventDefault();
  drag = { kind: 'new', type, started: false, x: e.clientX, y: e.clientY };
}

function toolAct(act) {
  const hit = selected ? findNode(selected) : null;
  if (!hit) return;
  if (act === 'parent') { const p = parentOf(selected); if (p) select(p.id); return; }
  remember();
  const { node, list, index } = hit;
  if (act === 'up' && index > 0) list.splice(index - 1, 0, list.splice(index, 1)[0]);
  else if (act === 'down' && index < list.length - 1) list.splice(index + 1, 0, list.splice(index, 1)[0]);
  else if (act === 'copy') {
    const copy = freshIds(JSON.parse(JSON.stringify(node)));
    list.splice(index + 1, 0, copy);
    selected = copy.id;
  } else if (act === 'del') {
    list.splice(index, 1);
    selected = null;
  }
  changed();
}

function canvasDown(e) {
  if (e.button !== 0) return;
  const d = doc();
  const r = canvas.getBoundingClientRect();
  const tool = e.target.closest('#cp-tools button');
  if (tool) {
    e.preventDefault();
    if (!tool.disabled) toolAct(tool.dataset.act);
    return;
  }
  const empty = e.target.closest('[data-empty]');
  if (empty) {
    e.preventDefault();
    if (empty.dataset.empty === 'starts') showTab('starts');
    else {
      remember();
      const node = makeNode(empty.dataset.empty);
      page.blocks.push(node);
      selected = node.id;
      changed();
    }
    return;
  }
  const gripKind = { 'cp-grip': 'w', 'cp-grip-b': 'h', 'cp-grip-c': 'wh' }[e.target.id];
  if (gripKind) {
    const el = d.querySelector(`[data-node="${selected}"]`);
    if (el) {
      /* the height its content needs, measured once: pulled shorter than that, the block goes back to "auto" */
      const keep = el.style.minHeight;
      el.style.minHeight = '0px';
      const natural = el.getBoundingClientRect().height;
      el.style.minHeight = keep;
      drag = { kind: 'resize', axes: gripKind, started: true, parent: el.parentElement.getBoundingClientRect(), y0: e.clientY + r.top,
        h0: el.getBoundingClientRect().height, natural, before: JSON.stringify(page) };
      e.target.classList.add('on');
    }
    e.preventDefault();
    return;
  }
  const block = e.target.closest('[data-node]');
  if (!block) {
    select(null);
    return;
  }
  select(block.dataset.node);
  e.preventDefault();
  drag = { kind: 'move', id: block.dataset.node, started: false, x: e.clientX + r.left, y: e.clientY + r.top };
}

function dragMove(x, y) {
  if (!drag) return;
  if (drag.kind === 'resize') {
    resizeTo(x, y);
    return;
  }
  if (!drag.started) {
    if (Math.hypot(x - drag.x, y - drag.y) < 6) return;
    drag.started = true;
    $('shield').hidden = false;
    canvas.style.pointerEvents = 'none';
    const g = $('ghost');
    const node = drag.kind === 'move' ? (findNode(drag.id) || {}).node : null;
    const type = drag.kind === 'new' ? drag.type : node && node.type;
    g.innerHTML = `<i>${drag.kind === 'new' ? icon('plus') : icon('grip')}</i><span></span>`;
    g.querySelector('span').textContent = type ? CP.byId[type].name : '移动';
    g.hidden = false;
    const t = doc().getElementById('cp-tools');
    if (t) t.style.display = 'none';
  }
  const g = $('ghost');
  g.style.left = x + 'px';
  g.style.top = y + 'px';
  drag.place = dropPlace(x, y);
  showLine(drag.place);
}

function dropPlace(x, y) {
  /* Where a block would land: which list, at which position. */
  const r = canvas.getBoundingClientRect();
  if (x < r.left || x > r.right || y < r.top || y > r.bottom) return null;
  const d = doc();
  const cx = x - r.left;
  const cy = y - r.top;
  let el = d.elementFromPoint(cx, cy);
  let slot = el ? el.closest('[data-slot]') : null;
  if (drag.kind === 'move' && slot) {  // a block cannot go inside itself
    const moving = findNode(drag.id);
    while (slot && moving && contains(moving.node, slot.dataset.slot.split(':')[0])) slot = slot.parentElement.closest('[data-slot]');
  }
  const host = slot || d.body;
  const kids = [...host.children].filter((c) => c.matches('[data-node]') && (drag.kind !== 'move' || c.dataset.node !== drag.id));
  let index = kids.length;
  for (let i = 0; i < kids.length; i++) {
    const b = kids[i].getBoundingClientRect();
    if (cy < b.top + b.height / 2) {
      index = i;
      break;
    }
  }
  const hb = host === d.body ? { left: 0, width: d.documentElement.clientWidth, top: 0, bottom: 0 } : host.getBoundingClientRect();
  let lineY;
  if (kids.length === 0) lineY = host === d.body ? 12 : hb.top + 4;
  else if (index < kids.length) lineY = kids[index].getBoundingClientRect().top;
  else lineY = kids[kids.length - 1].getBoundingClientRect().bottom;
  const inset = host === d.body ? 10 : 4;
  return { slot: slot ? slot.dataset.slot : null, index, line: { x: hb.left + inset, y: lineY, w: hb.width - inset * 2 } };
}

function showLine(place) {
  const d = doc();
  const line = d && d.getElementById('cp-line');
  if (!line) return;
  if (!place) {
    line.style.display = 'none';
    return;
  }
  line.style.display = 'block';
  line.style.left = (place.line.x + d.documentElement.scrollLeft) + 'px';
  line.style.width = place.line.w + 'px';
  line.style.top = (Math.max(place.line.y, 3) + d.documentElement.scrollTop - 1) + 'px';
}

function resizeTo(x, y) {
  /* The right grip sets the width (a share of what it sits in), the bottom one the height (px), the corner both. */
  const r = canvas.getBoundingClientRect();
  const hit = findNode(selected);
  if (!hit) return;
  const s = hit.node.style = hit.node.style || {};
  const el = doc().querySelector(`[data-node="${selected}"]`);
  if (drag.axes.includes('w')) {
    const inside = x - r.left - drag.parent.left;
    const value = Math.max(10, Math.min(100, Math.round(inside / drag.parent.width * 100)));
    if (value >= 100) delete s.width; else s.width = value;
  }
  if (drag.axes.includes('h')) {
    const want = Math.round(drag.h0 + (y - drag.y0));
    if (want <= drag.natural + 2) delete s.minHeight;  // shorter than its content: back to the height it needs
    else {
      s.minHeight = Math.min(2400, want);
      if (s.valign === undefined) s.valign = 'center';  // a taller block keeps its content in the middle
    }
  }
  if (el) {
    el.setAttribute('style', cpStyle(s).replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&'));
    mark();
  }
}

function dragEnd() {
  if (!drag) return;
  const was = drag;
  drag = null;
  $('ghost').hidden = true;
  $('shield').hidden = true;
  canvas.style.pointerEvents = '';
  showLine(null);
  if (was.kind === 'resize') {
    if (JSON.stringify(page) !== was.before) {  // a click on a grip without moving changes nothing
      history.push(was.before);
      future = [];
      dirty = true;
    }
    changed();
    return;
  }
  if (!was.started || !was.place) {
    mark();
    return;
  }
  remember();
  const target = listOf(was.place.slot);
  if (was.kind === 'new') {
    const node = makeNode(was.type);
    target.splice(was.place.index, 0, node);
    selected = node.id;
  } else {
    const hit = findNode(was.id);
    if (!hit) return;
    const [node] = hit.list.splice(hit.index, 1);
    target.splice(Math.min(was.place.index, target.length), 0, node);
  }
  changed();
}

document.addEventListener('mousemove', (e) => dragMove(e.clientX, e.clientY));
document.addEventListener('mouseup', dragEnd);

/* --- the left: components, starts, layers, design ---------------------------------------------------------------------- */

function sampleNode(item) {
  const node = { id: 't', type: item.id, values: Object.fromEntries((item.fields || []).map((f) => [f.key, f.value])), style: {} };
  if (item.slides) node.children = (item.kids || [[]]).map((ids) => ids.filter((t) => CP.byId[t]).map((t) => sampleNode(CP.byId[t])));
  else if (item.slots) node.children = Array.from({ length: item.slots }, () => []);
  return node;
}

function shadowShot(box, blocks, width, extra) {
  /* A real small rendering, kept away from the builder's own styles in a shadow root; scaled to the box it sits in. */
  const root = box.shadowRoot || box.attachShadow({ mode: 'open' });
  const fake = { theme: page ? page.theme : { ...CP.lib.themes[0], radius: 10, font: CP.lib.fonts[0].css }, blocks };
  const { css } = cpCss(fake);
  root.innerHTML = `<style>${css.replace(':root', ':host')}
    :host{display:block}
    .z{width:${width}px;transform-origin:top left;position:absolute;left:0;top:0;color:var(--cp-ink);background:var(--cp-bg);font-family:var(--cp-font);line-height:1.65;font-size:16px}
    .cp-nav{position:static}${extra || ''}</style>
    <div class="z">${cpBody(fake, false)}</div>`;
  box.dataset.w = width;
}

function fitShots(scope, center) {
  for (const box of scope.querySelectorAll('[data-w]')) {
    const z = box.shadowRoot && box.shadowRoot.querySelector('.z');
    if (!z) continue;
    const s = box.clientWidth / Number(box.dataset.w);
    if (!s) continue;
    z.style.transform = `scale(${s})`;
    const h = z.offsetHeight * s;
    z.style.top = center && h < box.clientHeight ? `${(box.clientHeight - h) / 2}px` : '0px';
  }
}

/* Components with nothing to see at this size (empty space, a bare line, a player with no file yet) get a drawing of what they do. */
const SKETCH = {
  spacer: '<rect x="20" y="14" width="80" height="9" rx="2" fill="#ececef"/><rect x="20" y="57" width="80" height="9" rx="2" fill="#ececef"/><path d="M60 28v24M55 33l5-5 5 5M55 47l5 5 5-5" stroke="#9a9aa2" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  divider: '<rect x="20" y="22" width="58" height="6" rx="2" fill="#ececef"/><rect x="20" y="31" width="40" height="6" rx="2" fill="#f3f3f5"/><path d="M14 41h92" stroke="#b9b9c0" stroke-width="1.2"/><rect x="20" y="47" width="64" height="6" rx="2" fill="#ececef"/><rect x="20" y="56" width="44" height="6" rx="2" fill="#f3f3f5"/>',
  video: '<rect x="18" y="13" width="84" height="54" rx="6" fill="#18181b"/><circle cx="60" cy="40" r="11" fill="rgba(255,255,255,.14)"/><path d="m56.5 34.5 9 5.5-9 5.5Z" fill="#fff"/><rect x="26" y="58" width="68" height="2" rx="1" fill="rgba(255,255,255,.2)"/><rect x="26" y="58" width="24" height="2" rx="1" fill="#fff"/>',
  audio: '<rect x="14" y="27" width="92" height="26" rx="13" fill="#f2f2f4"/><path d="m25 35 7 5-7 5Z" fill="#3c3c42"/><path d="M41 40h4M48 36v8M52 33v14M56 37v6M60 34v12M64 36v8M68 38v4M72 35v10M76 37v6M80 39v2M84 36v8" stroke="#9a9aa2" stroke-width="1.6" stroke-linecap="round"/>',
  html: '<rect x="18" y="14" width="84" height="52" rx="6" fill="#fafafa" stroke="#e3e3e6"/><path d="m46 32-8 8 8 8M74 32l8 8-8 8M64 28l-8 24" stroke="#5f5f66" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  'top-button': '<rect x="16" y="10" width="88" height="60" rx="6" fill="#fff" stroke="#e3e3e6"/><rect x="24" y="19" width="50" height="5" rx="2" fill="#ececef"/><rect x="24" y="28" width="62" height="5" rx="2" fill="#f3f3f5"/><rect x="24" y="37" width="40" height="5" rx="2" fill="#f3f3f5"/><circle cx="90" cy="57" r="8" fill="#111113"/><path d="M90 61v-8M86.5 56.5 90 53l3.5 3.5" stroke="#fff" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
};

const THUMB_EXTRA = '.cp-slot{min-height:190px;border:4px dashed #b9c4dd;border-radius:14px;background:#f3f6fc}.cp-hero{padding:56px 0}.cp-cover{min-height:340px}.cp-split{padding:28px 0}'
  + '.cp-deck{padding:0}.cp-slide+.cp-slide{display:none}.cp-slide .cp-slot{border:0;border-radius:0;background:none;min-height:0}.g-hero-cv{min-height:0}';

/* Hundreds of components: a picture is drawn only when its tile scrolls into view, and filters narrow the list. */
const LOOK_CHIPS = [['', '全部'], ['plain', '常规'], ['soft', '灰底'], ['ink', '反色'], ['brand', '主色'], ['glow', '渐变']];
let lookFilter = '';
let catFilter = '';
let thumbWatch = null;

function drawThumb(t) {
  const item = CP.byId[t.dataset.part];
  if (!item || t.dataset.drawn) return;
  t.dataset.drawn = '1';
  if (SKETCH[item.id]) t.innerHTML = `<svg viewBox="0 0 120 80" style="width:100%;height:100%;stroke:none">${SKETCH[item.id]}</svg>`;
  else {
    shadowShot(t, [sampleNode(item)], 560, THUMB_EXTRA);
    fitShots(t.parentElement, true);
  }
}

function fillFilters() {
  const box = $('partsFilter');
  box.innerHTML = '';
  const sel = document.createElement('select');
  sel.setAttribute('aria-label', '分类');
  sel.add(new Option('全部分类', ''));
  for (const cat of CP.lib.categories) if (!cat.hidden) sel.add(new Option(`${cat.name}（${cat.items.length}）`, cat.id, false, cat.id === catFilter));
  sel.value = catFilter;
  sel.onchange = () => { catFilter = sel.value; fillParts($('find').value); $('parts').scrollTop = 0; };
  const looks = document.createElement('div');
  looks.className = 'looks';
  for (const [key, name] of LOOK_CHIPS) {
    const b = document.createElement('button');
    b.className = 'chip' + (key === lookFilter ? ' on' : '');
    b.textContent = name;
    b.title = key ? `只看“${name}”样子的组件` : '所有样子';
    b.onclick = () => { lookFilter = key; fillFilters(); fillParts($('find').value); $('parts').scrollTop = 0; };
    looks.append(b);
  }
  box.append(sel, looks);
}

function fillParts(needle) {
  const box = $('parts');
  box.innerHTML = '';
  if (thumbWatch) thumbWatch.disconnect();
  thumbWatch = 'IntersectionObserver' in window ? new IntersectionObserver((seen) => {
    for (const e of seen) if (e.isIntersecting) { thumbWatch.unobserve(e.target); drawThumb(e.target); }
  }, { root: box, rootMargin: '400px 0px' }) : null;
  const q = needle.trim().toLowerCase();
  let total = 0;
  for (const cat of CP.lib.categories) {
    if (cat.hidden || (catFilter && cat.id !== catFilter)) continue;
    const items = cat.items.filter((i) => (!q || (cat.name + i.name + i.id + (i.tags || '')).toLowerCase().includes(q))
      && (!lookFilter || (i.look || 'plain') === lookFilter));
    if (!items.length) continue;
    total += items.length;
    const folded = !q && !catFilter && shut.has(cat.id);
    const head = document.createElement('button');
    head.className = 'cat' + (folded ? ' shut' : '');
    head.innerHTML = `${icon('chev')}<span></span><span class="count">${items.length}</span>`;
    head.children[1].textContent = cat.name;
    head.onclick = () => {
      if (shut.has(cat.id)) shut.delete(cat.id); else shut.add(cat.id);
      try { localStorage.setItem(FOLD, JSON.stringify([...shut])); } catch (e) { /* only a convenience */ }
      fillParts($('find').value);
    };
    box.append(head);
    if (folded) continue;
    const grid = document.createElement('div');
    grid.className = 'grid';
    for (const item of items) {
      const part = document.createElement('div');
      part.className = 'part';
      part.title = `${item.name}：拖到页面上，或者双击加到最后`;
      const t = document.createElement('div');
      t.className = 'thumb' + (cat.id === 'slides' ? ' wide' : '');
      t.dataset.part = item.id;
      const n = document.createElement('div');
      n.className = 'name';
      n.textContent = item.name;
      part.append(t, n);
      part.addEventListener('mousedown', (e) => partDown(e, item.id));
      part.addEventListener('dblclick', () => {  // for those who would rather not drag: add to the end
        remember();
        const node = makeNode(item.id);
        page.blocks.push(node);
        selected = node.id;
        changed();
        const el = doc() && doc().querySelector(`[data-node="${node.id}"]`);
        if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      });
      grid.append(part);
      if (thumbWatch) thumbWatch.observe(t);
    }
    box.append(grid);
  }
  if (!box.children.length) box.innerHTML = '<div class="empty">没有找到。<br>换个词试试，比如“图片”“表单”，或者把上面的筛选放宽一些。</div>';
  if (tab === 'parts') $('paneNote').textContent = q || lookFilter || catFilter ? `找到 ${total} 个` : `${partCount()} 个`;
  if (!thumbWatch) box.querySelectorAll('.thumb').forEach(drawThumb);
}

function partCount() {
  return CP.lib.categories.filter((c) => !c.hidden).reduce((n, c) => n + c.items.length, 0);
}

function fillLayers() {
  /* The whole page as a list: the quick way to a block that is hard to click, and the only way to one with nothing visible in it. */
  const box = $('layers');
  box.innerHTML = '';
  const tree = document.createElement('div');
  tree.className = 'tree';
  const walk = (list, depth) => {
    for (const n of list) {
      const b = document.createElement('button');
      b.className = 'layer' + (n.id === selected ? ' on' : '');
      b.style.paddingLeft = `${8 + depth * 16}px`;
      for (let i = 0; i < depth; i++) {
        const g = document.createElement('span');
        g.className = 'guide';
        g.style.left = `${16 + i * 16}px`;
        b.append(g);
      }
      const kind = document.createElement('span');
      kind.className = 'kind';
      kind.innerHTML = kindIcon(kindOf[n.type]);
      kind.querySelector('svg').style.cssText = 'width:12px;height:12px';
      const what = document.createElement('span');
      what.className = 'what';
      what.textContent = nameOf(n);
      const hint = document.createElement('span');
      hint.className = 'hint';
      hint.textContent = hintOf(n);
      b.append(kind, what, hint);
      b.onclick = () => {
        select(n.id);
        const el = doc() && doc().querySelector(`[data-node="${n.id}"]`);
        if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
        setTimeout(mark, 350);
      };
      tree.append(b);
      (n.children || []).forEach((l) => walk(l, depth + 1));
    }
  };
  walk(page.blocks, 0);
  box.append(tree);
  if (!tree.children.length) box.innerHTML = '<div class="empty">页面还是空的。</div>';
  if (tab === 'layers') $('paneNote').textContent = countBlocks() ? `${countBlocks()} 个` : '';
}

function colorControl(read, write, after) {
  /* A swatch that opens the picker, the hex code you can type, and a way back to "not set". */
  const wrap = document.createElement('div');
  wrap.className = 'color';
  wrap.innerHTML = `<span class="sw"><i></i><input type="color" tabindex="-1"></span><input class="hex" spellcheck="false" placeholder="不设置"><button title="不设置" aria-label="不设置">${icon('close')}</button>`;
  const sw = wrap.querySelector('.sw i');
  const pick = wrap.querySelector('input[type=color]');
  const hex = wrap.querySelector('.hex');
  const clear = wrap.querySelector('button');
  const show = () => {
    const v = read() || '';
    sw.style.background = v || 'transparent';
    if (document.activeElement !== hex) hex.value = v;
    pick.value = /^#[0-9a-f]{6}$/i.test(v) ? v : '#ffffff';
    clear.style.visibility = v && after !== 'required' ? 'visible' : 'hidden';
  };
  let first = true;
  const set = (v) => {
    if (first) { remember(); first = false; }
    write(v);
    show();
    draw();
    buttons();
  };
  pick.addEventListener('input', () => set(pick.value));
  pick.addEventListener('change', () => { first = true; changed(); });
  hex.addEventListener('input', () => {
    const v = hex.value.trim();
    if (!v || /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v) || /^(rgb|hsl)a?\(/.test(v)) set(v);
  });
  hex.addEventListener('blur', () => { first = true; show(); });
  clear.onclick = () => { set(''); first = true; changed(); };
  show();
  return wrap;
}

function slider(min, max, read, write, unit) {
  const wrap = document.createElement('div');
  wrap.className = 'slider';
  wrap.innerHTML = `<input type="range" min="${min}" max="${max}"><output></output>`;
  const r = wrap.querySelector('input');
  const out = wrap.querySelector('output');
  const show = () => {
    r.value = read();
    out.textContent = `${r.value}${unit}`;
    r.style.setProperty('--fill', `${(r.value - min) / (max - min) * 100}%`);
  };
  let first = true;
  r.addEventListener('input', () => {
    if (first) { remember(); first = false; }
    write(Number(r.value));
    show();
    draw();
    buttons();
  });
  r.addEventListener('change', () => { first = true; try { localStorage.setItem(STORE, JSON.stringify(page)); } catch (e) { /* see changed() */ } });
  show();
  return wrap;
}

function group(box, label, note) {
  const g = document.createElement('div');
  g.className = 'group';
  const l = document.createElement('div');
  l.className = 'label';
  l.textContent = label;
  if (note) {
    const n = document.createElement('span');
    n.className = 'note';
    n.textContent = note;
    l.append(n);
  }
  g.append(l);
  box.append(g);
  return g;
}

function fillDesign() {
  const box = $('design');
  box.innerHTML = '';
  const themes = group(box, '配色', `${CP.lib.themes.length} 套`);
  const grid = document.createElement('div');
  grid.className = 'themes';
  for (const t of CP.lib.themes) {
    const on = ['primary', 'bg', 'ink', 'soft'].every((k) => (page.theme[k] || '').toLowerCase() === t[k].toLowerCase());
    const b = document.createElement('button');
    b.className = 'theme' + (on ? ' on' : '');
    b.innerHTML = `<div class="face" style="background:${t.bg}"><i style="background:${t.ink}"></i><i style="background:${t.ink}"></i><i style="background:${t.primary}"></i></div><span><em></em>${icon('check')}</span>`;
    b.querySelector('em').textContent = t.name;
    b.querySelector('em').style.fontStyle = 'normal';
    b.onclick = () => {
      remember();
      page.theme = { ...page.theme, ...t };
      changed();
      fillDesign();
      fillParts($('find').value);
    };
    grid.append(b);
  }
  themes.append(grid);
  const tune = group(box, '细调');
  for (const [label, key] of [['主色', 'primary'], ['背景', 'bg'], ['文字', 'ink'], ['浅色块', 'soft'], ['线条', 'line']]) {
    const f = document.createElement('div');
    f.className = 'field';
    const l = document.createElement('label');
    l.textContent = label;
    f.append(l, colorControl(() => page.theme[key], (v) => { page.theme[key] = v || page.theme[key]; }, 'required'));
    tune.append(f);
  }
  const rf = document.createElement('div');
  rf.className = 'field';
  rf.innerHTML = '<label>圆角</label>';
  rf.append(slider(0, 28, () => page.theme.radius, (v) => { page.theme.radius = v; }, 'px'));
  tune.append(rf);
  const ff = document.createElement('div');
  ff.className = 'field';
  ff.innerHTML = '<label>字体</label><select></select>';
  const sel = ff.querySelector('select');
  for (const f of CP.lib.fonts) sel.add(new Option(f.name, f.css, false, f.css === page.theme.font));
  sel.addEventListener('change', () => {
    remember();
    page.theme.font = sel.value;
    changed();
  });
  tune.append(ff);
}

const STARTS = [
  { name: '空白页', note: '从零开始', blocks: [] },
  { name: '演示文稿', note: '一组能翻页、能全屏放映的幻灯片', blocks: ['deck'] },
  { name: '产品发布', note: '徽标首屏、拼贴格、评价、价格', blocks: ['nav-pill', 'hero-badge-glow', 'logo-row', 'feat-bento', 'feat-zigzag', 'proof-three', 'price-three', 'faq-accordion', 'cta-box', 'footer-four'] },
  { name: '手机应用', note: '手机样机、数字、下载按钮', blocks: ['nav-bar-two', 'hero-phone', 'stat-row-soft', 'feat-tabs', 'proof-chat', 'cta-app-brand', 'footer-social'] },
  { name: '餐厅小店', note: '大图、菜单、订位、地址', blocks: ['nav-split', 'hero-cover', 'content-left', 'card-products-soft', 'form-booking', 'contact-map', 'footer-center'] },
  { name: '工作室', note: '超大字、作品、团队', blocks: ['nav-crumbs', 'hero-giant', 'gal-masonry', 'text-intro', 'team-grid', 'footer-big'] },
  { name: '活动报名', note: '倒数、日程、报名表', blocks: ['nav-announce', 'hero-collage', 'card-events', 'step-line', 'form-signup-soft', 'faq-side', 'footer-center'] },
  { name: '博客文章', note: '正文、侧栏、推荐阅读', blocks: ['nav-search', 'content-article', 'content-pullquote', 'content-side-note', 'card-hlist', 'form-newsletter', 'footer-center'] },
  { name: '导航站', note: '搜索加一排排链接', blocks: ['search-tags', 'heading-sub', 'features', 'social', 'footer-simple'] },
  { name: '简历', note: '头像、经历、技能', blocks: ['hero-split', 'timeline', 'progress', 'social', 'footer-simple'] },
  { name: '公司介绍', note: '团队、步骤、地址', blocks: ['nav-left', 'hero-photo', 'steps', 'team', 'logos', 'map-link', 'footer-cols', 'top-button'] },
  { name: '作品集', note: '图片墙和联系方式', blocks: ['nav-center', 'carousel', 'gallery', 'form-contact', 'footer-simple'] },
  { name: '个人主页', note: '自我介绍、作品、联系方式', blocks: ['nav-center', 'hero-split', 'heading-sub', 'gallery', 'form-contact', 'footer-simple'] },
  { name: '产品介绍', note: '首屏、特点、价格、问答', blocks: ['nav-button', 'hero-center', 'features', 'stats', 'pricing', 'faq', 'cta', 'footer-cols'] },
  { name: '搜索首页', note: '一个大搜索框', blocks: ['nav-left', 'search-big', 'features', 'footer-simple'] },
  { name: '活动页', note: '大图、倒计时、时间线', blocks: ['hero-photo', 'countdown', 'timeline', 'form-news', 'footer-simple'] },
  { name: '文章页', note: '标题、段落、图片、引用', blocks: ['nav-dark', 'heading', 'paragraph', 'image', 'quote', 'paragraph', 'footer-simple'] },
];

function fillStarts() {
  const box = $('starts');
  box.innerHTML = '';
  const list = document.createElement('div');
  list.className = 'starts';
  for (const s of STARTS) {
    const b = document.createElement('button');
    b.className = 'start';
    const shot = document.createElement('div');
    shot.className = 'shot' + (s.blocks.length ? '' : ' blank');
    if (s.blocks.length) shadowShot(shot, s.blocks.filter((t) => CP.byId[t]).map((t) => sampleNode(CP.byId[t])), 1280, '.cp-top{display:none}.cp-slide+.cp-slide{display:none}.cp-anim{opacity:1}');
    else shot.innerHTML = icon('plus');
    const name = document.createElement('b');
    name.textContent = s.name;
    const note = document.createElement('small');
    note.textContent = s.note;
    b.append(shot, name, note);
    const swap = () => {
      remember();
      page.blocks = s.blocks.map(makeNode);
      selected = null;
      changed();
    };
    b.onclick = () => {
      if (page.blocks.length) ask(`换成“${s.name}”？现在的内容可以用“撤销”找回来。`, swap);
      else swap();
    };
    list.append(b);
  }
  box.append(list);
  if (tab === 'starts') $('paneNote').textContent = `${STARTS.length} 个`;
  requestAnimationFrame(() => fitShots(box, false));
}

function showTab(name) {
  tab = name;
  document.querySelectorAll('[data-tab]').forEach((x) => x.classList.toggle('on', x.dataset.tab === name));
  for (const id of ['parts', 'layers', 'design', 'starts']) $(id).hidden = id !== name;
  $('findBox').hidden = name !== 'parts';
  $('partsFilter').hidden = name !== 'parts';
  $('paneTitle').textContent = { parts: '组件', starts: '模板', layers: '层级', design: '外观' }[name];
  $('paneNote').textContent = '';
  if (name === 'parts') fillParts($('find').value);
  if (name === 'starts') fillStarts();
  if (name === 'layers') fillLayers();
  if (name === 'design') fillDesign();
}

/* --- the right: what is selected ---------------------------------------------------------------------------------------- */

function bind(input, read, write) {
  input.value = read() === undefined ? '' : read();
  let first = true;
  input.addEventListener('input', () => {
    if (first) {
      remember();
      first = false;
    }
    write(input.value);
    draw();
    buttons();
  });
  input.addEventListener('blur', () => {
    first = true;
    try { localStorage.setItem(STORE, JSON.stringify(page)); } catch (e) { /* see changed() */ }
    if (tab === 'layers') fillLayers();
  });
  return input;
}

function section(box, id, title) {
  const sec = document.createElement('div');
  sec.className = 'sec' + (shutSecs.has(id) ? ' shut' : '');
  const head = document.createElement('button');
  head.className = 'secHead';
  head.innerHTML = `<span></span>${icon('chev')}`;
  head.firstChild.textContent = title;
  head.onclick = () => {
    sec.classList.toggle('shut');
    if (sec.classList.contains('shut')) shutSecs.add(id); else shutSecs.delete(id);
  };
  const body = document.createElement('div');
  body.className = 'secBody';
  sec.append(head, body);
  box.append(sec);
  return body;
}

function field(box, label, control, help) {
  const f = document.createElement('div');
  f.className = 'field';
  const l = document.createElement('label');
  /* '特点（一行一个：符号|标题|说明）' -> the label, and what is in brackets as help under the box */
  const m = /^(.*?)（(.*)）$/.exec(label);
  l.textContent = m ? m[1] : label;
  f.append(l, control);
  const say = help || (m ? m[2] : '');
  if (say) {
    const h = document.createElement('div');
    h.className = 'help';
    h.textContent = say;
    f.append(h);
  }
  box.append(f);
  return f;
}

function numberBox(s, key, cls, unit) {
  const input = document.createElement('input');
  input.type = 'number';
  input.min = 0;
  input.placeholder = '–';
  if (cls) input.className = cls;
  bind(input, () => s[key], (v) => { if (v === '') delete s[key]; else s[key] = Number(v); });
  if (!unit) return input;
  const wrap = document.createElement('div');
  wrap.className = 'unit';
  wrap.dataset.unit = unit;
  wrap.append(input);
  return wrap;
}

function segs(options, read, write) {
  const wrap = document.createElement('div');
  wrap.className = 'segs';
  for (const [value, label, title] of options) {
    const b = document.createElement('button');
    b.innerHTML = label;
    b.title = title;
    b.className = read() === value ? 'on' : '';
    b.onclick = () => {
      if (read() === value) return;
      remember();
      write(value);
      changed();
    };
    wrap.append(b);
  }
  return wrap;
}

function toggle(label, read, write) {
  const row = document.createElement('div');
  row.className = 'switch';
  row.innerHTML = '<span></span><button class="toggle" role="switch"></button>';
  row.firstChild.textContent = label;
  const t = row.querySelector('button');
  t.classList.toggle('on', !!read());
  t.setAttribute('aria-checked', String(!!read()));
  t.onclick = () => {
    remember();
    write(!read());
    changed();
  };
  return row;
}

const VALIGN_ICON = {
  top: '<svg viewBox="0 0 16 16"><path d="M3 2.6h10"/><rect x="5" y="4.6" width="6" height="4" rx="1"/></svg>',
  center: '<svg viewBox="0 0 16 16"><path d="M3 2.6h10M3 13.4h10"/><rect x="5" y="6" width="6" height="4" rx="1"/></svg>',
  bottom: '<svg viewBox="0 0 16 16"><path d="M3 13.4h10"/><rect x="5" y="7.4" width="6" height="4" rx="1"/></svg>',
};
const ANIM_CHOICES = [['', '无', '直接显示'], ['up', '上浮', '从下面浮上来'], ['fade', '淡入', '慢慢显出来'], ['zoom', '放大', '从小一点变到正常'],
  ['left', '左入', '从左边进来'], ['right', '右入', '从右边进来']];

function slidesSection(box, node) {
  /* A deck's pages: move, remove, add one (empty, or a ready slide). */
  const body = section(box, 'slides', `幻灯片 · ${node.children.length} 页`);
  const list = document.createElement('div');
  list.className = 'pages';
  node.children.forEach((kids, i) => {
    const row = document.createElement('div');
    row.className = 'pageRow';
    const what = kids.length ? kids.map(nameOf).join('、') : '空白页';
    row.innerHTML = `<b>${i + 1}</b><span></span><button data-p="up" title="往前挪" ${i === 0 ? 'disabled' : ''}>${icon('up')}</button>`
      + `<button data-p="down" title="往后挪" ${i === node.children.length - 1 ? 'disabled' : ''}>${icon('down')}</button>`
      + `<button data-p="del" class="danger" title="删掉这一页" ${node.children.length < 2 ? 'disabled' : ''}>${icon('trash')}</button>`;
    row.querySelector('span').textContent = what;
    row.querySelector('span').title = what;
    row.querySelectorAll('[data-p]').forEach((b) => {
      b.onclick = () => {
        remember();
        const p = b.dataset.p;
        if (p === 'up') node.children.splice(i - 1, 0, node.children.splice(i, 1)[0]);
        if (p === 'down') node.children.splice(i + 1, 0, node.children.splice(i, 1)[0]);
        if (p === 'del') node.children.splice(i, 1);
        changed();
      };
    });
    row.querySelector('span').onclick = () => {
      const el = doc() && doc().querySelectorAll(`[data-node="${node.id}"] .cp-slide`)[i];
      if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    };
    list.append(row);
  });
  body.append(list);
  const add = document.createElement('div');
  add.className = 'addPage';
  const sel = document.createElement('select');
  sel.setAttribute('aria-label', '新的一页用什么');
  sel.add(new Option('空白页', ''));
  const slides = CP.lib.categories.find((c) => c.id === 'slides');
  for (const it of slides ? slides.items : []) if (!it.slides && (it.look || 'plain') === 'plain') sel.add(new Option(it.name, it.id));
  const go = document.createElement('button');
  go.className = 'line';
  go.innerHTML = `${icon('plus')}<span>加一页</span>`;
  go.onclick = () => {
    remember();
    node.children.push(sel.value ? [makeNode(sel.value)] : []);
    changed();
    const all = doc() && doc().querySelectorAll(`[data-node="${node.id}"] .cp-slide`);
    if (all && all.length) all[all.length - 1].scrollIntoView({ block: 'center', behavior: 'smooth' });
  };
  add.append(sel, go);
  body.append(add);
  const note = document.createElement('div');
  note.className = 'help';
  note.textContent = '编辑时每一页都摆出来；导出的网页里一次放一页，可以用方向键、按钮翻页，也能全屏放映、打印成 PDF。别的组件也能拖进任何一页。';
  body.append(note);
}

function pagePanel(box) {
  const intro = document.createElement('div');
  intro.className = 'intro';
  intro.innerHTML = '<h3>这个页面</h3><p>点画布上的东西来改它；拖动可以换位置。选中以后，右边的把手拖宽度，下边的拖高度，右下角的两样一起拖。</p>';
  const title = bind(document.createElement('input'), () => page.title, (v) => { page.title = v; });
  field(intro, '网页标题', title);
  const about = bind(document.createElement('textarea'), () => page.description || '', (v) => { page.description = v; });
  about.rows = 3;
  field(intro, '网页简介', about, '搜索引擎和分享链接时会显示这段话');
  const keys = document.createElement('div');
  keys.className = 'keys';
  for (const [what, ...ks] of [['撤销 / 重做', 'Ctrl', 'Z', 'Y'], ['复制一份', 'Ctrl', 'D'], ['上移 / 下移', 'Alt', '↑', '↓'], ['删除', 'Delete'], ['取消选择', 'Esc'], ['找组件', '/']]) {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span></span><span>${ks.map((k) => `<kbd>${k}</kbd>`).join('')}</span>`;
    row.firstChild.textContent = what;
    keys.append(row);
  }
  intro.append(keys);
  box.append(intro);
}

function panel() {
  const box = $('right');
  const scroll = box.scrollTop;
  const keepId = box.dataset.node;
  box.innerHTML = '';
  const hit = selected ? findNode(selected) : null;
  box.dataset.node = hit ? selected : '';
  if (!hit) {
    pagePanel(box);
    return;
  }
  const { node, list, index } = hit;
  const item = CP.byId[node.type];
  const cat = CP.lib.categories.find((c) => c.id === kindOf[node.type]);
  const head = document.createElement('div');
  head.className = 'insHead';
  head.innerHTML = `<div class="insTop"><strong></strong><span class="chip"></span></div><div class="insActs">
    <button data-a="up" title="上移 · Alt+↑" aria-label="上移" ${index === 0 ? 'disabled' : ''}>${icon('up')}</button>
    <button data-a="down" title="下移 · Alt+↓" aria-label="下移" ${index === list.length - 1 ? 'disabled' : ''}>${icon('down')}</button>
    <button data-a="copy" title="复制一份 · Ctrl+D" aria-label="复制一份">${icon('copy')}</button>
    <button data-a="del" class="danger" title="删除 · Delete" aria-label="删除">${icon('trash')}</button></div>`;
  head.querySelector('strong').textContent = item.name;
  head.querySelector('.chip').textContent = cat ? cat.name : '';
  head.querySelectorAll('[data-a]').forEach((b) => { b.onclick = () => toolAct(b.dataset.a); });
  box.append(head);

  node.values = node.values || {};
  if (item.slides) {
    node.children = node.children && node.children.length ? node.children : [[]];
    slidesSection(box, node);
  }
  if ((item.fields || []).length) {
    const content = section(box, 'content', '内容');
    for (const f of item.fields) {
      if (f.type === 'image') {
        const wrap = document.createElement('div');
        wrap.className = 'picture';
        const pv = document.createElement('span');
        pv.className = 'pv';
        const showPv = () => { pv.style.backgroundImage = node.values[f.key] ? `url("${cpValue(node.values[f.key]).replace(/"/g, '%22')}")` : ''; };
        const input = bind(document.createElement('input'), () => node.values[f.key], (v) => { node.values[f.key] = v; showPv(); });
        input.placeholder = '图片地址';
        const pick = document.createElement('button');
        pick.className = 'line';
        pick.innerHTML = `${icon('image')}<span>选图</span>`;
        pick.title = '选本地图片（会放进页面里）';
        pick.onclick = () => {
          imageTarget = { node, key: f.key };
          $('pickImage').click();
        };
        showPv();
        wrap.append(pv, input, pick);
        field(content, f.label, wrap);
      } else {
        const long = f.type !== 'text';
        const input = document.createElement(long ? 'textarea' : 'input');
        input.spellcheck = false;
        if (long) input.rows = f.key === 'code' ? 8 : Math.min(8, Math.max(3, String(node.values[f.key] || '').split('\n').length + 1));
        if (f.key === 'code') input.style.fontFamily = 'var(--mono)';
        field(content, f.label, bind(input, () => node.values[f.key], (v) => { node.values[f.key] = v; }));
      }
    }
  }

  node.style = node.style || {};
  const s = node.style;
  const look = section(box, 'look', '样子');
  const spacing = document.createElement('div');
  spacing.className = 'box';
  spacing.innerHTML = '<span class="tag">外边距</span><div class="inner"><span class="tag">内边距</span><div class="core">组件</div></div>';
  spacing.prepend(numberBox(s, 'marginTop', 't'));
  spacing.append(numberBox(s, 'marginBottom', 'b'));
  const inner = spacing.querySelector('.inner');
  inner.prepend(numberBox(s, 'padTop', 't'));
  inner.append(numberBox(s, 'padBottom', 'b'));
  field(look, '间距', spacing).querySelector('label').innerHTML = '间距<span class="note">像素，空着就是组件自己的</span>';
  const pair = document.createElement('div');
  pair.className = 'pair';
  field(pair, '高度', numberBox(s, 'minHeight', '', 'px'));
  field(pair, '圆角', numberBox(s, 'radius', '', 'px'));
  look.append(pair);
  pair.style.marginBottom = '12px';
  field(look, '宽度', slider(10, 100, () => (s.width === undefined ? 100 : s.width), (v) => { if (v >= 100) delete s.width; else s.width = v; }, '%'));
  field(look, '对齐', segs([['', icon('al-auto'), '跟随组件'], ['left', icon('al-left'), '靠左'], ['center', icon('al-center'), '居中'], ['right', icon('al-right'), '靠右']],
    () => s.align || '', (v) => { if (v) s.align = v; else delete s.align; }));
  field(look, '竖直', segs([['', VALIGN_ICON.top, '内容在上面'], ['center', VALIGN_ICON.center, '内容在中间'], ['bottom', VALIGN_ICON.bottom, '内容在下面']],
    () => s.valign || '', (v) => { if (v) s.valign = v; else delete s.valign; }), '组件比内容高的时候（拖了下面的把手），内容放在哪里');
  field(look, '出现', segs(ANIM_CHOICES, () => s.anim || '', (v) => { if (v) s.anim = v; else delete s.anim; }), '滚动到这里时怎么出现；在“预览”里能看到');
  field(look, '背景色', colorControl(() => s.bg, (v) => { if (v) s.bg = v; else delete s.bg; }));
  field(look, '文字色', colorControl(() => s.color, (v) => { if (v) s.color = v; else delete s.color; }));
  look.append(toggle('阴影', () => !!s.shadow, (v) => { if (v) s.shadow = true; else delete s.shadow; }));
  if (keepId === selected) box.scrollTop = scroll;
}

/* --- files ------------------------------------------------------------------------------------------------------------- */

function toast(text, good = true) {
  const t = $('toast');
  t.innerHTML = good ? icon('check') : '';
  t.append(document.createTextNode(text));
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 2400);
}

/* Asks inside the page: confirm() shows nothing in Qt's web view, and the answer was always "no". */
function ask(text, yes) {
  const box = $('askBox');
  $('askText').textContent = text;
  $('askYes').onclick = () => { box.close(); yes(); };
  $('askNo').onclick = () => box.close();
  box.showModal();
}

/* A picture put into the page lives inside page.json, in the undo history and in the browser's copy: a phone photo of 5 MB would fill
   all three. So it is made smaller first: no side longer than 1600 px, and a JPEG (quality .85) unless it has see-through parts,
   which stay a PNG. A picture that is already small and light is taken as it is. */
function shrinkImage(file) {
  const asIs = () => new Promise((ok, no) => {
    const r = new FileReader();
    r.onload = () => ok(r.result);
    r.onerror = no;
    r.readAsDataURL(file);
  });
  if (!/^image\/(png|jpe?g|webp|bmp)$/i.test(file.type)) return asIs();  // an SVG or a GIF stays as it is
  return new Promise((ok, no) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const long = Math.max(img.naturalWidth, img.naturalHeight);
      const scale = Math.min(1, 1600 / long);
      if (scale === 1 && file.size < 250 * 1024) { asIs().then(ok, no); return; }
      const c = document.createElement('canvas');
      c.width = Math.max(1, Math.round(img.naturalWidth * scale));
      c.height = Math.max(1, Math.round(img.naturalHeight * scale));
      const g = c.getContext('2d');
      g.drawImage(img, 0, 0, c.width, c.height);
      let see = false;
      if (file.type !== 'image/jpeg') {  // does any pixel let the page through?
        const px = g.getImageData(0, 0, c.width, c.height).data;
        for (let i = 3; i < px.length; i += 4 * 7) if (px[i] < 250) { see = true; break; }
      }
      ok(see ? c.toDataURL('image/png') : c.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); asIs().then(ok, no); };
    img.src = url;
  });
}

function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function saveProject(then) {
  const text = JSON.stringify(page, null, 1);
  if (bridge) {
    bridge.save(text, (where) => {
      if (where) {
        lastSaved = text;
        dirty = false;
      }
      buttons();
      toast(where ? `存好了：${where}` : '没有保存', !!where);
      if (typeof then === 'function') then(where);
    });
  } else {
    download('page.json', text, 'application/json');
    toast('下载了 page.json，下次用“打开”读回来');
    if (typeof then === 'function') then('');
  }
}

function exportPage() {
  const html = cpDocument(page);
  if (bridge) bridge.exportHtml(html, (where) => toast(where ? `导出了：${where}` : '没有导出', !!where));
  else download('index.html', html, 'text/html');
}

function preview() {
  if (bridge) bridge.preview(cpDocument(page));
  else window.open(URL.createObjectURL(new Blob([cpDocument(page)], { type: 'text/html' })), '_blank');
}

function loadPage(text, keepHistory) {
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    toast('这个文件读不了', false);
    return;
  }
  if (!data || !Array.isArray(data.blocks)) {
    toast('这不是 CodePage 的文件', false);
    return;
  }
  if (keepHistory) remember();
  page = { ...blankPage(), ...data, theme: { ...blankPage().theme, ...data.theme } };
  selected = null;
  changed();
  if (tab === 'design') fillDesign();
}

function freshIds(n) {
  n.id = newId();
  (n.children || []).forEach((l) => l.forEach(freshIds));
  return n;
}

function moveSelected(by) {
  const hit = selected ? findNode(selected) : null;
  if (!hit || hit.index + by < 0 || hit.index + by >= hit.list.length) return;
  remember();
  hit.list.splice(hit.index + by, 0, hit.list.splice(hit.index, 1)[0]);
  changed();
}

/* --- the backend: what on this page needs a server, written down for the AI --------------------------------------------- */

function backendNeeds() {
  /* Read the page as people will get it and list what cannot work without a server: forms, and buttons or links with nowhere to go. */
  const d = new DOMParser().parseFromString(cpDocument(page), 'text/html');
  const forms = [];
  const dead = [];
  const owner = (el) => {
    let n = el;
    while (n && n.parentElement && !(n.classList && n.classList.contains('cp-block'))) n = n.parentElement;
    return n;
  };
  const blocks = [...d.querySelectorAll('.cp-block')];
  const flat = [];
  cpWalk(page.blocks, (n) => flat.push(n));
  const nodeFor = (el) => {
    const b = owner(el);
    const i = blocks.indexOf(b);
    return i >= 0 ? flat[i] : null;
  };
  for (const f of d.querySelectorAll('form')) {
    const action = f.getAttribute('action') || '';
    const external = /^https?:\/\//.test(action);
    if (external && f.closest('.cp-search')) continue;  // a search box that already goes to a search engine
    const node = nodeFor(f);
    const fields = [...f.querySelectorAll('input,textarea,select')].filter((x) => x.type !== 'submit' && x.type !== 'button').map((x) => ({
      name: x.getAttribute('name') || x.getAttribute('aria-label') || x.getAttribute('placeholder') || '',
      type: x.tagName === 'TEXTAREA' ? '多行文字' : (x.getAttribute('type') || 'text'),
      required: x.hasAttribute('required'),
      hint: x.getAttribute('placeholder') || '',
    }));
    const btn = f.querySelector('button');
    const title = f.querySelector('h1,h2,h3');
    forms.push({ block: node ? nameOf(node) : '表单', title: title ? title.textContent.trim() : '', action, method: (f.getAttribute('method') || 'get').toUpperCase(), fields, button: btn ? btn.textContent.trim() : '' });
  }
  for (const a of d.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href').trim();
    const text = a.textContent.trim();
    if (!text || (href !== '#' && href !== '')) continue;
    if (a.closest('nav,footer,.cp-links,.cp-foot2-links')) continue;  // menu items are pages, not server work
    const node = nodeFor(a);
    dead.push({ text, block: node ? nameOf(node) : '' });
  }
  return { forms, dead };
}

function backendBrief(needs) {
  const lines = [`# 给「${page.title || '这个网页'}」写后端`, '',
    '前端已经在 CodePage 里拖好了：这个文件夹里的 page.json 是页面，导出的 index.html 是做成的网页。请写一个后端，让下面这些地方真的能用。', ''];
  if (needs.forms.length) {
    lines.push('## 要接住的表单', '');
    needs.forms.forEach((f, i) => {
      lines.push(`${i + 1}. ${f.title || f.block}（组件：${f.block}，按钮“${f.button || '提交'}”）`);
      lines.push(`   - 现在提交到：${f.action || '（没有地址）'}，方法 ${f.method}`);
      if (f.fields.length) lines.push(`   - 字段：${f.fields.map((x) => `${x.name || '（没有名字）'}（${x.type}${x.required ? '，必填' : ''}）`).join('、')}`);
    });
    lines.push('');
  }
  if (needs.dead.length) {
    lines.push('## 还没有去处的按钮和链接', '');
    for (const x of needs.dead) lines.push(`- “${x.text}”${x.block ? `（${x.block}）` : ''}`);
    lines.push('');
  }
  lines.push('## 怎么做', '',
    '- 后端代码放在这个文件夹的 backend/ 里，写清楚怎么启动。能用 Python 自带的库就别装新东西；真要装，先问我。',
    '- 页面上的改动（表单提交地址、按钮链接）用 @CodePage 改 page.json 再导出，不要直接手改 index.html，它会被下一次导出盖掉。联系表单有“提交地址”（url）一栏，填上后端的地址就不再走邮件。',
    '- 数据先存在本地文件里（比如 SQLite），不要连任何外部收费服务。',
    '- 做完自己启动一遍，真的提交一次表单，确认收到了。');
  return lines.join('\n');
}

function showBackend() {
  const needs = backendNeeds();
  const body = $('backendBody');
  body.innerHTML = '';
  const add = (title, chip, html) => {
    const n = document.createElement('div');
    n.className = 'need';
    n.innerHTML = `<div class="nh"><span></span><span class="chip"></span></div><div class="nb">${html}</div>`;
    n.querySelector('.nh span').textContent = title;
    n.querySelector('.chip').textContent = chip;
    body.append(n);
  };
  const esc = (t) => cpEsc(t);
  for (const f of needs.forms) {
    add(f.title || f.block, f.block, `提交到 <code>${esc(f.action || '没有地址')}</code> · ${esc(f.method)}`
      + (f.fields.length ? `<ul>${f.fields.map((x) => `<li>${esc(x.name || '没有名字')} <span class="note">${esc(x.type)}${x.required ? ' · 必填' : ''}</span></li>`).join('')}</ul>` : ''));
  }
  if (needs.dead.length) add('还没有去处的按钮和链接', `${needs.dead.length} 个`, `<ul>${needs.dead.map((x) => `<li>${esc(x.text)}${x.block ? ` <span class="note">${esc(x.block)}</span>` : ''}</li>`).join('')}</ul>`);
  if (!needs.forms.length && !needs.dead.length) {
    body.innerHTML = '<div class="empty">这个页面没有需要后端的地方：没有表单，按钮都有去处。<br>想加一个，可以先拖一个“联系表单”或“订阅邮箱”。</div>';
  }
  const ask = document.createElement('div');
  ask.className = 'ask';
  ask.innerHTML = '<label>还想让后端做什么（可以不写）</label><textarea id="backendMore" rows="3" placeholder="比如：收到留言时给我发一封邮件；做一个能看所有留言的后台页"></textarea>';
  body.append(ask);
  const log = document.createElement('pre');
  log.id = 'backendLog';
  log.hidden = true;
  log.style.cssText = 'margin-top:14px;border-radius:10px;max-height:220px;font-size:11.5px';
  body.append(log);
  $('sendBackend').disabled = !bridge || (!needs.forms.length && !needs.dead.length);
  $('backendWhere').textContent = bridge ? '会先保存页面，再把需求交给 Lumen 的团队' : '在 CodePage 窗口里才能直接交给 Lumen；这里可以复制需求，贴到 Lumen 里';
  $('copyBackend').disabled = !needs.forms.length && !needs.dead.length;
  showBackend.needs = needs;
  $('backendBox').showModal();
  $('backendMore').focus();
}

function briefNow() {
  const more = ($('backendMore') || {}).value || '';
  return backendBrief(showBackend.needs) + (more.trim() ? `\n\n## 另外\n\n${more.trim()}` : '');
}

function sendBackend() {
  if (!bridge) return;
  $('sendBackend').disabled = true;
  saveProject((where) => {
    if (!where) {
      $('sendBackend').disabled = false;
      return;
    }
    const log = $('backendLog');
    log.hidden = false;
    log.textContent = '交给 Lumen…\n';
    bridge.backend(briefNow(), (started) => {
      if (!started) {
        log.textContent += '没有开始：没有找到 Lumen（应在 D:\\CodeDoctor\\code-doctor）。\n';
        $('sendBackend').disabled = false;
      }
    });
  });
}

/* --- the code view: one CSS rule a line, numbered, quietly coloured -------------------------------------------------------- */

function showCode() { /* holds .raw: the page as exported */ }

function codeView(code) {
  const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const span = (cls, t) => `<span class="${cls}">${t}</span>`;
  /* one pass, so that what one rule wraps is never seen by the next */
  const htmlLine = (t) => esc(t).replace(/(&lt;\/?)([\w!-]+)|(\s)([\w:-]+)=("[^"]*"|'[^']*')|(\/?&gt;)/g, (m, open, tag, sp, name, value, close) => {
    if (open) return span('pn', open) + span('tg', tag);
    if (name) return sp + span('at', name) + span('pn', '=') + span('st', value);
    return span('pn', close);
  });
  const cssLine = (t) => {
    const e = esc(t);
    const open = e.indexOf('{');
    if (open < 0) return span('pr', e);
    const head = e.slice(0, open);
    const body = e.slice(open).replace(/([{;])([\w-]+):/g, (_, p, prop) => `${span('pn', p)}${span('pr', prop)}:`).replace(/(--[\w-]+)/g, (m) => span('vr', m));
    return `${span(head.startsWith('@') ? 'at' : 'sl', head)}${body.replace(/\}/g, span('pn', '}'))}`;
  };
  const jsLine = (t) => esc(t)
    .replace(/('[^']*'|"[^"]*")/g, (m) => span('st', m))
    .replace(/\b(function|var|let|const|return|if|else|for|new|document|window)\b/g, (m) => span('kw', m));
  const out = [];
  let mode = 'html';
  for (const raw of code.split('\n')) {
    if (mode === 'html' && /^<style>/.test(raw)) { out.push(htmlLine(raw)); mode = 'css'; continue; }
    if (mode === 'html' && /^<script>/.test(raw)) { out.push(htmlLine(raw)); mode = 'js'; continue; }
    if (mode !== 'html' && /^<\/(style|script)>/.test(raw)) { out.push(htmlLine(raw)); mode = 'html'; continue; }
    if (mode === 'css') {
      for (const piece of raw.replace(/\}(?!\})/g, '}\n').split('\n')) if (piece.trim()) out.push(cssLine(piece));
    } else if (mode === 'js') {
      out.push(jsLine(raw));
    } else {
      out.push(htmlLine(raw));
    }
  }
  return { html: out.map((l, i) => `<span class="ln" data-n="${i + 1}">${l || ' '}</span>`).join(''), lines: out.length };
}

function keys(e) {
  const editing = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '') && document.activeElement !== document.body;
  const mod = e.ctrlKey || e.metaKey;
  if (!editing && e.key === '/' && !mod) {
    e.preventDefault();
    showTab('parts');
    $('find').focus();
    return;
  }
  if (!editing && selected) {
    const hit = findNode(selected);
    if (mod && e.key.toLowerCase() === 'c' && hit) { clipboard = JSON.stringify(hit.node); toast('复制了'); return; }
    if (mod && e.key.toLowerCase() === 'd' && hit) {
      e.preventDefault();
      toolAct('copy');
      return;
    }
    if (e.key === 'ArrowUp' && e.altKey) { e.preventDefault(); moveSelected(-1); return; }
    if (e.key === 'ArrowDown' && e.altKey) { e.preventDefault(); moveSelected(1); return; }
    if (e.key === 'Escape') { select(null); return; }
  }
  if (!editing && mod && e.key.toLowerCase() === 'v' && clipboard) {
    e.preventDefault();
    remember();
    const copy = freshIds(JSON.parse(clipboard));
    const hit = selected ? findNode(selected) : null;
    if (hit) hit.list.splice(hit.index + 1, 0, copy);
    else page.blocks.push(copy);
    selected = copy.id;
    changed();
    return;
  }
  if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); }
  else if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); }
  else if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); saveProject(); }
  else if (!editing && (e.key === 'Delete' || e.key === 'Backspace') && selected) {
    e.preventDefault();
    toolAct('del');
  }
}

function wire() {
  document.addEventListener('keydown', keys);
  $('undo').onclick = undo;
  $('redo').onclick = redo;
  $('save').onclick = () => saveProject();
  $('export').onclick = exportPage;
  $('preview').onclick = preview;
  $('backend').onclick = showBackend;
  $('closeBackend').onclick = () => $('backendBox').close();
  $('copyBackend').onclick = () => navigator.clipboard.writeText(briefNow()).then(() => toast('需求复制好了'));
  $('sendBackend').onclick = sendBackend;
  $('pageTitle').addEventListener('change', (e) => {
    remember();
    page.title = e.target.value;
    changed();
  });
  $('pageTitle').addEventListener('keydown', (e) => { if (e.key === 'Enter') e.target.blur(); });
  $('pageTitle').addEventListener('input', fitTitle);
  $('find').addEventListener('input', (e) => fillParts(e.target.value));
  $('find').addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.target.value = ''; fillParts(''); e.target.blur(); } });
  $('open').onclick = () => {
    if (bridge) bridge.open((text) => { if (text) loadPage(text, true); });
    else $('pickJson').click();
  };
  $('pickJson').addEventListener('change', async (e) => {
    const f = e.target.files[0];
    if (f) loadPage(await f.text(), true);
    e.target.value = '';
  });
  $('pickImage').addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (!f || !imageTarget) return;
    const target = imageTarget;
    e.target.value = '';
    shrinkImage(f).then((url) => {
      remember();
      target.node.values[target.key] = url;  // in the page itself, so that one file is the whole site
      changed();
    }).catch(() => toast('这张图读不了', false));
  });
  $('showCode').onclick = () => {
    const code = cpDocument(page);
    showCode.raw = code;  // what is copied is exactly what is exported; only the view is spread out and coloured
    const view = codeView(code);
    $('codeText').innerHTML = view.html;
    $('codeSize').textContent = `${code.split('\n').length} 行（展开后 ${view.lines} 行）· ${(new Blob([code]).size / 1024).toFixed(1)} KB`;
    $('codeBox').showModal();
    $('codeText').focus();
  };
  $('closeCode').onclick = () => $('codeBox').close();
  $('copyCode').onclick = () => navigator.clipboard.writeText(showCode.raw || cpDocument(page)).then(() => toast('复制好了'));
  document.querySelectorAll('[data-width]').forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll('[data-width]').forEach((x) => x.classList.remove('on'));
      b.classList.add('on');
      const full = b.dataset.width === '100%';
      $('stage').style.width = full ? '100%' : `calc(${b.dataset.width} + 16px)`;
      $('stage').classList.toggle('device', !full);
      $('stageSize').textContent = full ? b.dataset.name : `${b.dataset.name} · ${parseInt(b.dataset.width, 10)}`;
      setTimeout(mark, 260);
    };
  });
  const thin = () => window.matchMedia('(max-width: 1000px)').matches;
  document.querySelectorAll('[data-tab]').forEach((b) => {
    b.onclick = () => {
      const again = b.classList.contains('on') && document.body.classList.contains('open-left');
      showTab(b.dataset.tab);
      if (thin()) { document.body.classList.toggle('open-left', !again); document.body.classList.remove('open-right'); }
    };
  });
  $('drawerRight').onclick = () => {
    document.body.classList.toggle('open-right');
    document.body.classList.remove('open-left');
  };
  window.addEventListener('resize', () => {
    clearTimeout(wire.t);
    wire.t = setTimeout(() => { fitShots($(tab), tab === 'parts'); mark(); }, 120);
  });
}

function follow() {
  /* In the window: the page file may be changed by the AI. Pick that up unless the person has unsaved changes. */
  setInterval(() => {
    if (!bridge || drag || dirty) return;  /* never while there are unsaved changes: save() would write into another project */
    bridge.pageFile((text) => {
      if (text && text !== lastSaved && !dirty) {
        lastSaved = text;
        loadPage(text, false);
      }
    });
  }, 1500);
}

function begin() {
  cpLoad(window.CP_COMPONENTS);
  for (const cat of CP.lib.categories) for (const item of cat.items) kindOf[item.id] = cat.id;
  page = blankPage();
  try {
    const kept = localStorage.getItem(STORE);
    if (kept) page = { ...page, ...JSON.parse(kept) };
    for (const id of JSON.parse(localStorage.getItem(FOLD) || '[]')) shut.add(id);
  } catch (e) { /* nothing kept */ }
  wire();
  fillFilters();
  showTab('parts');
  panel();
  buttons();
  startCanvas();
  if (window.qt && window.QWebChannel) {
    new QWebChannel(window.qt.webChannelTransport, (channel) => {
      bridge = channel.objects.host;
      if (bridge.said) bridge.said.connect((text) => {
        const log = $('backendLog');
        if (log) {
          log.hidden = false;
          log.textContent += text.endsWith('\n') ? text : text + '\n';
          log.scrollTop = log.scrollHeight;
        }
      });
      if (bridge.ended) bridge.ended.connect((how) => {
        const log = $('backendLog');
        if (log) log.textContent += `\n${how}\n`;
        $('sendBackend').disabled = false;
        toast(how, how.startsWith('完成'));
      });
      bridge.pageFile((t) => {
        if (t) {
          lastSaved = t;
          loadPage(t, false);
        }
        buttons();
      });
      follow();
    });
  }
}

begin();
