/* The page in the interface language. Its texts are written in Chinese, like the rest of Lumen, and looked up in the same
   catalog the Qt window uses (desktop/locale/en.json, sent by the bridge when the language is not Chinese):

     t('新聊天')                 -> "New chat"
     t('{0} 步', 3)              -> "3 steps"   (a template: the catalog's "templates")

   tests/daemon/test_web_locale.py checks every t('…') here has an English entry. */
let exact = {};
let templates = {};
let lang = 'zh';
let hant = null; // 繁體中文: the Chinese texts converted by the table python sends (desktop/zh_hant.py)

export function setCatalog(language, catalog) {
  lang = language || 'zh';
  hant = null;
  if (lang === 'zh-TW' && catalog && catalog.hant) {
    const table = {};
    const pairs = Array.from(catalog.hant.pairs);
    for (let i = 0; i + 1 < pairs.length; i += 2) table[pairs[i]] = pairs[i + 1];
    hant = { table, phrases: catalog.hant.phrases || [] };
  }
  exact = (catalog && catalog.exact) || {};
  templates = (catalog && catalog.templates) || {};
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang;
}

export function language() {
  return lang;
}

/* The team's Chinese names (光, 火花 ...) are shown beside the English ones only in a Chinese interface. */
export function chinese() {
  return lang === 'zh' || lang === 'zh-TW';
}

export function t(text, ...args) {
  let out = text;
  if (hant) {
    out = text;
    for (const [a, b] of hant.phrases) if (out.includes(a)) out = out.split(a).join(b);
    out = Array.from(out, (c) => hant.table[c] || c).join('');
  } else if (lang !== 'zh') out = (args.length ? templates[text] : exact[text]) || exact[text] || templates[text] || text;
  if (!args.length) return out;
  return out.replace(/\{(\d+)\}/g, (m, i) => {
    const v = args[Number(i)];
    if (v === undefined) return m;
    return typeof v === 'number' ? v.toLocaleString() : String(v);
  });
}
