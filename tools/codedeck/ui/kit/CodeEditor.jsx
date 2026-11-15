import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

/* A code box: line numbers in a quiet gutter, the current line faintly marked, tabs four spaces wide, a little colour.
   It is a plain textarea over a coloured copy of the same text, so typing, selecting, undo and the IME are the
   browser's own. language: json | py | js | md | log | '' (by the file's name: langOf). */

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const KW = {
  py: 'False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield|self|print',
  js: 'break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|false|finally|for|function|if|import|in|instanceof|let|new|null|return|super|switch|this|throw|true|try|typeof|undefined|var|void|while|with|yield|async|await|of',
};

const RULES = {
  json: [
    [/"(?:[^"\\\n]|\\.)*"(?=\s*:)/y, 'key'], [/"(?:[^"\\\n]|\\.)*"?/y, 'str'], [/-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/y, 'num'],
    [/\b(?:true|false|null)\b/y, 'kw'], [/[{}[\],:]/y, 'punc'],
  ],
  py: [
    [/#.*/y, 'com'], [/(?:[rRbBfFuU]{0,2})("""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$))/y, 'str'], [/(?:[rRbBfFuU]{0,2})("(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?)/y, 'str'],
    [/\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/y, 'num'], [new RegExp(`\\b(?:${KW.py})\\b`, 'y'), 'kw'],
  ],
  js: [
    [/\/\/.*/y, 'com'], [/\/\*[\s\S]*?(?:\*\/|$)/y, 'com'], [/`(?:[^`\\]|\\.)*`?/y, 'str'], [/"(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?/y, 'str'],
    [/\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/y, 'num'], [new RegExp(`\\b(?:${KW.js})\\b`, 'y'), 'kw'],
  ],
  md: [
    [/^#{1,6} .*/my, 'head'], [/^```.*$/my, 'com'], [/`[^`\n]+`/y, 'str'], [/^\s*(?:[-*+]|\d+\.) /my, 'kw'], [/\*\*[^*\n]+\*\*/y, 'key'],
  ],
  log: [
    [/\b(?:nan|NaN|inf|error|Error|ERROR|Traceback|Exception)\b/y, 'key'], [/\b(?:warn|warning|WARNING)\b/y, 'num'], [/-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/y, 'str'],
  ],
};

function paint(text, lang) {
  const rules = RULES[lang];
  if (!rules) return esc(text);
  let out = '';
  let plain = '';
  let i = 0;
  const n = text.length;
  while (i < n) {
    let hit = null;
    for (const [re, cls] of rules) {
      re.lastIndex = i;
      const m = re.exec(text);
      if (m && m[0].length) { hit = [m[0], cls]; break; }
    }
    if (hit) {
      if (plain) { out += esc(plain); plain = ''; }
      out += `<span class="tok-${hit[1]}">${esc(hit[0])}</span>`;
      i += hit[0].length;
    } else {
      // a word at a time, so a keyword is only found at the start of a word
      const m = /[A-Za-z_$][\w$]*|\s+|./y;
      m.lastIndex = i;
      const w = m.exec(text)[0];
      plain += w;
      i += w.length;
    }
  }
  return out + esc(plain);
}

export function langOf(name) {
  const ext = String(name || '').split('.').pop().toLowerCase();
  return { json: 'json', py: 'py', js: 'js', mjs: 'js', ts: 'js', md: 'md', log: 'log', txt: 'log', csv: 'log', out: 'log' }[ext] || '';
}

let ruler = null;
function textWidth(s) {
  if (!ruler) ruler = document.createElement('canvas').getContext('2d');
  ruler.font = `13px ${getComputedStyle(document.documentElement).getPropertyValue('--mono').trim() || 'monospace'}`;
  return ruler.measureText(s.replace(/\t/g, '    ')).width;
}

export function CodeEditor({ value, onChange, readOnly, language = '', placeholder, onSave, follow }) {
  const area = useRef(null);
  const scroller = useRef(null);
  const [line, setLine] = useState(0);
  const html = useMemo(() => paint(value || '', language) + '\n ', [value, language]);
  const lines = useMemo(() => (value || '').split('\n').length, [value]);

  const where = () => {
    const el = area.current;
    if (!el) return;
    const before = el.value.slice(0, el.selectionEnd);
    const row = before.split('\n').length - 1;
    setLine(row);
    // keep the caret in sight: the textarea is as large as the text, so the box around it scrolls
    const sc = scroller.current;
    const top = 10 + row * 20;
    if (top < sc.scrollTop) sc.scrollTop = top - 10;
    else if (top + 30 > sc.scrollTop + sc.clientHeight) sc.scrollTop = top + 30 - sc.clientHeight;
    const col = textWidth(before.slice(before.lastIndexOf('\n') + 1));
    const gutter = sc.querySelector('.gutter');
    const x = (gutter ? gutter.offsetWidth : 0) + 6 + col;
    const room = sc.clientWidth;
    if (x + 24 > sc.scrollLeft + room) sc.scrollLeft = x + 24 - room;
    else if (x - (gutter ? gutter.offsetWidth : 0) - 10 < sc.scrollLeft) sc.scrollLeft = Math.max(0, x - (gutter ? gutter.offsetWidth : 0) - 40);
  };

  // a log that grows is followed to its end
  useLayoutEffect(() => {
    if (follow && scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [value, follow]);

  useEffect(() => {
    const el = area.current;
    if (!el) return undefined;
    const f = () => { if (document.activeElement === el) where(); };
    document.addEventListener('selectionchange', f);
    return () => document.removeEventListener('selectionchange', f);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const edit = (text, a, b) => {
    const el = area.current;
    // through the browser's own editing, so Ctrl+Z still undoes it
    el.setSelectionRange(a, b);
    if (!document.execCommand('insertText', false, text)) {
      el.setRangeText(text, a, b, 'end');
      onChange(el.value);
    }
  };

  const key = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); if (onSave) onSave(); return; }
    if (readOnly) return;
    const el = e.currentTarget;
    const { selectionStart: s, selectionEnd: t, value: v } = el;
    if (e.key === 'Tab') {
      e.preventDefault();
      const from = v.lastIndexOf('\n', s - 1) + 1;
      if (s === t && !e.shiftKey) { edit('    ', s, t); return; }
      const to = t;
      const block = v.slice(from, to);
      const next = e.shiftKey ? block.replace(/^ {1,4}/gm, '') : block.replace(/^/gm, '    ');
      edit(next, from, to);
      el.setSelectionRange(from, from + next.length);
    } else if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      const from = v.lastIndexOf('\n', s - 1) + 1;
      const indent = /^[ \t]*/.exec(v.slice(from, s))[0];
      const more = /[:{[(]\s*$/.test(v.slice(from, s)) ? '    ' : '';
      edit('\n' + indent + more, s, t);
    }
  };

  return (
    <div className={`code${readOnly ? ' read' : ''}`}>
      <div className="scroller" ref={scroller}>
        <div className="sheet">
          <div className="gutter" style={{ minWidth: `${Math.max(3, String(lines).length) + 2.2}ch` }}>
            {Array.from({ length: lines }, (_, i) => <div key={i} className={i === line && !readOnly ? 'on' : ''}>{i + 1}</div>)}
          </div>
          <div className="text">
            {!readOnly && <div className="line-on" style={{ top: 10 + line * 20 }} />}
            <pre aria-hidden="true" dangerouslySetInnerHTML={{ __html: html }} />
            <textarea ref={area} value={value || ''} spellCheck={false} wrap="off" readOnly={readOnly} placeholder={placeholder}
              autoCapitalize="off" autoComplete="off" autoCorrect="off"
              onChange={(e) => onChange && onChange(e.target.value)} onKeyDown={key} onClick={where} onFocus={where} />
          </div>
        </div>
      </div>
    </div>
  );
}
