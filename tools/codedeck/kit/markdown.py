"""A document is written in Markdown: headings, lists, tables, pictures, quotes, code. This reads it into blocks for Word and for the web page."""
from __future__ import annotations

from html import escape
import re

INLINE = re.compile(r'(\*\*.+?\*\*|`[^`]+`|\*[^*\s][^*]*\*)')


def inline(text: str) -> list:
    out = []
    for piece in INLINE.split(text):
        if not piece:
            continue
        if piece.startswith('**') and piece.endswith('**') and len(piece) > 4:
            out.append({'text': piece[2:-2], 'bold': True})
        elif piece.startswith('`') and piece.endswith('`') and len(piece) > 2:
            out.append({'text': piece[1:-1], 'code': True})
        elif piece.startswith('*') and piece.endswith('*') and len(piece) > 2:
            out.append({'text': piece[1:-1], 'italic': True})
        else:
            out.append({'text': piece})
    return out or [{'text': ''}]


def _cells(line: str) -> list:
    return [c.strip() for c in line.strip().strip('|').split('|')]


def parse(text: str) -> list:
    lines = text.replace('\r\n', '\n').split('\n')
    blocks: list = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
        elif s.startswith('```'):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i])
                i += 1
            i += 1
            blocks.append({'kind': 'code', 'text': '\n'.join(code)})
        elif re.match(r'^#{1,4}\s', s):
            level = len(s) - len(s.lstrip('#'))
            blocks.append({'kind': 'heading', 'level': level, 'inline': inline(s[level:].strip())})
            i += 1
        elif s in ('---', '***'):
            blocks.append({'kind': 'rule'})
            i += 1
        elif s in ('<!-- 换页 -->', '<!-- pagebreak -->'):
            blocks.append({'kind': 'pagebreak'})
            i += 1
        elif re.match(r'^!\[.*\]\(.+\)$', s):
            m = re.match(r'^!\[(.*)\]\((.+)\)$', s)
            blocks.append({'kind': 'image', 'alt': m.group(1), 'path': m.group(2)})
            i += 1
        elif s.startswith('|') and i + 1 < len(lines) and re.match(r'^\|?[\s:|-]+\|?$', lines[i + 1].strip()):
            rows = [[inline(c) for c in _cells(s)]]
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append([inline(c) for c in _cells(lines[i])])
                i += 1
            blocks.append({'kind': 'table', 'rows': rows})
        elif s.startswith('>'):
            part = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                part.append(lines[i].strip().lstrip('>').strip())
                i += 1
            blocks.append({'kind': 'quote', 'inline': inline(' '.join(part))})
        elif re.match(r'^([-*+]|\d+\.)\s', s):
            ordered = s[0].isdigit()
            items = []
            while i < len(lines) and re.match(r'^\s*([-*+]|\d+\.)\s', lines[i]):
                items.append(inline(re.sub(r'^\s*([-*+]|\d+\.)\s+', '', lines[i])))
                i += 1
            blocks.append({'kind': 'list', 'ordered': ordered, 'items': items})
        else:
            part = []
            while i < len(lines) and lines[i].strip() and not re.match(r'^(#{1,4}\s|```|>|\||[-*+]\s|\d+\.\s|!\[)', lines[i].strip()):
                part.append(lines[i].strip())
                i += 1
            if not part:  # a line that looked like the start of something and was not
                part = [s]
                i += 1
            blocks.append({'kind': 'para', 'inline': inline(' '.join(part))})
    return blocks


def _html_inline(pieces: list) -> str:
    out = ''
    for p in pieces:
        t = escape(p['text'])
        if p.get('bold'):
            t = f'<strong>{t}</strong>'
        if p.get('italic'):
            t = f'<em>{t}</em>'
        if p.get('code'):
            t = f'<code>{t}</code>'
        out += t
    return out


def to_html(blocks: list) -> str:
    out = []
    for b in blocks:
        kind = b['kind']
        if kind == 'heading':
            out.append(f'<h{b["level"]}>{_html_inline(b["inline"])}</h{b["level"]}>')
        elif kind == 'para':
            out.append(f'<p>{_html_inline(b["inline"])}</p>')
        elif kind == 'quote':
            out.append(f'<blockquote>{_html_inline(b["inline"])}</blockquote>')
        elif kind == 'list':
            tag = 'ol' if b['ordered'] else 'ul'
            out.append(f'<{tag}>' + ''.join(f'<li>{_html_inline(i)}</li>' for i in b['items']) + f'</{tag}>')
        elif kind == 'code':
            out.append(f'<pre>{escape(b["text"])}</pre>')
        elif kind == 'table':
            rows = ''
            for ri, row in enumerate(b['rows']):
                tag = 'th' if ri == 0 else 'td'
                rows += '<tr>' + ''.join(f'<{tag}>{_html_inline(c)}</{tag}>' for c in row) + '</tr>'
            out.append(f'<table>{rows}</table>')
        elif kind == 'rule':
            out.append('<hr>')
        elif kind == 'pagebreak':
            out.append('<div class="break"></div>')
        elif kind == 'image':
            out.append(f'<figure><img src="../{escape(b["path"])}" alt="{escape(b["alt"])}"></figure>')
    return '\n'.join(out)
