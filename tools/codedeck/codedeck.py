"""CodeDeck's command line: slides and documents written as data, made into PowerPoint, Word, PDF and web pages.

    codedeck init <folder> [--doc]         slides (deck.json) or a document (doc.md)
    codedeck schema                        the guide
    codedeck build <folder>                out/deck.pptx or out/doc.docx, out/*.pdf, a web page, and a picture of every page

Everything is written directly: no Office, no extra libraries. Edge or Chrome makes the PDF and the pictures, and measures whether text fits.
Every command prints one JSON object as its last line.
"""
from __future__ import annotations

import right_python

right_python.use('playwright', 'PIL')

import argparse
import base64
from html import escape
import json
import mimetypes
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'kit'))

import charts  # noqa: E402
import layout  # noqa: E402
import markdown  # noqa: E402
import office  # noqa: E402

DECK = {'title': '演示标题', 'theme': '清爽', 'slides': [
    {'kind': 'title', 'title': '演示标题', 'subtitle': '一句话说明这次要讲什么'},
    {'kind': 'points', 'title': '这一页的结论写在标题里', 'points': ['第一点', '第二点', {'text': '第三点', 'note': '需要时再加一行说明'}]},
    {'kind': 'end', 'title': '谢谢', 'subtitle': ''},
]}
DOC = '# 文档标题\n\n开头一段话，说明这份文档是做什么的。\n\n## 第一部分\n\n- 要点一\n- 要点二\n\n## 第二部分\n\n| 项目 | 说明 |\n|---|---|\n| 甲 | 第一项 |\n| 乙 | 第二项 |\n'
DECK_EN = {'title': 'Presentation title', 'theme': '清爽', 'slides': [  # the theme names are what deck.json is written with, in any language
    {'kind': 'title', 'title': 'Presentation title', 'subtitle': 'One sentence on what this talk is about'},
    {'kind': 'points', 'title': "Put this page's conclusion in its title", 'points': ['First point', 'Second point', {'text': 'Third point', 'note': 'Add a line of explanation when needed'}]},
    {'kind': 'end', 'title': 'Thank you', 'subtitle': ''},
]}
DOC_EN = '# Document title\n\nA first paragraph saying what this document is for.\n\n## First part\n\n- Point one\n- Point two\n\n## Second part\n\n| Item | Note |\n|---|---|\n| A | First |\n| B | Second |\n'


def english() -> bool:
    """Whether what is written for the person (a new deck, the speaker notes) is in English: LUMEN_LANG, else the window's preference."""
    try:
        import i18n
        return i18n.language() != 'zh'
    except ImportError:
        return False


CHARTS = {'bar': charts.bar, 'hbar': charts.hbar, 'line': charts.line, 'donut': charts.donut}
DOC_CSS = """
@page{size:A4;margin:22mm 20mm}*{box-sizing:border-box}body{margin:0;font:11.5pt/1.7 'Microsoft YaHei',system-ui,sans-serif;color:#1c1f26}main{max-width:780px;margin:0 auto;padding:30px 20px}
h1{font-size:26pt;line-height:1.25;margin:0 0 16px}h2{font-size:17pt;margin:28px 0 8px}h3{font-size:13.5pt;margin:20px 0 6px}p{margin:8px 0}table{border-collapse:collapse;width:100%;margin:12px 0}
th,td{border:1px solid #bfc4ce;padding:6px 10px;text-align:left;vertical-align:top}th{background:#e9edf4}blockquote{margin:12px 0;padding:6px 16px;border-left:3px solid #2f6fed;font-style:italic}
pre{background:#f2f2f2;padding:10px 12px;font:10pt/1.5 Consolas,monospace;white-space:pre-wrap}code{font-family:Consolas,monospace;background:#eee;padding:0 3px}img{max-width:100%;display:block;margin:0 auto}figure{margin:14px 0}.break{break-after:page}
@media print{main{max-width:none;padding:0}}
"""


