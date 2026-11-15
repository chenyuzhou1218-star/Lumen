/* A page (page.json) -> HTML. The same steps as render() in codepage.py: the window and the command line must give the same page.
   A node: {id, type, values:{}, style:{}, children:[[...], ...]}. Components come from components.json. */
'use strict';

const CP = { lib: null, byId: {} };

function cpLoad(lib) {
  CP.lib = lib;
  CP.byId = {};
  for (const cat of lib.categories) for (const item of cat.items) CP.byId[item.id] = item;
}

function cpEsc(text) {
  return String(text == null ? '' : text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function cpValue(text) {
  const value = String(text == null ? '' : text);
  return value.startsWith('@') && CP.lib.placeholders[value] ? CP.lib.placeholders[value] : value;
}

function cpFill(html, values, raw) {
  html = html.replace(/\{\{#(\w+)\}\}([\s\S]*?)\{\{\/\1\}\}/g, (_, key, inner) =>
    String(values[key] || '').split('\n').filter((l) => l.trim()).map((line) => {
      const parts = line.split('|').map((p) => p.trim());
      return inner.replace(/\{\{(\d)\}\}/g, (__, i) => cpEsc(cpValue(parts[i - 1])));
    }).join(''));
  /* {{url/mailto:email}}: the first that has a value, with what stands before its ':' put in front (the same in codepage.py) */
  html = html.replace(/\{\{([\w:]+(?:\/[\w:]+)+)\}\}/g, (_, alts) => {
    for (const alt of alts.split('/')) {
      const cut = alt.lastIndexOf(':');
      const prefix = cut >= 0 ? alt.slice(0, cut + 1) : '';
      const key = alt.slice(cut + 1);
      if (String(values[key] || '').trim()) return cpEsc(prefix + cpValue(values[key]));
    }
    return '';
  });
  return html.replace(/\{\{(\w+)\}\}/g, (_, key) => (raw ? String(values[key] || '') : cpEsc(cpValue(values[key]))));
}

function cpStyle(s) {
  s = s || {};
  const out = [];
  const px = (name, value) => { if (value !== undefined && value !== '' && value !== null) out.push(`${name}:${Number(value) || 0}px`); };
  px('padding-top', s.padTop);
  px('padding-bottom', s.padBottom);
  px('margin-top', s.marginTop);
  px('margin-bottom', s.marginBottom);
  px('min-height', s.minHeight);
  px('border-radius', s.radius);
  if (s.bg) out.push(`background:${s.bg}`);
  if (s.color) out.push(`color:${s.color}`);
  if (s.align) out.push(`text-align:${s.align}`);
  if (s.width && Number(s.width) < 100) {
    out.push(`width:${Number(s.width)}%`);
    out.push(s.align === 'right' ? 'margin-left:auto' : s.align === 'left' ? 'margin-right:auto' : 'margin-left:auto;margin-right:auto');
  }
  if (s.shadow) out.push('box-shadow:0 10px 28px rgba(0,0,0,.14)');
  /* a block made taller than what is in it: where its content sits in the height */
  if (CP_VALIGN[s.valign]) out.push(`display:flex;flex-direction:column;justify-content:${CP_VALIGN[s.valign]}`);
  return cpEsc(out.join(';'));
}

const CP_VALIGN = { center: 'center', bottom: 'flex-end' };
const CP_ANIMS = ['up', 'fade', 'zoom', 'left', 'right'];

function cpAnim(node) {
  const a = (node.style || {}).anim;
  return CP_ANIMS.includes(a) ? ` cp-anim cp-anim-${a}` : '';
}

function cpNode(node, edit) {
  const item = CP.byId[node.type];
  if (!item) return '';
  /* a field the page file leaves out has the component's own value (the same in codepage.py) */
  const values = { ...Object.fromEntries((item.fields || []).map((f) => [f.key, f.value === undefined ? '' : f.value])), ...(node.values || {}) };
  let html = cpFill(item.html, values, !!item.raw);
  const kids = node.children || [];
  const slot = (i) => `<div class="cp-slot"${edit ? ` data-slot="${node.id}:${i}"` : ''}>${(kids[i] || []).map((k) => cpNode(k, edit)).join('')}</div>`;
  html = html.replace(/\{\{slot:(\d)\}\}/g, (_, i) => slot(Number(i)));
  /* a deck of slides: one slide for each list of children, as many as there are */
  html = html.replace(/\{\{slot:\*\}\}/g, () => kids.map((_, i) => `<section class="cp-slide">${slot(i)}</section>`).join(''));
  const style = cpStyle(node.style);
  return `<div class="cp-block${cpAnim(node)}"${edit ? ` data-node="${node.id}"` : ''}${style ? ` style="${style}"` : ''}>${html}</div>`;
}

function cpWalk(nodes, fn) {
  for (const n of nodes) {
    fn(n);
    for (const list of n.children || []) cpWalk(list, fn);
  }
}

function cpCss(page) {
  const seen = new Set();
  const css = [];
  const add = (id) => {
    if (seen.has(id) || !CP.byId[id]) return;
    seen.add(id);
    if (CP.byId[id].needs) add(CP.byId[id].needs);
    if (CP.byId[id].css) css.push(CP.byId[id].css);
  };
  const scripts = [];
  let moving = false;
  cpWalk(page.blocks || [], (n) => {
    add(n.type);
    const js = (CP.byId[n.type] || {}).js;
    if (js && !scripts.includes(js)) scripts.push(js);
    if (cpAnim(n)) moving = true;
  });
  if (moving && CP.lib.anim_js) scripts.push(CP.lib.anim_js);
  /* the same defaults as a new page (blank() in codepage.py): a page file may name only what it changes */
  const t = { ...CP.lib.themes[0], radius: 10, font: CP.lib.fonts[0].css, ...(page.theme || {}) };
  const on = (hex) => {  /* white or near-black text, whichever reads on this colour */
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim());
    if (!m) return '#fff';
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? '#111' : '#fff';
  };
  const root = `:root{--cp-on-primary:${on(t.primary)};--cp-primary:${t.primary};--cp-bg:${t.bg};--cp-ink:${t.ink};--cp-soft:${t.soft};--cp-line:${t.line};--cp-radius:${Number(t.radius === undefined ? 10 : t.radius)}px;--cp-font:${t.font}}`;
  return { css: [root, CP.lib.base, ...css].join('\n'), scripts };
}

/* edit: marks for the builder's canvas; the page people get has none of them. */
function cpBody(page, edit) {
  return (page.blocks || []).map((n) => cpNode(n, edit)).join('\n');
}

function cpDocument(page) {
  const { css, scripts } = cpCss(page);
  const js = scripts.length ? `\n<script>\n${scripts.join('\n')}\n</script>` : '';
  const title = cpEsc(page.title || '');
  const note = page.description ? `\n<meta name="description" content="${cpEsc(page.description)}">` : '';
  return `<!doctype html>
<html lang="${cpEsc(page.lang || 'zh-CN')}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>${note}
<style>
${css}
</style>
</head>
<body>
${cpBody(page, false)}${js}
</body>
</html>
`;
}

if (typeof module !== 'undefined') module.exports = { cpLoad, cpDocument };
