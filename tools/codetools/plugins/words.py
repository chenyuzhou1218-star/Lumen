"""Writing: long books, subtitles, translation checks, a voice, quizzes, sources."""
from __future__ import annotations

from collections import Counter
from html import escape
import json
import os
import sys
from pathlib import Path
import re
import subprocess
import uuid
import zipfile

from kit import Action, Field, Plugin, Stop, done, need, number, path_of

CHAPTER = re.compile(r'^(第[一二三四五六七八九十百千0-9]+[章回节卷].*|#+\s+.+|Chapter\s+\d+.*)$', re.M)


def _read(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ('utf-8-sig', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise Stop('读不出这个文件的编码')


def _chapters(text: str) -> list:
    marks = list(CHAPTER.finditer(text))
    if not marks:
        return [('全文', text)]
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(0).lstrip('# ').strip(), text[m.end():end].strip()))
    return out


def count_words(t: str) -> int:
    return len(re.findall(r'[一-鿿]|[A-Za-z0-9]+', t))


def book_check(a, out):
    """What a tired editor misses: who appears when, gaps, repeated phrases, chapters of odd length."""
    text = _read(path_of(a, 'file'))
    chapters = _chapters(text)
    names = [n.strip() for n in re.split(r'[,，、\s]+', str(a.get('names') or '')) if n.strip()]
    rows = [['章节', '字数', *names]]
    seen = {n: [] for n in names}
    for i, (title, body) in enumerate(chapters):
        rows.append([title[:24], count_words(body), *[body.count(n) for n in names]])
        for n in names:
            if n in body:
                seen[n].append(i)
    warnings = []
    for n, where in seen.items():
        if not where:
            warnings.append(f'{n} 一次都没出现')
            continue
        for x, y in zip(where, where[1:]):
            if y - x > max(4, len(chapters) // 3):
                warnings.append(f'{n} 从第 {x + 1} 章到第 {y + 1} 章之间消失了')
    lengths = [count_words(b) for _, b in chapters]
    mean = sum(lengths) / len(lengths)
    for (title, _), n in zip(chapters, lengths):
        if len(chapters) > 3 and (n < mean * .4 or n > mean * 2.2):
            warnings.append(f'{title[:20]} 有 {n} 字，和平均 {mean:.0f} 字差很多')
    grams = Counter(text[i:i + 6] for i in range(len(text) - 5) if re.fullmatch(r'[一-鿿]{6}', text[i:i + 6]))
    repeats = [(g, c) for g, c in grams.most_common(8) if c >= 4]
    if repeats:
        warnings.append('反复出现的句子片段：' + '、'.join(f'{g}（{c} 次）' for g, c in repeats[:5]))
    return done(f'{len(chapters)} 章，共 {sum(lengths)} 字', table=rows, warnings=warnings)


def book_epub(a, out):
    """An e-book any reader opens."""
    source = path_of(a, 'file')
    text = _read(source)
    title = str(a.get('title') or source.stem)
    author = str(a.get('author') or '')
    chapters = _chapters(text)
    book = uuid.uuid4()
    path = out / f'{re.sub(r"[^\w一-鿿]+", "_", title)}.epub'
    items, spine, nav = [], [], []
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        for i, (head, body) in enumerate(chapters, 1):
            name = f'c{i}.xhtml'
            paras = ''.join(f'<p>{escape(p.strip())}</p>' for p in body.split('\n') if p.strip())
            z.writestr(f'OEBPS/{name}', f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>{escape(head)}</title></head><body><h1>{escape(head)}</h1>{paras}</body></html>', compress_type=zipfile.ZIP_DEFLATED)
            items.append(f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="c{i}"/>')
            nav.append(f'<li><a href="{name}">{escape(head)}</a></li>')
        z.writestr('OEBPS/nav.xhtml', f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>目录</title></head><body><nav epub:type="toc"><ol>{"".join(nav)}</ol></nav></body></html>')
        z.writestr('OEBPS/book.opf', f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">urn:uuid:{book}</dc:identifier><dc:title>{escape(title)}</dc:title><dc:language>zh</dc:language><dc:creator>{escape(author)}</dc:creator><meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>{"".join(items)}</manifest><spine>{"".join(spine)}</spine></package>')
    return done(f'{len(chapters)} 章的电子书', files=[path])


# --- subtitles ---------------------------------------------------------------------------------------------------------

STAMP = re.compile(r'(\d+):(\d\d):(\d\d)[,.](\d{3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{3})')


def _subs(text: str) -> list:
    out = []
    for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n').strip()):
        m = STAMP.search(block)
        if m:
            g = [int(x) for x in m.groups()]
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
            body = block[m.end():].strip()
            out.append([start, end, body])
    return out


def _stamp(t: float, sep: str = ',') -> str:
    t = max(0, t)
    ms = round(t * 1000)
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}'


def sub_shift(a, out):
    src = path_of(a, 'file')
    subs = _subs(_read(src))
    if not subs:
        raise Stop('里面没有字幕')
    by = number(a, 'seconds', 0)
    speed = number(a, 'speed', 1) or 1
    lines = []
    for i, (s, e, t) in enumerate(subs, 1):
        lines.append(f'{i}\n{_stamp(s / speed + by)} --> {_stamp(e / speed + by)}\n{t}\n')
    srt = out / f'{src.stem}_改.srt'
    srt.write_text('\n'.join(lines), encoding='utf-8')
    vtt = out / f'{src.stem}_改.vtt'
    vtt.write_text('WEBVTT\n\n' + '\n'.join(f'{_stamp(s / speed + by, ".")} --> {_stamp(e / speed + by, ".")}\n{t}\n' for s, e, t in subs), encoding='utf-8')
    return done(f'{len(subs)} 条字幕，移动了 {by:g} 秒', files=[srt, vtt])


def sub_check(a, out):
    subs = _subs(_read(path_of(a, 'file')))
    if not subs:
        raise Stop('里面没有字幕')
    warnings = []
    for i, (s, e, t) in enumerate(subs, 1):
        if e <= s:
            warnings.append(f'第 {i} 条结束时间不晚于开始时间')
        if i < len(subs) and subs[i][0] < e - .001:
            warnings.append(f'第 {i} 条和下一条重叠')
        speed = len(re.sub(r'\s', '', t)) / max(.01, e - s)
        if speed > 12:
            warnings.append(f'第 {i} 条每秒 {speed:.0f} 字，读不过来')
        if e - s < .6:
            warnings.append(f'第 {i} 条只显示 {e - s:.2f} 秒')
    return done(f'{len(subs)} 条字幕，共 {subs[-1][1] / 60:.1f} 分钟', warnings=warnings[:40])


def sub_make(a, out):
    """A script, one sentence a line, timed by how long it takes to say."""
    pace = number(a, 'pace', 4.5)
    t = 0.0
    lines = []
    for i, line in enumerate(x.strip() for x in str(need(a, 'text', '台词')).splitlines() if x.strip()):
        length = max(1.0, len(line) / pace)
        lines.append(f'{i + 1}\n{_stamp(t)} --> {_stamp(t + length)}\n{line}\n')
        t += length + .15
    path = out / 'subtitles.srt'
    path.write_text('\n'.join(lines), encoding='utf-8')
    return done(f'{len(lines)} 条，约 {t:.0f} 秒', files=[path])


# --- translation ------------------------------------------------------------------------------------------------------

def trans_check(a, out):
    """Compares a source and its translation: the same number of lines, the terms in the list, numbers and placeholders kept."""
    src = _read(path_of(a, 'source')).splitlines()
    dst = _read(path_of(a, 'target')).splitlines()
    glossary = dict(x.split('=', 1) for x in str(a.get('glossary') or '').splitlines() if '=' in x)
    warnings = []
    if len(src) != len(dst):
        warnings.append(f'行数不同：原文 {len(src)} 行，译文 {len(dst)} 行')
    for i, (s, d) in enumerate(zip(src, dst), 1):
        if s.strip() and not d.strip():
            warnings.append(f'第 {i} 行没有翻译')
            continue
        for mark in re.findall(r'\{[^}]*\}|%[sd]|<[^>]+>', s):
            if mark not in d:
                warnings.append(f'第 {i} 行丢了 {mark}')
        for n in re.findall(r'\d+(?:\.\d+)?', s):
            if n not in d:
                warnings.append(f'第 {i} 行的数字 {n} 不见了')
        for term, want in glossary.items():
            if term.strip() in s and want.strip() not in d:
                warnings.append(f'第 {i} 行的“{term.strip()}”应该译成“{want.strip()}”')
    return done(f'比对了 {min(len(src), len(dst))} 行，发现 {len(warnings)} 处', warnings=warnings[:60])


# --- a voice ----------------------------------------------------------------------------------------------------------

def _voices() -> list:
    if sys.platform == 'darwin':  # macOS: `say -v ?` lists "Name   lang  # sample"
        res = subprocess.run(['say', '-v', '?'], capture_output=True)
        return [x.split('  ')[0].strip() for x in res.stdout.decode('utf-8', 'replace').splitlines() if x.strip()]
    script = "Add-Type -AssemblyName System.Speech;(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices()|%{$_.VoiceInfo.Name}"
    res = subprocess.run(['powershell', '-NoProfile', '-Command', script], capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0)
    return [x.strip() for x in res.stdout.decode('gbk', 'replace').splitlines() if x.strip()]


def voice_list(a, out):
    names = _voices()
    return done(f'这台电脑有 {len(names)} 个语音', *names)


def voice_say(a, out):
    """Windows' own voices: offline, free, and nothing to download."""
    text = str(need(a, 'text', '文字'))
    path = out / 'voice.wav'
    source = out / 'voice.txt'
    source.write_text(text, encoding='utf-8-sig')
    pick = str(a.get('voice') or '')
    rate = int(number(a, 'rate', 0))
    if sys.platform == 'darwin':  # macOS: the system's `say`, written straight to a wav
        cmd = ['say', *(['-v', pick] if pick else []), '-r', str(175 + rate * 15), '--file-format=WAVE', '--data-format=LEI16@22050', '-o', str(path), '-f', str(source)]
        res = subprocess.run(cmd, capture_output=True, timeout=300)
        if res.returncode or not path.is_file() or path.stat().st_size < 1000:
            raise Stop('没有读成：' + res.stderr.decode('utf-8', 'replace')[-300:])
        return done(f'读好了，{path.stat().st_size // 1024} KB', files=[path])
    # the paths and the voice go in through the environment: a quote or a $ in a folder name must not become part of the script
    script = ("Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;if($env:LUMEN_VOICE){$s.SelectVoice($env:LUMEN_VOICE)};"
              f"$s.Rate={rate};$s.SetOutputToWaveFile($env:LUMEN_OUT);$s.Speak([IO.File]::ReadAllText($env:LUMEN_IN));$s.Dispose()")
    res = subprocess.run(['powershell', '-NoProfile', '-Command', script], capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0, timeout=300,
                         env={**os.environ, 'LUMEN_VOICE': pick, 'LUMEN_OUT': str(path), 'LUMEN_IN': str(source)})
    if res.returncode or not path.is_file() or path.stat().st_size < 1000:
        raise Stop('没有读成：' + res.stderr.decode('gbk', 'replace')[-300:])
    return done(f'读好了，{path.stat().st_size // 1024} KB', files=[path])


# --- learning ---------------------------------------------------------------------------------------------------------

def quiz(a, out):
    """A page that asks and scores by itself. A line: 问题|对的答案|错的答案|错的答案"""
    rows = [[p.strip() for p in line.split('|')] for line in str(need(a, 'text', '题目')).splitlines() if '|' in line]
    if not rows:
        raise Stop('一行一题：问题|正确答案|错误答案|错误答案')
    data = json.dumps([{'q': r[0], 'a': r[1:]} for r in rows], ensure_ascii=False)
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(str(a.get('title') or '小测验'))}</title>
<style>body{{font:18px/1.6 system-ui,'Microsoft YaHei',sans-serif;max-width:640px;margin:40px auto;padding:0 18px;color:#1f1f1f}}button{{display:block;width:100%;text-align:left;padding:12px 16px;margin:8px 0;border:1px solid #ddd;border-radius:12px;background:#fff;font:inherit;cursor:pointer}}button:hover{{background:#f6f6f6}}.right{{background:#e2f3ea;border-color:#2f8f5b}}.wrong{{background:#f9e3e1;border-color:#c8463d}}small{{color:#777}}</style>
<h1>{escape(str(a.get('title') or '小测验'))}</h1><div id="box"></div><script>
const Q={data};let n=0,score=0;const box=document.getElementById('box');
function show(){{if(n>=Q.length){{box.innerHTML='<h2>得分 '+score+' / '+Q.length+'</h2><button onclick="n=0;score=0;show()">再来一次</button>';return}}
const q=Q[n],ans=q.a.map((t,i)=>[Math.random(),t,i]).sort((x,y)=>x[0]-y[0]);box.innerHTML='<small>第 '+(n+1)+' / '+Q.length+' 题</small><p>'+q.q+'</p>';
ans.forEach(([,t,i])=>{{const b=document.createElement('button');b.textContent=t;b.onclick=()=>{{if(i==0)score++;b.className=i==0?'right':'wrong';[...box.querySelectorAll('button')].forEach(x=>x.disabled=true);setTimeout(()=>{{n++;show()}},700)}};box.append(b)}})}}show()</script></html>'''
    path = out / 'quiz.html'
    path.write_text(page, encoding='utf-8')
    return done(f'{len(rows)} 道题，双击网页就能做', files=[path])


def cards(a, out):
    """Flash cards that come back when they are due (the SM-2 rule). Kept in a file next to the cards."""
    path = Path(str(a.get('deck') or (out / 'deck.json')))
    deck = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
    known = {c['q'] for c in deck}
    for line in str(a.get('add') or '').splitlines():
        if '|' in line:
            q, ans = line.split('|', 1)
            if q.strip() not in known:
                deck.append({'q': q.strip(), 'a': ans.strip(), 'ease': 2.5, 'days': 0, 'due': 0})
    import time

    today = int(time.time() // 86400)
    if a.get('answer') and a.get('question'):
        grade = int(number(a, 'grade', 4))
        for c in deck:
            if c['q'] == a['question']:
                c['ease'] = max(1.3, c['ease'] + .1 - (5 - grade) * (.08 + (5 - grade) * .02))
                c['days'] = 1 if grade < 3 or not c['days'] else 6 if c['days'] == 1 else round(c['days'] * c['ease'])
                c['due'] = today + c['days']
    path.write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding='utf-8')
    due = [c for c in deck if c['due'] <= today]
    return done(f'共 {len(deck)} 张，今天要复习 {len(due)} 张', table=[['问题', '答案', '再过几天']] + [[c['q'], c['a'], c['days']] for c in deck[:30]], files=[path])


# --- sources -----------------------------------------------------------------------------------------------------------

def cite_check(a, out):
    """Every quoted sentence in a report must really be in one of the saved sources."""
    report = _read(path_of(a, 'report'))
    folder = path_of(a, 'sources')
    sources = {p.name: re.sub(r'\s+', '', _read(p)) for p in folder.rglob('*') if p.suffix.lower() in ('.txt', '.md', '.html', '.htm')}
    quotes = re.findall(r'[“"「]([^”"」]{6,})[”"」]', report)
    rows, warnings = [['引文', '出处']], []
    for q in quotes:
        flat = re.sub(r'\s+', '', q)
        hit = next((n for n, t in sources.items() if flat in t), None)
        rows.append([q[:40], hit or '找不到'])
        if hit is None:
            warnings.append(f'这句在资料里找不到：{q[:40]}')
    return done(f'{len(sources)} 份资料，{len(quotes)} 处引文，{len(quotes) - len(warnings)} 处对得上', table=rows, warnings=warnings)


def _sample_book(o):
    p = o / 'book.txt'
    p.write_text('第一章 出发\n张三走了。他说：天气真好啊今天。\n第二章 路上\n李四来了。天气真好啊今天。\n第三章 到达\n张三和李四。天气真好啊今天。天气真好啊今天。\n', encoding='utf-8')
    return {'file': str(p)}


def _sample_srt(o):
    p = o / 'a.srt'
    p.write_text('1\n00:00:01,000 --> 00:00:02,000\n你好\n\n2\n00:00:01,500 --> 00:00:03,000\n这一条和上一条重叠了\n', encoding='utf-8')
    return {'file': str(p), 'seconds': 2}


def _sample_trans(o):
    s, t = o / 's.txt', o / 't.txt'
    s.write_text('Press {key} to open 3 files\nHello Lumen\n', encoding='utf-8')
    t.write_text('按键打开文件\n\n', encoding='utf-8')
    return {'source': str(s), 'target': str(t), 'glossary': 'Lumen=光'}


def _sample_cite(o):
    (o / 'src').mkdir()
    (o / 'src' / 'a.txt').write_text('今年的销售额比去年高了百分之十二。', encoding='utf-8')
    r = o / 'r.md'
    r.write_text('报告说“今年的销售额比去年高了百分之十二”，又说“这句话根本没有来源”。', encoding='utf-8')
    return {'report': str(r), 'sources': str(o / 'src')}


PLUGINS = [
    Plugin('book', '写书助手', '写作', '查长篇的人物、字数、重复，做成电子书', [
        Action('check', '检查全书', [Field('file', '书稿（txt 或 md）', 'file'), Field('names', '人物（用逗号分开）', value='')], book_check, sample={'_setup': _sample_book, 'names': '张三,李四,王五'}),
        Action('epub', '做成 EPUB', [Field('file', '书稿', 'file'), Field('title', '书名'), Field('author', '作者')], book_epub, sample={'_setup': _sample_book, 'title': '样书'})]),
    Plugin('subtitle', '字幕工具', '写作', '整体平移、查错、从台词生成字幕', [
        Action('shift', '平移和调速', [Field('file', '字幕文件', 'file'), Field('seconds', '移动秒数', 'number', 0), Field('speed', '速度倍数', 'number', 1)], sub_shift, sample={'_setup': _sample_srt}),
        Action('check', '查错', [Field('file', '字幕文件', 'file')], sub_check, sample={'_setup': _sample_srt}),
        Action('make', '台词生成字幕', [Field('text', '台词，一句一行', 'area', '大家好\n今天讲一件事'), Field('pace', '每秒几个字', 'number', 4.5)], sub_make, sample={'text': '大家好\n今天讲一件事'})]),
    Plugin('translate', '译文检查', '写作', '查漏译、术语不一致、数字和占位符丢失', [
        Action('check', '比对', [Field('source', '原文文件', 'file'), Field('target', '译文文件', 'file'), Field('glossary', '术语表，一行一个：原文=译文', 'area')], trans_check, sample={'_setup': _sample_trans})]),
    Plugin('voice', '配音', '写作', '用 Windows 自带的语音把文字读成 WAV，离线免费', [
        Action('say', '生成配音', [Field('text', '文字', 'area', '大家好，这是一段配音。'), Field('voice', '语音名字（可空）'), Field('rate', '语速 -10 到 10', 'number', 0)], voice_say, sample={'text': '你好'}),
        Action('list', '有哪些语音', [], voice_list)]),
    Plugin('learn', '学习卡片', '写作', '做能自动打分的小测验，和会按时提醒的记忆卡片', [
        Action('quiz', '做测验网页', [Field('title', '标题', value='小测验'), Field('text', '题目：问题|正确|错误|错误', 'area', '1+1=?|2|3|4')], quiz, sample={'text': '1+1=?|2|3|4\n首都？|北京|上海|广州'}),
        Action('cards', '记忆卡片', [Field('deck', '卡组文件（可空）'), Field('add', '加卡片：问题|答案', 'area'), Field('question', '刚复习的问题'), Field('answer', '答过了', 'check', False), Field('grade', '记得多清楚 0-5', 'number', 4)], cards, sample={'add': 'apple|苹果\nbook|书'})]),
    Plugin('cite', '引文核对', '写作', '报告里引用的每句话，到保存的资料里逐句核对', [
        Action('check', '核对', [Field('report', '报告文件', 'file'), Field('sources', '资料文件夹', 'folder')], cite_check, sample={'_setup': _sample_cite})]),
]