class Stop(Exception):
    """An answer with ok:false."""


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'deck.json').exists() or (folder / 'doc.md').exists():
        raise Stop(f'{folder} 已经是项目了')
    folder.mkdir(parents=True, exist_ok=True)
    if a.doc:
        (folder / 'doc.md').write_text(DOC_EN if english() else DOC, encoding='utf-8')
        return {'ok': True, 'project': str(folder), 'script': 'doc.md'}
    (folder / 'deck.json').write_text(json.dumps(DECK_EN if english() else DECK, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'ok': True, 'project': str(folder), 'script': 'deck.json'}


def cmd_schema(_a) -> dict:
    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8'), 'themes': list(layout.THEMES), 'slide_kinds': list(layout.KINDS), 'chart_types': list(CHARTS)}


def chart_svg(spec: dict, width: int, height: int) -> str:
    fn = CHARTS.get(spec.get('type', 'bar'))
    if fn is None:
        raise Stop(f'没有 {spec.get("type")} 这种图：有 {", ".join(CHARTS)}')
    kw = {'title': spec.get('title', ''), 'width': width}
    if spec.get('type') != 'hbar':
        kw['height'] = height
    return fn(spec.get('labels', []), spec.get('values', {}), **kw)


def _data_uri(path: Path) -> str:
    kind = mimetypes.guess_type(path.name)[0] or 'image/png'
    return f'data:{kind};base64,{base64.b64encode(path.read_bytes()).decode("ascii")}'


def _thing_html(t: dict, index: int, folder: Path) -> str:
    box = f'left:{t["x"]}px;top:{t["y"]}px;width:{t["w"]}px;height:{t["h"]}px'
    if t['kind'] == 'rect':
        return f'<div style="{box};background:{t["fill"]};border-radius:{t.get("radius", 0)}px"></div>'
    if t['kind'] == 'text':
        paras = ''
        for p in t['paras']:
            if not p.get('text'):
                continue
            style = f'font-size:{p.get("size", 20)}px;color:{p.get("color", "#000")};text-align:{p.get("align", "left")};margin:0 0 {p.get("space", 0)}px;font-weight:{700 if p.get("bold") else 400}'
            if p.get('bullet') or p.get('indent'):
                style += ';padding-left:1.3em'
            mark = '<span class="dot">•</span>' if p.get('bullet') else ''
            paras += f'<p style="{style}">{mark}{escape(p["text"])}</p>'
        align = {'middle': 'center', 'bottom': 'flex-end'}.get(t.get('valign'), 'flex-start')
        return f'<div class="text" data-fit="{index}" style="{box};justify-content:{align}"><div class="inner">{paras}</div></div>'
    if t['kind'] == 'image':
        path = folder / t.get('path', '')
        if not path.is_file():
            return f'<div class="missing" style="{box}">缺图片：{escape(t.get("path", ""))}</div>'
        t['file'] = str(path)
        return f'<img style="{box};object-fit:cover;border-radius:{t.get("radius", 0)}px" src="{_data_uri(path)}" alt="">'
    if t['kind'] == 'chart':
        return f'<div class="chart" data-chart="{index}" style="{box}">{chart_svg(t["chart"], int(t["w"] / 1.45), int(t["h"] / 1.45))}</div>'  # drawn small and shown big: its words are read across a room
    if t['kind'] == 'table':
        th = t['theme']
        rows = ''
        for ri, row in enumerate(t['rows']):
            bg = th['dark'] if ri == 0 else th['soft'] if ri % 2 == 0 else th['bg']
            color = th['on_dark'] if ri == 0 else th['ink']
            rows += '<tr>' + ''.join(f'<td style="background:{bg};color:{color};font-weight:{700 if ri == 0 else 400}">{escape(str(c))}</td>' for c in row) + '</tr>'
        return f'<div class="text" data-fit="{index}" style="{box}"><table>{rows}</table></div>'
    return ''


def deck_html(slides: list, title: str, folder: Path) -> str:
    pages = []
    for bg, things in slides:
        inner = ''.join(_thing_html(t, i, folder) for i, t in enumerate(things))
        pages.append(f'<section class="slide" style="background:{bg}">{inner}</section>')
    css = """
    @page{size:1280px 720px;margin:0}*{box-sizing:border-box}html,body{margin:0;background:#2a2c33}
    body{font-family:'Microsoft YaHei','PingFang SC',system-ui,sans-serif;line-height:1.35}.slide{position:relative;width:1280px;height:720px;overflow:hidden;margin:0 auto 16px;break-after:page}
    .slide>*{position:absolute}.text{display:flex;flex-direction:column;overflow:hidden}.inner{width:100%}.inner p{position:relative}.dot{position:absolute;left:.15em}
    .slide table{border-collapse:collapse;width:100%;font-size:24px}.slide td{padding:13px 18px;line-height:1.3}.chart svg{width:100%;height:100%;max-width:none}.missing{background:#fde8e6;color:#a02c22;display:flex;align-items:center;justify-content:center}
    @media print{body{background:none}.slide{margin:0}}
    """
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{escape(title)}</title><style>{css}</style></head><body>{"".join(pages)}</body></html>'


FIT_JS = """() => [...document.querySelectorAll('.slide')].flatMap((slide, n) =>
  [...slide.querySelectorAll('[data-fit]')].filter((b) => b.scrollHeight > b.clientHeight + 2 || b.scrollWidth > b.clientWidth + 2)
    .map((b) => ({slide: n + 1, over: b.scrollHeight - b.clientHeight, text: b.textContent.slice(0, 30)})))"""


def _cached(html_path: Path, folder: Path, name: str, slides: list | None, width: int, height: int) -> dict | None:
    """The last run's PDF and pictures, when the page is exactly the same: starting the browser is most of the time a build takes."""
    import hashlib

    out = folder / 'out'
    mark = out / f'.{name}.shots'
    key = hashlib.sha1(f'{width}x{height}'.encode() + html_path.read_bytes()).hexdigest()
    try:
        if mark.read_text(encoding='utf-8').split('\n')[0] != key:
            return None
        info = json.loads(mark.read_text(encoding='utf-8').split('\n', 1)[1])
    except (OSError, ValueError, IndexError):
        return None
    files = [out / f'{name}.pdf', *[folder / p for p in info.get('pictures', [])]]
    if not all(p.is_file() for p in files):
        return None
    if slides is not None:
        for i, (_bg, things) in enumerate(slides):
            for k, t in enumerate(things):
                if t['kind'] == 'chart':
                    pic = out / f'chart_{i + 1}_{k}.png'
                    if not pic.is_file():
                        return None
                    t['file'] = str(pic)
    return {'pictures': info.get('pictures', []), 'warnings': info.get('warnings', [])}


def _browser_work(html_path: Path, folder: Path, name: str, slides: list | None, width: int, height: int) -> dict:
    """PDF, pictures, chart pictures for PowerPoint, and whether the text fits. Whatever goes wrong with the browser, the deck itself is still made."""
    try:
        same = _cached(html_path, folder, name, slides, width, height)
        if same is not None:
            return same
        res = _browser_run(html_path, folder, name, slides, width, height)
        if res.get('pictures') and not res.get('failed'):
            import hashlib

            key = hashlib.sha1(f'{width}x{height}'.encode() + html_path.read_bytes()).hexdigest()
            (folder / 'out' / f'.{name}.shots').write_text(key + '\n' + json.dumps({'pictures': res['pictures'], 'warnings': res.get('warnings', [])}, ensure_ascii=False), encoding='utf-8')
        return res
    except Exception as e:  # noqa: BLE001 (playwright raises its own kinds, not only RuntimeError)
        return {'pictures': [], 'warnings': [f'PDF 和图片没有做成：{type(e).__name__}: {str(e)[:200]}'], 'failed': True}


def _browser_run(html_path: Path, folder: Path, name: str, slides: list | None, width: int, height: int) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {'warnings': ['这个 Python 里没有 playwright：没有 PDF 和图片'], 'failed': True}
    out = folder / 'out'
    answer: dict = {'pictures': [], 'warnings': []}
    with sync_playwright() as pw:
        browser = None
        for channel in ('msedge', 'chrome', None):
            try:
                browser = pw.chromium.launch(channel=channel, headless=True) if channel else pw.chromium.launch(headless=True)
                break
            except Exception:  # noqa: BLE001 (not here: the next one)
                continue
        if browser is None:
            return {'warnings': ['没有找到 Edge 或 Chrome：没有 PDF 和图片'], 'failed': True}
        try:
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.goto(html_path.as_uri())
            page.wait_for_timeout(200)
            if slides is not None:
                page.pdf(path=str(out / f'{name}.pdf'), width='1280px', height='720px', print_background=True)
                for over in page.evaluate(FIT_JS):
                    answer['warnings'].append(f'第 {over["slide"]} 页放不下，多了 {over["over"]} 像素：{over["text"]}')
                sections = page.query_selector_all('.slide')
                for i, sec in enumerate(sections):
                    say({'event': 'progress', 'at': f'第 {i + 1} / {len(sections)} 页'})
                    shot = out / f'page_{i + 1:02d}.png'
                    sec.screenshot(path=str(shot))
                    answer['pictures'].append(f'out/page_{i + 1:02d}.png')
                    for k, t in enumerate(slides[i][1]):
                        if t['kind'] == 'chart':
                            el = sec.query_selector(f'[data-chart="{k}"]')
                            if el is not None:
                                pic = out / f'chart_{i + 1}_{k}.png'
                                el.screenshot(path=str(pic))
                                t['file'] = str(pic)
            else:
                page.pdf(path=str(out / f'{name}.pdf'), format='A4', print_background=True)
                count = page.evaluate('Math.ceil(document.documentElement.scrollHeight / 1000)')
                for i in range(min(count, 6)):
                    shot = out / f'page_{i + 1:02d}.png'
                    page.evaluate(f'window.scrollTo(0, {i * 1000})')
                    page.screenshot(path=str(shot), clip=None)
                    answer['pictures'].append(f'out/page_{i + 1:02d}.png')
        finally:
            browser.close()
    return answer


def _notes_deck(data: dict, slides: list) -> list:
    out = []
    for i, s in enumerate(data['slides'], 1):
        words = office.word_count(json.dumps(s, ensure_ascii=False))
        if words > 90:
            out.append(f'第 {i} 页有 {words} 个字词，太满了：一页讲一件事。')
        points = s.get('points') or []
        if len(points) > 6:
            out.append(f'第 {i} 页有 {len(points)} 条，最多 6 条。')
    if len(slides) > 2 and not any(s.get('kind') == 'title' for s in data['slides']):
        out.append('没有标题页。')
    return out


def cmd_build(a) -> dict:
    folder = Path(a.folder).resolve()
    out = folder / 'out'
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob('page_*.png'):
        old.unlink()
    if (folder / 'deck.json').is_file():
        try:
            data = json.loads((folder / 'deck.json').read_text(encoding='utf-8-sig'))
        except ValueError as e:
            raise Stop(f'deck.json 写错了：{e}') from e
        theme = layout.THEMES.get(data.get('theme', '清爽'))
        if theme is None:
            raise Stop(f'没有 {data.get("theme")} 这个主题：有 {", ".join(layout.THEMES)}')
        count = len(data.get('slides') or [])
        slides = []
        for i, s in enumerate(data.get('slides') or [], 1):
            if s.get('kind', 'points') not in layout.KINDS:
                raise Stop(f'第 {i} 页：没有 {s.get("kind")} 这种页面。有：{", ".join(layout.KINDS)}')
            slides.append(layout.place(s, theme, i, count))
        html_path = out / 'deck.html'
        html_path.write_text(deck_html(slides, data.get('title', ''), folder), encoding='utf-8')
        res = _browser_work(html_path, folder, 'deck', slides, 1280, 720)
        said = [f"## {'Slide ' + str(i) if english() else '第 ' + str(i) + ' 页'} {s.get('title', '')}\n\n{s['notes']}\n" for i, s in enumerate(data.get('slides') or [], 1) if s.get('notes')]
        if said:
            (out / ('speaker-notes.md' if english() else '讲稿.md')).write_text('\n'.join(said), encoding='utf-8')
        office.write_pptx(out / 'deck.pptx', slides, data.get('title', ''))
        files = ['out/deck.pptx', 'out/deck.html']
        if (out / 'deck.pdf').is_file():
            files.append('out/deck.pdf')
        return {'ok': True, 'output': 'out/deck.pptx', 'files': files, 'pages': count, 'pictures': res.get('pictures', []), 'warnings': _notes_deck(data, slides) + res.get('warnings', [])}
    if (folder / 'doc.md').is_file():
        text = (folder / 'doc.md').read_text(encoding='utf-8-sig')
        blocks = markdown.parse(text)
        title = next((re.sub(r'[*`]', '', ''.join(p['text'] for p in b['inline'])) for b in blocks if b['kind'] == 'heading'), folder.name)
        html_path = out / 'doc.html'
        html_path.write_text(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{escape(title)}</title><style>{DOC_CSS}</style></head><body><main>{markdown.to_html(blocks)}</main></body></html>', encoding='utf-8')
        res = _browser_work(html_path, folder, 'doc', None, 860, 1000)
        office.write_docx(out / 'doc.docx', blocks, title, folder)
        missing = [b['path'] for b in blocks if b['kind'] == 'image' and not (folder / b['path']).is_file()]
        notes = [f'缺图片：{m}' for m in missing]
        files = ['out/doc.docx', 'out/doc.html']
        if (out / 'doc.pdf').is_file():
            files.append('out/doc.pdf')
        return {'ok': True, 'output': 'out/doc.docx', 'files': files, 'words': office.word_count(text), 'pictures': res.get('pictures', []), 'warnings': notes + res.get('warnings', [])}
    raise Stop(f'{folder} 里没有 deck.json 或 doc.md：先运行 init')


def cmd_outline(a) -> dict:
    """A plain outline into slides: # the title, ## one slide each, - its points, a line of its own a sentence to say aloud."""
    folder = Path(a.folder).resolve()
    source = Path(a.file)
    if not source.is_file():
        raise Stop(f'没有 {source}')
    slides, title = [], ''
    for line in source.read_text(encoding='utf-8-sig').splitlines():
        s = line.strip()
        if s.startswith('## '):
            slides.append({'kind': 'points', 'title': s[3:].strip(), 'points': []})
        elif s.startswith('# '):
            title = s[2:].strip()
            slides.insert(0, {'kind': 'title', 'title': title, 'subtitle': ''})
        elif s[:2] in ('- ', '* ') and slides:
            slides[-1].setdefault('points', []).append(s[2:].strip())
        elif s and slides:
            slides[-1]['notes'] = (slides[-1].get('notes', '') + ' ' + s).strip()
    if not slides:
        raise Stop('里面没有 # 标题 或 ## 页面')
    if len(slides) > 3:
        slides.insert(1, {'kind': 'agenda', 'title': 'Today' if english() else '今天讲什么', 'items': [x['title'] for x in slides[1:7]]})
    slides.append({'kind': 'end', 'title': 'Thank you' if english() else '谢谢', 'subtitle': ''})
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'deck.json').write_text(json.dumps({'title': title or source.stem, 'theme': a.theme, 'slides': slides}, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'ok': True, 'project': str(folder), 'pages': len(slides)}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codedeck')
    sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('outline')
    q.add_argument('folder')
    q.add_argument('file')
    q.add_argument('--theme', default='清爽')
    q.set_defaults(fn=cmd_outline)
    sub.add_parser('schema').set_defaults(fn=cmd_schema)
    q = sub.add_parser('init')
    q.add_argument('folder')
    q.add_argument('--doc', action='store_true')
    q.set_defaults(fn=cmd_init)
    q = sub.add_parser('build')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_build)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parser().parse_args(argv)
    try:
        answer = args.fn(args)
    except Stop as e:
        answer = {'ok': False, 'error': str(e)}
    except Exception as e:  # noqa: BLE001 (whatever else goes wrong still answers in JSON, so the window can say it)
        answer = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    say(answer)
    return 0 if answer.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
