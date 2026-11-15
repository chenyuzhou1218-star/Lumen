"""CodePDF: the common things people do with PDFs. Photos to PDF, merge, split, compress, change the page size, rotate, keep or delete pages.

    codepdf.py schema                          what each tool asks for (for AI)
    codepdf.py run <tool> --args '{...}' [--out folder]
    codepdf.py                                 the window

Tools: images, merge, split, compress, size, rotate, pick. Every command prints one JSON object as its last line.
Nothing here changes or deletes the original: results are new files in a CodePDF folder next to it (or --out).
"""
from __future__ import annotations

import right_python

right_python.use('PIL')

import argparse  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import sys  # noqa: E402

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'libs'))  # pypdf, installed here (python -m pip install --target libs pypdf)

from words import t  # noqa: E402

PAGE_SIZES = {'A4': (595.276, 841.89), 'A3': (841.89, 1190.55), 'A5': (419.53, 595.276), 'Letter': (612.0, 792.0)}
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff')
TOOLS = ('images', 'merge', 'split', 'compress', 'size', 'rotate', 'pick')


class Stop(Exception):
    """Something the person can fix, in words."""


def human(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def has_pypdf() -> bool:
    import importlib.util
    return importlib.util.find_spec('pypdf') is not None


def pypdf():
    try:
        import pypdf as lib
    except ImportError as e:
        raise Stop(t('err.lib')) from e
    return lib


def need_file(p, kind: str = 'pdf') -> Path:
    if not p:
        raise Stop(t('err.nofile'))
    path = Path(str(p)).expanduser()
    if not path.is_file():
        raise Stop(t('err.missing', path))
    return path


def reader(path: Path):
    lib = pypdf()
    try:
        r = lib.PdfReader(str(path))
        if r.is_encrypted and not r.decrypt(''):
            raise Stop(t('err.open', path.name))
        len(r.pages)
    except Stop:
        raise
    except Exception as e:  # noqa: BLE001 (a broken file can fail in many ways; the person needs one sentence)
        raise Stop(t('err.open', path.name)) from e
    return r


def pages_of(text: str, count: int) -> list[int]:
    """'1-3,5,8-' -> zero-based page numbers in the order written; empty means every page."""
    text = (text or '').replace('，', ',').replace('－', '-').replace('—', '-').replace(' ', '')
    if not text:
        return list(range(count))
    out: list[int] = []
    for part in text.split(','):
        if not part:
            continue
        try:
            if '-' in part:
                a, b = part.split('-', 1)
                lo, hi = int(a or 1), int(b or count)
            else:
                lo = hi = int(part)
        except ValueError as e:
            raise Stop(t('err.pages', text, count)) from e
        if lo < 1 or hi > count or lo > hi:
            raise Stop(t('err.pages', text, count))
        out.extend(range(lo - 1, hi))
    if not out:
        raise Stop(t('err.pages', text, count))
    return out


def out_folder(a: dict, source: Path | None) -> Path:
    if a.get('out'):
        folder = Path(str(a['out'])).expanduser()
    else:
        folder = (source.parent if source else Path.home() / 'Documents') / 'CodePDF'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def fresh(folder: Path, stem: str, suffix: str = '.pdf') -> Path:
    path = folder / f'{stem}{suffix}'
    n = 2
    while path.exists():
        path = folder / f'{stem}-{n}{suffix}'
        n += 1
    return path


def listed(a: dict, key: str) -> list:
    value = a.get(key) or []
    if isinstance(value, str):
        value = [v for v in value.replace('\r', '').split('\n') if v.strip()]
    return list(value)


def done(*lines, files=(), **more) -> dict:
    return {'ok': True, 'lines': [str(x) for x in lines], 'files': [str(f) for f in files], **more}


# --- the tools -------------------------------------------------------------------------------------------------------

def do_images(a: dict) -> dict:
    from PIL import Image, ImageOps

    paths = [need_file(p) for p in listed(a, 'files')]
    if not paths:
        raise Stop(t('err.noimg'))
    size = a.get('size') or 'A4'
    margin = {'0': 0, '1': 0.04, '2': 0.08}.get(str(a.get('margin', '1')), 0.04)
    dpi = 150
    pages = []
    for p in paths:
        try:
            im = ImageOps.exif_transpose(Image.open(p))
            if im.mode in ('RGBA', 'LA', 'P'):
                im = im.convert('RGBA')
                flat = Image.new('RGB', im.size, 'white')
                flat.paste(im, mask=im.split()[-1])
                im = flat
            else:
                im = im.convert('RGB')
        except Exception as e:  # noqa: BLE001
            raise Stop(t('err.img', p.name)) from e
        if size in PAGE_SIZES:
            w, h = PAGE_SIZES[size]
            if im.width > im.height:
                w, h = h, w
            pw, ph = round(w / 72 * dpi), round(h / 72 * dpi)
            room_w, room_h = pw * (1 - 2 * margin), ph * (1 - 2 * margin)
            scale = min(room_w / im.width, room_h / im.height)
            shown = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
            page = Image.new('RGB', (pw, ph), 'white')
            page.paste(shown, ((pw - shown.width) // 2, (ph - shown.height) // 2))
            pages.append(page)
        else:
            pages.append(im)
    folder = out_folder(a, paths[0])
    target = fresh(folder, paths[0].stem if len(paths) == 1 else 'photos')
    pages[0].save(target, 'PDF', save_all=True, append_images=pages[1:], resolution=dpi)
    return done(t('done.img', n=len(pages)), files=[target])


def do_merge(a: dict) -> dict:
    lib = pypdf()
    paths = [need_file(p) for p in listed(a, 'files')]
    if len(paths) < 2:
        raise Stop(t('err.two'))
    writer = lib.PdfWriter()
    total = 0
    for p in paths:
        r = reader(p)
        total += len(r.pages)
        writer.append(r)
    target = fresh(out_folder(a, paths[0]), 'merged')
    with open(target, 'wb') as f:
        writer.write(f)
    return done(t('done.merge', n=len(paths), pages=total), files=[target])


def do_split(a: dict) -> dict:
    lib = pypdf()
    source = need_file(a.get('file'))
    r = reader(source)
    count = len(r.pages)
    mode = a.get('mode') or 'each'
    groups: list[list[int]] = []
    if mode == 'ranges':
        for part in str(a.get('ranges') or '').replace('，', ',').split(','):
            if part.strip():
                groups.append(pages_of(part, count))
        if not groups:
            raise Stop(t('err.pages', a.get('ranges') or '', count))
    elif mode == 'every':
        try:
            n = int(a.get('n') or 1)
        except (TypeError, ValueError) as e:
            raise Stop(t('err.n')) from e
        if n < 1:
            raise Stop(t('err.n'))
        groups = [list(range(i, min(i + n, count))) for i in range(0, count, n)]
    else:
        groups = [[i] for i in range(count)]
    folder = out_folder(a, source) / source.stem
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    width = len(str(len(groups)))
    for k, group in enumerate(groups, 1):
        writer = lib.PdfWriter()
        for i in group:
            writer.add_page(r.pages[i])
        target = fresh(folder, f'{source.stem}-{k:0{width}d}')
        with open(target, 'wb') as f:
            writer.write(f)
        files.append(target)
    return done(t('done.split', n=len(files)), files=files[:40])


def do_compress(a: dict) -> dict:
    lib = pypdf()
    source = need_file(a.get('file'))
    quality, scale = {'light': (85, 1.0), 'strong': (40, 0.6)}.get(str(a.get('level') or 'mid'), (65, 0.85))
    r = reader(source)
    writer = lib.PdfWriter(clone_from=r)
    for page in writer.pages:
        try:
            page.compress_content_streams()
        except Exception:  # noqa: BLE001 (a page whose text cannot be repacked still goes through)
            pass
        try:
            for img in page.images:
                pil = img.image
                if pil is None:
                    continue
                if scale < 1.0 and max(pil.size) > 900:
                    from PIL import Image
                    pil = pil.resize((max(1, int(pil.width * scale)), max(1, int(pil.height * scale))), Image.LANCZOS)
                if pil.mode not in ('RGB', 'L'):
                    pil = pil.convert('RGB')
                img.replace(pil, quality=quality)
        except Exception:  # noqa: BLE001 (an odd picture stays as it was)
            continue
    try:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    except Exception:  # noqa: BLE001 (older pypdf: skip)
        pass
    target = fresh(out_folder(a, source), f'{source.stem}-small')
    with open(target, 'wb') as f:
        writer.write(f)
    before, after = source.stat().st_size, target.stat().st_size
    if after >= before:
        target.write_bytes(source.read_bytes())  # never hand back something bigger than what came in
        after = before
    pct = round(100 * (before - after) / before) if before else 0
    line = t('done.compress', before=human(before), after=human(after), pct=pct) if after < before else t('done.compress.same', before=human(before), after=human(after))
    return done(line, files=[target])


def do_size(a: dict) -> dict:
    lib = pypdf()
    from pypdf import PageObject, Transformation

    source = need_file(a.get('file'))
    name = a.get('to') if a.get('to') in PAGE_SIZES else 'A4'
    r = reader(source)
    scratch = lib.PdfWriter(clone_from=r)  # pages that belong to a writer: a page read from a file cannot be changed in place any more
    writer = lib.PdfWriter()
    for page in scratch.pages:
        page.transfer_rotation_to_content()
        pw, ph = float(page.mediabox.width), float(page.mediabox.height)
        w, h = PAGE_SIZES[name]
        if pw > ph:
            w, h = h, w
        scale = min(w / pw, h / ph)
        blank = PageObject.create_blank_page(scratch, w, h)
        move = Transformation().scale(scale, scale).translate((w - pw * scale) / 2 - float(page.mediabox.left) * scale,
                                                              (h - ph * scale) / 2 - float(page.mediabox.bottom) * scale)
        blank.merge_transformed_page(page, move)
        writer.add_page(blank)
    target = fresh(out_folder(a, source), f'{source.stem}-{name}')
    with open(target, 'wb') as f:
        writer.write(f)
    return done(t('done.size', pages=len(r.pages), to=name), files=[target])


def do_rotate(a: dict) -> dict:
    lib = pypdf()
    source = need_file(a.get('file'))
    r = reader(source)
    chosen = set(pages_of(str(a.get('pages') or ''), len(r.pages)))
    angle = {'180': 180, '270': 270}.get(str(a.get('by') or '90'), 90)
    writer = lib.PdfWriter()
    for i, page in enumerate(r.pages):
        if i in chosen:
            page.rotate(angle)
        writer.add_page(page)
    target = fresh(out_folder(a, source), f'{source.stem}-rotated')
    with open(target, 'wb') as f:
        writer.write(f)
    return done(t('done.rotate', n=len(chosen)), files=[target])


def do_pick(a: dict) -> dict:
    lib = pypdf()
    source = need_file(a.get('file'))
    r = reader(source)
    count = len(r.pages)
    chosen = pages_of(str(a.get('pages') or ''), count)
    if a.get('do') == 'drop':
        gone = set(chosen)
        chosen = [i for i in range(count) if i not in gone]
    if not chosen:
        raise Stop(t('err.empty'))
    writer = lib.PdfWriter()
    for i in chosen:
        writer.add_page(r.pages[i])
    target = fresh(out_folder(a, source), f'{source.stem}-pages')
    with open(target, 'wb') as f:
        writer.write(f)
    return done(t('done.pick', n=len(chosen)), files=[target])


RUN = {'images': do_images, 'merge': do_merge, 'split': do_split, 'compress': do_compress, 'size': do_size, 'rotate': do_rotate, 'pick': do_pick}

SCHEMA = {
    'images': {'files': 'list of photo paths, in page order', 'size': 'A4|A3|A5|Letter|fit', 'margin': '0|1|2'},
    'merge': {'files': 'list of PDF paths, in order'},
    'split': {'file': 'PDF path', 'mode': 'each|every|ranges', 'n': 'pages per file (every)', 'ranges': 'e.g. 1-3,4-6 (ranges)'},
    'compress': {'file': 'PDF path', 'level': 'light|mid|strong'},
    'size': {'file': 'PDF path', 'to': 'A4|A3|A5|Letter'},
    'rotate': {'file': 'PDF path', 'by': '90|180|270', 'pages': 'e.g. 1-3,5 (empty = all)'},
    'pick': {'file': 'PDF path', 'do': 'keep|drop', 'pages': 'e.g. 1-3,5'},
}


def run(tool: str, args: dict) -> dict:
    if tool not in RUN:
        raise Stop(t('err.unknown', tool))
    return RUN[tool](args)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        import editor
        return editor.main()
    p = argparse.ArgumentParser(prog='codepdf')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('schema')
    q = sub.add_parser('run')
    q.add_argument('tool')
    q.add_argument('--args', default='{}')
    q.add_argument('--args-file')
    q.add_argument('--out')
    args = p.parse_args(argv)
    try:
        if args.cmd == 'schema':
            answer = {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8'), 'tools': SCHEMA}
        else:
            raw = Path(args.args_file).read_text(encoding='utf-8-sig') if args.args_file else args.args
            try:
                values = json.loads(raw or '{}')
            except ValueError as e:
                raise Stop(f'--args: {e}') from e
            if args.out:
                values['out'] = args.out
            answer = run(args.tool, values)
    except Stop as e:
        answer = {'ok': False, 'error': str(e)}
    except Exception as e:  # noqa: BLE001 (whatever else goes wrong still answers in JSON, so the window can say it)
        answer = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    print(json.dumps(answer, ensure_ascii=False, default=str), flush=True)
    return 0 if answer.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
