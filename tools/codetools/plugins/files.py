"""The person's own files: pictures, PDFs, tidying, disk space, backups, comparing, searching. Nothing here deletes: files are moved or copied, and only after a plan was shown."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import zipfile

from PIL import Image, ImageDraw

from kit import Action, Field, Plugin, Stop, done, font, human, need, number, path_of

KINDS = {'图片': ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.heic'), '视频': ('.mp4', '.mov', '.mkv', '.avi', '.webm'), '音频': ('.mp3', '.wav', '.flac', '.m4a', '.ogg'),
         '文档': ('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.txt', '.md', '.csv'), '压缩包': ('.zip', '.rar', '.7z', '.gz', '.tar'), '程序': ('.exe', '.msi')}
SKIP = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}


def walk(folder: Path):
    for base, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for n in names:
            yield Path(base) / n


# --- pictures --------------------------------------------------------------------------------------------------------

def images_of(folder: Path) -> list:
    return [p for p in sorted(folder.iterdir()) if p.suffix.lower() in KINDS['图片'] and p.is_file()]


def image_batch(a, out):
    folder = path_of(a, 'folder')
    width = int(number(a, 'width', 1600))
    fmt = str(a.get('format') or 'jpg')
    quality = int(number(a, 'quality', 85))
    mark = str(a.get('watermark') or '')
    made, before, after = [], 0, 0
    for p in images_of(folder):
        im = Image.open(p)
        if im.mode in ('RGBA', 'P') and fmt == 'jpg':
            bg = Image.new('RGB', im.size, 'white')
            bg.paste(im.convert('RGBA'), mask=im.convert('RGBA').split()[-1])
            im = bg
        if im.width > width:
            im = im.resize((width, im.height * width // im.width), Image.LANCZOS)
        if mark:
            im = im.convert('RGB')
            d = ImageDraw.Draw(im, 'RGBA')
            f = font(max(16, im.width // 36))
            w = d.textlength(mark, font=f)
            d.text((im.width - w - 18, im.height - f.size - 22), mark, font=f, fill=(255, 255, 255, 170), stroke_width=2, stroke_fill=(0, 0, 0, 100))
        target = out / f'{p.stem}.{fmt}'
        im.save(target, quality=quality) if fmt != 'png' else im.save(target, optimize=True)
        made.append(target)
        before += p.stat().st_size
        after += target.stat().st_size
    if not made:
        raise Stop('这个文件夹里没有图片')
    return done(f'{len(made)} 张，从 {human(before)} 变成 {human(after)}', f'原图没有动，新图在 {out}', files=made[:40], pictures=made[:1])


def image_sheet(a, out):
    """All the pictures of a folder on one page."""
    items = images_of(path_of(a, 'folder'))
    if not items:
        raise Stop('这个文件夹里没有图片')
    cols = 5
    cell = 240
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell, rows * (cell + 26)), 'white')
    d = ImageDraw.Draw(sheet)
    f = font(14)
    for i, p in enumerate(items[:200]):
        im = Image.open(p).convert('RGB')
        im.thumbnail((cell - 12, cell - 12))
        x, y = (i % cols) * cell, (i // cols) * (cell + 26)
        sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
        d.text((x + 8, y + cell + 2), p.name[:28], font=f, fill='#444')
    path = out / 'sheet.jpg'
    sheet.save(path, quality=88)
    return done(f'{len(items)} 张图', files=[path], pictures=[path])


# --- PDF -------------------------------------------------------------------------------------------------------------

def _pdf(path: Path):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtPdf import QPdfDocument

    if QCoreApplication.instance() is None:
        QCoreApplication._kept = QCoreApplication([])
    doc = QPdfDocument()
    doc.load(str(path))
    if doc.pageCount() < 1:
        raise Stop('打不开这个 PDF（可能有密码）')
    return doc


def pdf_text(a, out):
    source = path_of(a, 'file')
    doc = _pdf(source)
    parts = []
    for i in range(doc.pageCount()):
        parts.append(f'--- 第 {i + 1} 页 ---\n{doc.getAllText(i).text()}')
    path = out / f'{source.stem}.txt'
    path.write_text('\n\n'.join(parts), encoding='utf-8')
    chars = sum(len(p) for p in parts)
    warnings = ['几乎没有文字：这可能是扫描件'] if chars < doc.pageCount() * 40 else []
    return done(f'{doc.pageCount()} 页，{chars} 字', files=[path], warnings=warnings)


def pdf_images(a, out):
    from PySide6.QtCore import QSize

    source = path_of(a, 'file')
    doc = _pdf(source)
    width = int(number(a, 'width', 1400))
    files = []
    for i in range(min(doc.pageCount(), 300)):
        size = doc.pagePointSize(i)
        image = doc.render(i, QSize(width, int(width * size.height() / size.width())))
        p = out / f'page_{i + 1:03d}.png'
        image.save(str(p))
        files.append(p)
    return done(f'{len(files)} 页图片', files=files[:40], pictures=files[:1])


def pdf_join(a, out):
    """Pictures of a folder as one PDF, in name order."""
    items = images_of(path_of(a, 'folder'))
    if not items:
        raise Stop('这个文件夹里没有图片')
    pages = [Image.open(p).convert('RGB') for p in items]
    path = out / 'joined.pdf'
    pages[0].save(path, save_all=True, append_images=pages[1:])
    return done(f'{len(pages)} 页', files=[path])


# --- tidying ----------------------------------------------------------------------------------------------------------

def tidy_plan(a, out):
    folder = path_of(a, 'folder')
    plan = []
    for p in sorted(folder.iterdir()):
        if p.is_file():
            kind = next((k for k, v in KINDS.items() if p.suffix.lower() in v), None)
            if kind:
                plan.append([p.name, kind])
    path = out / 'plan.json'
    path.write_text(json.dumps({'folder': str(folder), 'moves': plan}, ensure_ascii=False, indent=1), encoding='utf-8')
    counts = {}
    for _, k in plan:
        counts[k] = counts.get(k, 0) + 1
    return done(f'要移动 {len(plan)} 个文件：什么都还没动。确认后点“按计划整理”', table=[['分类', '个数']] + [[k, v] for k, v in counts.items()], files=[path])


def tidy_do(a, out):
    """Moves by the plan and writes how to undo it."""
    data = json.loads(path_of(a, 'plan').read_text(encoding='utf-8'))
    folder = Path(data['folder'])
    undo = []
    for name, kind in data['moves']:
        src = folder / name
        if src.is_file():
            (folder / kind).mkdir(exist_ok=True)
            dst = folder / kind / name
            if not dst.exists():
                shutil.move(str(src), str(dst))
                undo.append([str(dst), str(src)])
    log = out / f'undo_{datetime.now():%Y%m%d_%H%M%S}.json'
    log.write_text(json.dumps(undo, ensure_ascii=False, indent=1), encoding='utf-8')
    return done(f'移动了 {len(undo)} 个文件，反悔用“撤销整理”', files=[log])


def tidy_undo(a, out):
    pairs = json.loads(path_of(a, 'log').read_text(encoding='utf-8'))
    back = 0
    for dst, src in pairs:
        if Path(dst).is_file() and not Path(src).exists():
            shutil.move(dst, src)
            back += 1
    return done(f'放回了 {back} 个文件')


def _hash(p: Path) -> str:
    h = hashlib.blake2b(digest_size=16)
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def dupes(a, out):
    """Files that are exactly the same, however they are named. It only reports."""
    folder = path_of(a, 'folder')
    sizes = {}
    for p in walk(folder):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 0:
            sizes.setdefault(size, []).append(p)
    groups = {}
    for size, items in sizes.items():
        if len(items) > 1:
            for p in items:
                try:
                    groups.setdefault((size, _hash(p)), []).append(p)
                except OSError:
                    pass
    found = [(k[0], v) for k, v in groups.items() if len(v) > 1]
    found.sort(key=lambda x: -x[0] * (len(x[1]) - 1))
    waste = sum(size * (len(v) - 1) for size, v in found)
    rows = [['大小', '个数', '例子']] + [[human(s), len(v), str(v[0].relative_to(folder))[:60]] for s, v in found[:40]]
    report = out / 'duplicates.txt'
    report.write_text('\n\n'.join('\n'.join(str(p) for p in v) for _, v in found), encoding='utf-8')
    return done(f'{len(found)} 组重复，多占了 {human(waste)}。没有删除任何文件', table=rows, files=[report])


def disk(a, out):
    """Where the space went: a map of a folder, biggest first."""
    folder = path_of(a, 'folder')
    sizes, kinds, big = {}, {}, []
    for p in walk(folder):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        top = p.relative_to(folder).parts[0]
        sizes[top] = sizes.get(top, 0) + size
        kinds[p.suffix.lower() or '无'] = kinds.get(p.suffix.lower() or '无', 0) + size
        big.append((size, p))
    total = sum(sizes.values())
    if not total:
        raise Stop('这个文件夹是空的')
    big = sorted(big, key=lambda x: -x[0])[:12]
    w, h = 1100, 620
    im = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(im)
    colours = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
    items = sorted(sizes.items(), key=lambda x: -x[1])
    if len(items) > 8:
        items = items[:7] + [('其他', sum(v for _, v in items[7:]))]
    x, y, rw, rh = 0.0, 0.0, float(w), float(h)
    f = font(20, True)
    for i, (name, size) in enumerate(items):  # each takes a slice off the longer side: the squarest simple map
        share = size / max(1, sum(v for _, v in items[i:]))
        if rw >= rh:
            bw = rw * share
            box = (x, y, x + bw, y + rh)
            x += bw
            rw -= bw
        else:
            bh = rh * share
            box = (x, y, x + rw, y + bh)
            y += bh
            rh -= bh
        d.rectangle(box, fill=colours[i], outline='white', width=3)
        if box[2] - box[0] > 90 and box[3] - box[1] > 60:
            d.text((box[0] + 12, box[1] + 10), f'{name[:18]}\n{human(size)}', font=f, fill='white')
    path = out / 'disk.png'
    im.save(path)
    rows = [['最大的文件', '大小']] + [[str(p.relative_to(folder))[:70], human(s)] for s, p in big]
    return done(f'一共 {human(total)}', '、'.join(f'{k} {human(v)}' for k, v in sorted(kinds.items(), key=lambda x: -x[1])[:6]), table=rows, files=[path], pictures=[path])


# --- backup -----------------------------------------------------------------------------------------------------------

def backup(a, out):
    """Only what changed since the last time goes into a new zip; a list says what is where."""
    folder = path_of(a, 'folder')
    target = Path(str(a.get('to') or out))
    target.mkdir(parents=True, exist_ok=True)
    index_path = target / 'backup_index.json'
    index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.is_file() else {}
    stamp = f'{datetime.now():%Y%m%d_%H%M%S}'
    archive = target / f'{folder.name}_{stamp}.zip'
    changed = 0
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in walk(folder):
            rel = p.relative_to(folder).as_posix()
            try:
                digest = _hash(p)
            except OSError:
                continue
            if index.get(rel, {}).get('hash') != digest:
                z.write(p, rel)
                index[rel] = {'hash': digest, 'in': archive.name}
                changed += 1
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding='utf-8')
    if not changed:
        archive.unlink()
        return done('没有变化，不用备份')
    return done(f'{changed} 个文件进了新备份，一共记录 {len(index)} 个，{human(archive.stat().st_size)}', files=[archive, index_path])


def backup_verify(a, out):
    target = path_of(a, 'to')
    index = json.loads((target / 'backup_index.json').read_text(encoding='utf-8'))
    bad = []
    for rel, e in index.items():
        z = target / e['in']
        try:
            with zipfile.ZipFile(z) as f:
                h = hashlib.blake2b(f.read(rel), digest_size=16).hexdigest()
        except (OSError, KeyError, zipfile.BadZipFile):
            bad.append(rel)
            continue
        if h != e['hash']:
            bad.append(rel)
    return done(f'查了 {len(index)} 个文件，{len(bad)} 个有问题', warnings=[f'坏了：{b}' for b in bad[:30]])


def backup_restore(a, out):
    target = path_of(a, 'to')
    index = json.loads((target / 'backup_index.json').read_text(encoding='utf-8'))
    dest = Path(str(a.get('dest') or out / 'restored'))
    count = 0
    for rel, e in index.items():
        with zipfile.ZipFile(target / e['in']) as f:
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f.read(rel))
            count += 1
    return done(f'恢复了 {count} 个文件到 {dest}')


# --- comparing and finding ---------------------------------------------------------------------------------------------

def compare(a, out):
    left, right = path_of(a, 'left'), path_of(a, 'right')
    if left.is_file() and right.is_file():
        import difflib

        x = left.read_text(encoding='utf-8', errors='replace').splitlines()
        y = right.read_text(encoding='utf-8', errors='replace').splitlines()
        page = difflib.HtmlDiff(wrapcolumn=70).make_file(x, y, left.name, right.name, context=True, numlines=3)
        path = out / 'diff.html'
        path.write_text(page, encoding='utf-8')
        changed = sum(1 for line in difflib.unified_diff(x, y, lineterm='') if line[:1] in '+-' and line[:3] not in ('+++', '---'))
        return done(f'{changed} 行不同', files=[path])
    lf = {p.relative_to(left).as_posix(): p for p in walk(left)}
    rf = {p.relative_to(right).as_posix(): p for p in walk(right)}
    only_l, only_r = sorted(set(lf) - set(rf)), sorted(set(rf) - set(lf))
    diff = [k for k in sorted(set(lf) & set(rf)) if lf[k].stat().st_size != rf[k].stat().st_size or _hash(lf[k]) != _hash(rf[k])]
    rows = [['情况', '文件']] + [['只在左边', k] for k in only_l[:30]] + [['只在右边', k] for k in only_r[:30]] + [['内容不同', k] for k in diff[:30]]
    return done(f'只在左边 {len(only_l)}，只在右边 {len(only_r)}，内容不同 {len(diff)}', table=rows)


TEXT = ('.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.csv', '.c', '.cpp', '.h', '.java', '.go', '.rs', '.toml', '.yaml', '.yml', '.ini', '.log', '.srt')


def index_build(a, out):
    """A search index of a folder, kept beside the results: searching then takes no time at all."""
    folder = path_of(a, 'folder')
    db = out / 'search.db'
    con = sqlite3.connect(db)
    con.execute('DROP TABLE IF EXISTS docs')
    con.execute('CREATE VIRTUAL TABLE docs USING fts5(path, body, tokenize="trigram")')
    count = 0
    for p in walk(folder):
        if p.suffix.lower() in TEXT and p.stat().st_size < 2_000_000:
            try:
                con.execute('INSERT INTO docs VALUES (?, ?)', (str(p), p.read_text(encoding='utf-8', errors='replace')))
                count += 1
            except OSError:
                pass
    con.commit()
    con.close()
    return done(f'记下了 {count} 个文件', files=[db])


def index_find(a, out):
    db = Path(str(a.get('index') or out / 'search.db'))
    if not db.is_file():
        raise Stop('先“建立索引”')
    words = str(need(a, 'query', '要找什么')).replace('"', ' ')
    con = sqlite3.connect(db)
    if len(words) >= 3:
        rows = con.execute('SELECT path, snippet(docs, 1, "【", "】", " … ", 16) FROM docs WHERE docs MATCH ? LIMIT 40', (f'"{words}"',)).fetchall()
    else:  # a trigram index cannot look up one or two characters
        rows = [(p, b[max(0, b.find(words) - 20):b.find(words) + 40]) for p, b in con.execute('SELECT path, body FROM docs WHERE body LIKE ? LIMIT 40', (f'%{words}%',))]
    con.close()
    return done(f'找到 {len(rows)} 个文件', table=[['文件', '内容']] + [[r[0][-60:], ' '.join(r[1].split())[:90]] for r in rows])


def _images(o):
    d = o / 'pics'
    d.mkdir()
    for i, c in enumerate(('#2f6fed', '#e8702a', '#1baf7a')):
        Image.new('RGB', (2400, 1500), c).save(d / f'p{i}.png')
    return {'folder': str(d)}


def _pdf_sample(o):
    p = o / 'a.pdf'
    from PySide6.QtCore import QCoreApplication, QRectF
    from PySide6.QtGui import QFont, QPainter, QPageSize, QPdfWriter
    from PySide6.QtWidgets import QApplication

    if QCoreApplication.instance() is None:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        QApplication._kept = QApplication([])
    w = QPdfWriter(str(p))
    w.setPageSize(QPageSize(QPageSize.A4))
    painter = QPainter(w)
    painter.setFont(QFont('Arial', 12))
    painter.drawText(QRectF(200, 200, 8000, 1000), 'Hello from a PDF page')
    painter.end()
    return {'file': str(p)}


def _mess(o):
    d = o / 'mess'
    d.mkdir()
    for n in ('a.png', 'b.mp4', 'c.docx', 'd.zip', 'keep.xyz'):
        (d / n).write_bytes(b'x' * 50)
    (d / 'copy.png').write_bytes(b'x' * 50)
    return {'folder': str(d)}


def _tidy_do_sample(o):
    s = _mess(o)
    plan = tidy_plan(s, o)
    return {'plan': plan['files'][0]}


def _tidy_undo_sample(o):
    s = _tidy_do_sample(o)
    res = tidy_do(s, o)
    return {'log': res['files'][0]}


def _backup_sample(o):
    s = _mess(o)
    backup({**s, 'to': str(o / 'b')}, o)
    return {'to': str(o / 'b')}


def _two(o):
    l, r = o / 'l', o / 'r'
    l.mkdir()
    r.mkdir()
    (l / 'same.txt').write_text('x')
    (r / 'same.txt').write_text('x')
    (l / 'diff.txt').write_text('a')
    (r / 'diff.txt').write_text('bb')
    (l / 'only.txt').write_text('z')
    return {'left': str(l), 'right': str(r)}


def _search_sample(o):
    d = o / 'docs'
    d.mkdir()
    (d / 'a.md').write_text('今天天气很好，适合写代码', encoding='utf-8')
    index_build({'folder': str(d)}, o)
    return {'query': '适合写代码'}


PLUGINS = [
    Plugin('images', '批量修图', '文件', '一次缩小、转格式、加水印，或拼成一页。原图不动', [
        Action('batch', '批量处理', [Field('folder', '图片文件夹', 'folder'), Field('width', '最大宽度', 'number', 1600), Field('format', '格式', 'choice', 'jpg', ('jpg', 'png', 'webp')), Field('quality', '质量', 'number', 85), Field('watermark', '水印文字')], image_batch, sample={'_setup': _images, 'watermark': 'Lumen'}),
        Action('sheet', '拼成总览图', [Field('folder', '图片文件夹', 'folder')], image_sheet, sample={'_setup': _images})]),
    Plugin('pdf', 'PDF 工具', '文件', '提取文字，转成图片，图片合成 PDF', [
        Action('text', '提取文字', [Field('file', 'PDF 文件', 'file')], pdf_text, sample={'_setup': _pdf_sample}),
        Action('images', '每页转图片', [Field('file', 'PDF 文件', 'file'), Field('width', '宽度', 'number', 1400)], pdf_images, sample={'_setup': _pdf_sample}),
        Action('join', '图片合成 PDF', [Field('folder', '图片文件夹', 'folder')], pdf_join, sample={'_setup': _images})]),
    Plugin('tidy', '整理文件夹', '文件', '先看计划再动手，随时能撤销，绝不删除', [
        Action('plan', '看整理计划', [Field('folder', '文件夹', 'folder')], tidy_plan, sample={'_setup': _mess}),
        Action('do', '按计划整理', [Field('plan', '计划文件', 'file')], tidy_do, changes=True, sample={'_setup': _tidy_do_sample}),
        Action('undo', '撤销整理', [Field('log', '记录文件', 'file')], tidy_undo, changes=True, sample={'_setup': _tidy_undo_sample})]),
    Plugin('dupes', '找重复文件', '文件', '按内容找一模一样的文件，只报告不删除', [
        Action('find', '查找', [Field('folder', '文件夹', 'folder')], dupes, sample={'_setup': _mess})]),
    Plugin('disk', '磁盘分析', '文件', '画出一个文件夹的空间都被谁占了', [
        Action('map', '分析', [Field('folder', '文件夹', 'folder')], disk, sample={'_setup': _mess})]),
    Plugin('backup', '增量备份', '文件', '只备份变过的文件，能校验，能恢复', [
        Action('run', '备份', [Field('folder', '要备份的文件夹', 'folder'), Field('to', '存到哪里', 'folder')], backup, sample={'_setup': _mess}),
        Action('verify', '校验', [Field('to', '备份文件夹', 'folder')], backup_verify, sample={'_setup': _backup_sample}),
        Action('restore', '恢复', [Field('to', '备份文件夹', 'folder'), Field('dest', '恢复到哪里', 'folder')], backup_restore, sample={'_setup': _backup_sample})]),
    Plugin('compare', '比较差异', '文件', '比较两个文件或两个文件夹', [
        Action('run', '比较', [Field('left', '左边', 'folder'), Field('right', '右边', 'folder')], compare, sample={'_setup': _two})]),
    Plugin('finder', '全文搜索', '文件', '给文件夹建索引，一瞬间搜到文件里的字', [
        Action('build', '建立索引', [Field('folder', '文件夹', 'folder')], index_build, sample={'_setup': _mess}),
        Action('find', '搜索', [Field('query', '要找什么'), Field('index', '索引文件（可空）')], index_find, sample={'_setup': _search_sample})]),
]
