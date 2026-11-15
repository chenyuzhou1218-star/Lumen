"""Every word CodePDF shows, in the language Lumen is set to (preference `language` in ~/.codedoctor/ui.json; 中文 for zh, English otherwise).

    t('merge.title')            the text
    t('done.pages', n=3)        with values filled in
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ZH = {
    'app': 'CodePDF',
    'chip': '{0} 个功能',
    'results': '结果文件夹',
    'results.tip': '打开做出来的文件',
    'fill': '填写',
    'result': '结果',
    'run': '开始',
    'busy': '处理中…',
    'ok': '做好了',
    'bad': '没有做成',
    'empty': '还没有运行',
    'empty.hint': '选好文件，点“{0}”',
    'none': '不用填，直接开始',
    'items': '{0} 项',
    'files': '{0} 个文件',
    'pick': '选择',
    'add': '添加',
    'remove': '移除',
    'up': '上移',
    'down': '下移',
    'clear': '清空',
    'pick.pdf': '选一个 PDF',
    'pick.folder': '选一个文件夹',
    'out': '保存到',
    'out.same': '和原文件放在一起',
    'out.hint': '不选就放在原文件旁边的 CodePDF 文件夹里',
    'filter.pdf': 'PDF 文件 (*.pdf)',
    'filter.img': '图片 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)',
    'list.pdf': '要处理的 PDF（按这里的顺序）',
    'list.img': '要放进 PDF 的照片（按这里的顺序）',
    'pages': '页码',
    'pages.hint': '例如 1-3,5,8-（不填就是全部）',
    'img.title': '照片转 PDF',
    'img.blurb': '把一张或很多张照片按顺序放进一个 PDF',
    'img.size': '页面大小',
    'img.fit': '和照片一样大',
    'img.margin': '页边距',
    'img.m0': '没有',
    'img.m1': '小',
    'img.m2': '中',
    'merge.title': '合并',
    'merge.blurb': '把几个 PDF 按顺序接成一个',
    'split.title': '拆分',
    'split.blurb': '把一个 PDF 拆成几个',
    'split.mode': '怎么拆',
    'split.each': '每一页一个文件',
    'split.every': '每隔几页一个文件',
    'split.ranges': '按页码范围',
    'split.n': '每个文件几页',
    'split.ranges.hint': '每段用逗号分开，每段做成一个文件，例如 1-3,4-6,7-',
    'compress.title': '压缩',
    'compress.blurb': '让 PDF 变小，方便发送',
    'compress.level': '压缩程度',
    'compress.light': '轻（几乎看不出变化）',
    'compress.mid': '中（推荐）',
    'compress.strong': '强（图片会变糊）',
    'size.title': '页面大小',
    'size.blurb': '把每一页改成 A4、A3、A5 或信纸大小，内容按比例放进去',
    'size.to': '改成',
    'rotate.title': '旋转',
    'rotate.blurb': '把整本或指定的页转个方向',
    'rotate.by': '转多少',
    'rotate.r90': '向右 90°',
    'rotate.r180': '180°',
    'rotate.r270': '向左 90°',
    'pick.title': '提取或删除页',
    'pick.blurb': '只留下想要的页，或者去掉不要的页',
    'pick.keep': '只留下这些页',
    'pick.drop': '删掉这些页',
    'pick.do': '做什么',
    'done.pages': '{n} 页',
    'done.merge': '合并好了：{n} 个文件，共 {pages} 页',
    'done.split': '拆成了 {n} 个文件',
    'done.compress': '{before} → {after}（小了 {pct}%）',
    'done.compress.same': '{before} → {after}：这个 PDF 已经很小，几乎没有能再压的',
    'done.size': '{pages} 页都改成了 {to}',
    'done.rotate': '转好了：{n} 页',
    'done.pick': '留下 {n} 页',
    'done.img': '{n} 张照片，做成了 {n} 页',
    'err.nofile': '还没有选文件',
    'err.noimg': '还没有选照片',
    'err.two': '合并至少要两个 PDF',
    'err.missing': '找不到这个文件：{0}',
    'err.open': '打不开这个 PDF（可能有密码，或者文件坏了）：{0}',
    'err.pages': '页码看不懂：{0}。要像 1-3,5 这样写，最大是 {1}',
    'err.empty': '这样一页都不剩了',
    'err.lib': '需要安装 pypdf 才能做这一项。在 CodePDF 文件夹里运行：python -m pip install --target libs pypdf',
    'err.img': '打不开这张照片：{0}',
    'err.n': '每个文件的页数要是大于 0 的整数',
    'err.unknown': '没有这个功能：{0}',
}

EN = {
    'app': 'CodePDF',
    'chip': '{0} tools',
    'results': 'Results folder',
    'results.tip': 'Open the files that were made',
    'fill': 'Settings',
    'result': 'Result',
    'run': 'Start',
    'busy': 'Working…',
    'ok': 'Done',
    'bad': 'Did not work',
    'empty': 'Nothing yet',
    'empty.hint': 'Choose files, then click “{0}”',
    'none': 'Nothing to fill in, just start',
    'items': '{0} settings',
    'files': '{0} files',
    'pick': 'Choose',
    'add': 'Add',
    'remove': 'Remove',
    'up': 'Up',
    'down': 'Down',
    'clear': 'Clear',
    'pick.pdf': 'Choose a PDF',
    'pick.folder': 'Choose a folder',
    'out': 'Save to',
    'out.same': 'Next to the original file',
    'out.hint': 'Left empty, results go to a CodePDF folder next to the original',
    'filter.pdf': 'PDF files (*.pdf)',
    'filter.img': 'Pictures (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)',
    'list.pdf': 'PDFs to use (in this order)',
    'list.img': 'Photos to put in the PDF (in this order)',
    'pages': 'Pages',
    'pages.hint': 'For example 1-3,5,8- (empty means all)',
    'img.title': 'Photos to PDF',
    'img.blurb': 'Put one or many photos, in order, into one PDF',
    'img.size': 'Page size',
    'img.fit': 'Same size as the photo',
    'img.margin': 'Margin',
    'img.m0': 'None',
    'img.m1': 'Small',
    'img.m2': 'Medium',
    'merge.title': 'Merge',
    'merge.blurb': 'Join several PDFs, in order, into one',
    'split.title': 'Split',
    'split.blurb': 'Cut one PDF into several',
    'split.mode': 'How',
    'split.each': 'One file per page',
    'split.every': 'One file every few pages',
    'split.ranges': 'By page ranges',
    'split.n': 'Pages per file',
    'split.ranges.hint': 'Separate parts with commas; each part becomes a file, for example 1-3,4-6,7-',
    'compress.title': 'Compress',
    'compress.blurb': 'Make a PDF smaller so it is easy to send',
    'compress.level': 'Strength',
    'compress.light': 'Light (hardly any change)',
    'compress.mid': 'Medium (recommended)',
    'compress.strong': 'Strong (pictures get blurrier)',
    'size.title': 'Page size',
    'size.blurb': 'Change every page to A4, A3, A5 or Letter; content is scaled to fit',
    'size.to': 'Change to',
    'rotate.title': 'Rotate',
    'rotate.blurb': 'Turn the whole file or chosen pages',
    'rotate.by': 'Turn by',
    'rotate.r90': '90° right',
    'rotate.r180': '180°',
    'rotate.r270': '90° left',
    'pick.title': 'Keep or delete pages',
    'pick.blurb': 'Keep only the pages you want, or take out the ones you do not',
    'pick.keep': 'Keep only these pages',
    'pick.drop': 'Delete these pages',
    'pick.do': 'What to do',
    'done.pages': '{n} pages',
    'done.merge': 'Merged: {n} files, {pages} pages',
    'done.split': 'Split into {n} files',
    'done.compress': '{before} → {after} ({pct}% smaller)',
    'done.compress.same': '{before} → {after}: this PDF is already small, there is almost nothing left to squeeze',
    'done.size': 'All {pages} pages are now {to}',
    'done.rotate': 'Rotated {n} pages',
    'done.pick': 'Kept {n} pages',
    'done.img': '{n} photos, made into {n} pages',
    'err.nofile': 'No file chosen yet',
    'err.noimg': 'No photos chosen yet',
    'err.two': 'Merging needs at least two PDFs',
    'err.missing': 'Cannot find this file: {0}',
    'err.open': 'Cannot open this PDF (it may have a password, or be damaged): {0}',
    'err.pages': 'Cannot read the pages: {0}. Write them like 1-3,5; the last page is {1}',
    'err.empty': 'That would leave no pages',
    'err.lib': 'pypdf needs to be installed for this one. In the CodePDF folder run: python -m pip install --target libs pypdf',
    'err.img': 'Cannot open this photo: {0}',
    'err.n': 'Pages per file must be a whole number above 0',
    'err.unknown': 'No such tool: {0}',
}


LANGS = ('zh', 'en', 'fr', 'es', 'de', 'it', 'pt')  # Lumen's languages; another one shows English
HERE = Path(__file__).resolve().parent
_others: dict = {}


def language() -> str:
    given = os.environ.get('LUMEN_LANG')  # Lumen sets it for the tools it starts (desktop/i18n.set_language)
    if not given:
        home = Path(os.environ.get('CODEDOCTOR_HOME') or Path.home() / '.codedoctor')
        try:
            given = json.loads((home / 'ui.json').read_text(encoding='utf-8')).get('language')
        except (OSError, ValueError, AttributeError):
            given = None
    c = str(given or 'zh').lower()
    return 'zh' if c.startswith('zh') else c[:2] if c[:2] in LANGS else 'en'


def _table(lang: str) -> dict:
    """ZH, EN, or EN with <lang>.json over it ({"中文": "translation"}, next to this file: fr.json, es.json ...)."""
    if lang == 'zh':
        return ZH
    if lang == 'en':
        return EN
    if lang not in _others:
        try:
            words = json.loads((HERE / f'{lang}.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            words = {}
        _others[lang] = {k: words.get(ZH.get(k, ''), v) or v for k, v in EN.items()}
    return _others[lang]


def t(key: str, *pos, **named) -> str:
    table = _table(language())
    text = table.get(key) or ZH.get(key) or key
    try:
        return text.format(*pos, **named)
    except (IndexError, KeyError):
        return text
