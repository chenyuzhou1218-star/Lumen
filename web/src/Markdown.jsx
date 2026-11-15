import { useMemo, useRef, useEffect } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { t } from './i18n.js';

marked.setOptions({ gfm: true, breaks: true });

/* An answer as people read it: headings, lists, tables, code with a copy button. Links open in Lumen's browser. */
export function Markdown({ text, api }) {
  const html = useMemo(() => DOMPurify.sanitize(marked.parse(text || '')), [text]);
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.querySelectorAll('pre').forEach((pre) => {
      if (pre.querySelector('.copy')) return;
      const lang = (pre.querySelector('code')?.className.match(/language-(\w+)/) || [])[1];
      const bar = document.createElement('div');
      bar.className = 'code-bar';
      bar.innerHTML = `<span>${lang || t('代码')}</span><button class="copy" type="button">${t('复制')}</button>`;
      bar.querySelector('button').onclick = (e) => {
        api.copy(pre.querySelector('code')?.innerText || pre.innerText);
        const btn = e.currentTarget;
        btn.textContent = t('已复制');
        setTimeout(() => { btn.textContent = t('复制'); }, 1400);
      };
      pre.prepend(bar);
    });
  }, [html, api]);
  const click = (e) => {
    const a = e.target.closest('a');
    if (a && a.getAttribute('href')) {
      e.preventDefault();
      api.openLink(a.href);
    }
  };
  return <div className="md" ref={ref} onClick={click} dangerouslySetInnerHTML={{ __html: html }} />;
}
