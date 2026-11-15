"""PowerPoint and Word files, written as what they are: zip files of XML. Only Python's own library.

Everything stays editable: slides are real text boxes and tables, a document has real headings and lists. Charts go in as pictures.
"""
from __future__ import annotations

from pathlib import Path
import re
import zipfile
from xml.sax.saxutils import escape

EMU = 12700 * .75  # a CSS pixel on the 1280 x 720 page is 9525 EMU
XMLH = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
NS_P = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
FONT = 'Microsoft YaHei'


def e(v) -> int:
    return int(round(v * EMU))


def _hex(c: str) -> str:
    return c.lstrip('#').upper()


def _run(text: str, size: float, color: str, bold: bool) -> str:
    return (f'<a:r><a:rPr lang="zh-CN" sz="{int(size * 75)}" b="{1 if bold else 0}" dirty="0"><a:solidFill><a:srgbClr val="{_hex(color)}"/></a:solidFill>'
            f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>')


def _para(p: dict) -> str:
    props = [f'algn="{ {"center": "ctr", "right": "r"}.get(p.get("align"), "l") }"']
    inner = ''
    if p.get('bullet'):
        props += ['marL="342900"', 'indent="-342900"']
        inner = f'<a:buClr><a:srgbClr val="{_hex(p.get("color", "#000000"))}"/></a:buClr><a:buFont typeface="Arial"/><a:buChar char="•"/>'
    elif p.get('indent'):
        props += ['marL="342900"', 'indent="0"']
        inner = '<a:buNone/>'
    else:
        inner = '<a:buNone/>'
    space = f'<a:spcAft><a:spcPts val="{int(p.get("space", 0) * 75)}"/></a:spcAft>'
    size = p.get('size', 20)
    return f'<a:p><a:pPr {" ".join(props)}>{space}{inner}</a:pPr>{_run(p.get("text", ""), size, p.get("color", "#000000"), bool(p.get("bold")))}</a:p>'


def _xfrm(t: dict, tag: str = 'a') -> str:
    return f'<{tag}:xfrm><a:off x="{e(t["x"])}" y="{e(t["y"])}"/><a:ext cx="{e(t["w"])}" cy="{e(t["h"])}"/></{tag}:xfrm>'


def _shape_text(i: int, t: dict) -> str:
    anchor = {'middle': 'ctr', 'bottom': 'b'}.get(t.get('valign'), 't')
    paras = ''.join(_para(p) for p in t['paras']) or '<a:p/>'
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="文本 {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>{_xfrm(t)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="{anchor}"><a:normAutofit/></a:bodyPr><a:lstStyle/>{paras}</p:txBody></p:sp>')


def _shape_rect(i: int, t: dict) -> str:
    round_it = t.get('radius', 0) > 0
    adj = int(min(50000, t.get('radius', 0) / max(1, min(t['w'], t['h'])) * 100000))
    geom = f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val {adj}"/></a:avLst></a:prstGeom>' if round_it else '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="形状 {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>{_xfrm(t)}{geom}<a:solidFill><a:srgbClr val="{_hex(t["fill"])}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody></p:sp>')


def _shape_pic(i: int, t: dict, rel: str) -> str:
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="图片 {i}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rel}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr>{_xfrm(t)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')


def _shape_table(i: int, t: dict) -> str:
    rows = t['rows']
    if not rows:
        return ''
    th = t['theme']
    cols = max(len(r) for r in rows)
    cw = e(t['w']) // cols
    rh = min(e(t['h']) // len(rows), e(56))
    grid = ''.join(f'<a:gridCol w="{cw}"/>' for _ in range(cols))
    body = ''
    for ri, row in enumerate(rows):
        cells = ''
        for c in range(cols):
            value = str(row[c]) if c < len(row) else ''
            head = ri == 0
            fill = th['dark'] if head else (th['soft'] if ri % 2 == 0 else th['bg'])
            color = th['on_dark'] if head else th['ink']
            para = _para({'text': value, 'size': 24, 'color': color, 'bold': head})
            cells += f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{para}</a:txBody><a:tcPr anchor="ctr"><a:solidFill><a:srgbClr val="{_hex(fill)}"/></a:solidFill></a:tcPr></a:tc>'
        body += f'<a:tr h="{rh}">{cells}</a:tr>'
    return (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="表格 {i}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>{_xfrm(t, "p")}'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1"/><a:tblGrid>{grid}</a:tblGrid>{body}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>')


THEME_XML = XMLH + ('<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="CodeDeck"><a:themeElements><a:clrScheme name="CodeDeck"><a:dk1><a:srgbClr val="1C1F26"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
                    '<a:dk2><a:srgbClr val="16243F"/></a:dk2><a:lt2><a:srgbClr val="EEF2FA"/></a:lt2><a:accent1><a:srgbClr val="2A78D6"/></a:accent1><a:accent2><a:srgbClr val="EB6834"/></a:accent2><a:accent3><a:srgbClr val="1BAF7A"/></a:accent3>'
                    '<a:accent4><a:srgbClr val="EDA100"/></a:accent4><a:accent5><a:srgbClr val="E87BA4"/></a:accent5><a:accent6><a:srgbClr val="6250D6"/></a:accent6><a:hlink><a:srgbClr val="2A78D6"/></a:hlink><a:folHlink><a:srgbClr val="6250D6"/></a:folHlink></a:clrScheme>'
                    f'<a:fontScheme name="CodeDeck"><a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
                    '<a:fmtScheme name="CodeDeck"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
                    '<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
                    '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
                    '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>')
EMPTY_TREE = '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree>'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def _rels(items: list) -> str:
    return XMLH + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="{i}" Type="{t}" Target="{target}"/>' for i, t, target in items) + '</Relationships>'


def write_pptx(path: Path, slides: list, title: str) -> None:
    """slides: [(background, things)]. A 'chart' or 'image' thing has 'file': a picture on disk."""
    media: dict = {}
    types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}
    parts = {}
    overrides = []
    for number, (bg, things) in enumerate(slides, 1):
        shapes = ''
        rels = [('rId1', f'{REL}/slideLayout', '../slideLayouts/slideLayout1.xml')]
        for i, t in enumerate(things, 2):
            if t['kind'] == 'text':
                shapes += _shape_text(i, t)
            elif t['kind'] == 'rect':
                shapes += _shape_rect(i, t)
            elif t['kind'] == 'table':
                shapes += _shape_table(i, t)
            elif t.get('file'):
                src = Path(t['file'])
                name = media.setdefault(str(src), f'image{len(media) + 1}{src.suffix.lower()}')
                rid = f'rId{len(rels) + 1}'
                rels.append((rid, f'{REL}/image', f'../media/{name}'))
                shapes += _shape_pic(i, t, rid)
        tree = EMPTY_TREE.replace('</p:spTree>', shapes + '</p:spTree>')
        parts[f'ppt/slides/slide{number}.xml'] = (XMLH + f'<p:sld {NS_P}><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{_hex(bg)}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>{tree}</p:cSld>'
                                                  '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')
        parts[f'ppt/slides/_rels/slide{number}.xml.rels'] = _rels(rels)
        overrides.append((f'/ppt/slides/slide{number}.xml', 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'))
    ids = ''.join(f'<p:sldId id="{255 + n}" r:id="rId{n + 2}"/>' for n in range(1, len(slides) + 1))
    parts['ppt/presentation.xml'] = (XMLH + f'<p:presentation {NS_P} saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{ids}</p:sldIdLst>'
                                     f'<p:sldSz cx="{e(1280)}" cy="{e(720)}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
    parts['ppt/_rels/presentation.xml.rels'] = _rels([('rId1', f'{REL}/slideMaster', 'slideMasters/slideMaster1.xml'), ('rId2', f'{REL}/theme', 'theme/theme1.xml')]
                                                     + [(f'rId{n + 2}', f'{REL}/slide', f'slides/slide{n}.xml') for n in range(1, len(slides) + 1)])
    # rId2 is taken by the theme, so slides start at rId3: the list above and the ids match
    parts['ppt/slideMasters/slideMaster1.xml'] = (XMLH + f'<p:sldMaster {NS_P}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>{EMPTY_TREE}</p:cSld>'
                                                  '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
                                                  '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>')
    parts['ppt/slideMasters/_rels/slideMaster1.xml.rels'] = _rels([('rId1', f'{REL}/slideLayout', '../slideLayouts/slideLayout1.xml'), ('rId2', f'{REL}/theme', '../theme/theme1.xml')])
    parts['ppt/slideLayouts/slideLayout1.xml'] = (XMLH + f'<p:sldLayout {NS_P} type="blank" preserve="1"><p:cSld name="空白">{EMPTY_TREE}</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
    parts['ppt/slideLayouts/_rels/slideLayout1.xml.rels'] = _rels([('rId1', f'{REL}/slideMaster', '../slideMasters/slideMaster1.xml')])
    parts['ppt/theme/theme1.xml'] = THEME_XML
    parts['docProps/core.xml'] = (XMLH + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
                                  f'<dc:title>{escape(title)}</dc:title></cp:coreProperties>')
    parts['_rels/.rels'] = _rels([('rId1', f'{REL}/officeDocument', 'ppt/presentation.xml'), ('rId2', 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties', 'docProps/core.xml')])
    overrides += [('/ppt/presentation.xml', 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),
                  ('/ppt/slideMasters/slideMaster1.xml', 'application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml'),
                  ('/ppt/slideLayouts/slideLayout1.xml', 'application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml'),
                  ('/ppt/theme/theme1.xml', 'application/vnd.openxmlformats-officedocument.theme+xml'), ('/docProps/core.xml', 'application/vnd.openxmlformats-package.core-properties+xml')]
    defaults = ''.join(f'<Default Extension="{k[1:]}" ContentType="{v}"/>' for k, v in types.items())
    parts['[Content_Types].xml'] = (XMLH + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                                    f'<Default Extension="xml" ContentType="application/xml"/>{defaults}' + ''.join(f'<Override PartName="{p}" ContentType="{c}"/>' for p, c in overrides) + '</Types>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', parts.pop('[Content_Types].xml'))
        for name, data in parts.items():
            z.writestr(name, data)
        for src, name in media.items():
            z.write(src, f'ppt/media/{name}')


# --- Word --------------------------------------------------------------------------------------------------------------

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
W_DRAW = ('xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
          'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def _w_runs(inline: list) -> str:
    out = ''
    for piece in inline:
        props = ''
        if piece.get('bold'):
            props += '<w:b/>'
        if piece.get('italic'):
            props += '<w:i/>'
        if piece.get('code'):
            props += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:shd w:val="clear" w:color="auto" w:fill="EEEEEE"/>'
        out += f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{escape(piece["text"])}</w:t></w:r>'
    return out


def _w_para(inline: list, style: str = '', extra: str = '') -> str:
    p = f'<w:pStyle w:val="{style}"/>' if style else ''
    return f'<w:p><w:pPr>{p}{extra}</w:pPr>{_w_runs(inline)}</w:p>'


def _w_picture(rid: str, index: int, width_px: int, height_px: int) -> str:
    cx, cy = int(width_px * 9525), int(height_px * 9525)
    return (f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{index}" name="图片 {index}"/>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="{index}" name="图片 {index}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def _w_table(rows: list) -> str:
    cols = max(len(r) for r in rows)
    grid = ''.join('<w:gridCol w:w="2000"/>' for _ in range(cols))
    body = ''
    for ri, row in enumerate(rows):
        cells = ''
        for c in range(cols):
            inline = row[c] if c < len(row) else [{'text': ''}]
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="E9EDF4"/>' if ri == 0 else ''
            cells += f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/>{shade}</w:tcPr><w:p>{_w_runs([{**x, "bold": x.get("bold") or ri == 0} for x in inline])}</w:p></w:tc>'
        body += f'<w:tr>{cells}</w:tr>'
    border = ''.join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="BFC4CE"/>' for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    return f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{border}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl><w:p/>'


STYLES = (XMLH + f'<w:styles {W_NS}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="{FONT}"/><w:sz w:val="22"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/></w:rPr></w:rPrDefault>'
          '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="312" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
          + ''.join(f'<w:style w:type="paragraph" w:styleId="Heading{n}"><w:name w:val="heading {n}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="{b}" w:after="100"/><w:outlineLvl w:val="{n - 1}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{s}"/></w:rPr></w:style>'
                    for n, s, b in ((1, 36, 320), (2, 28, 260), (3, 24, 200)))
          + '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="48"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="400"/></w:pPr><w:rPr><w:i/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="19"/></w:rPr></w:style>'
          '</w:styles>')
NUMBERING = (XMLH + f'<w:numbering {W_NS}><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="420" w:hanging="300"/></w:pPr></w:lvl></w:abstractNum>'
             '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="420" w:hanging="300"/></w:pPr></w:lvl></w:abstractNum>'
             '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>')


def write_docx(path: Path, blocks: list, title: str, folder: Path) -> None:
    """blocks: from markdown.parse. Pictures are read relative to folder."""
    from PIL import Image

    body = ''
    media = []
    for b in blocks:
        kind = b['kind']
        if kind == 'heading':
            body += _w_para(b['inline'], 'Title' if b['level'] == 1 else f'Heading{b["level"] - 1}')
        elif kind == 'para':
            body += _w_para(b['inline'])
        elif kind == 'quote':
            body += _w_para(b['inline'], 'Quote')
        elif kind == 'list':
            num = '2' if b['ordered'] else '1'
            for item in b['items']:
                body += _w_para(item, '', f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>')
        elif kind == 'code':
            for line in b['text'].split('\n'):
                body += _w_para([{'text': line}], 'Code')
        elif kind == 'table':
            body += _w_table(b['rows'])
        elif kind == 'rule':
            body += '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="BFC4CE"/></w:pBdr></w:pPr></w:p>'
        elif kind == 'pagebreak':
            body += '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
        elif kind == 'image':
            src = (folder / b['path']).resolve()
            if src.is_file():
                with Image.open(src) as im:
                    w, h = im.size
                scale = min(1.0, 620 / w)
                media.append(src)
                body += _w_picture(f'rId{len(media) + 10}', len(media), int(w * scale), int(h * scale))
    section = '<w:sectPr><w:footerReference w:type="default" r:id="rId9"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1300" w:bottom="1440" w:left="1300" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    document = XMLH + f'<w:document {W_NS} {W_DRAW}><w:body>{body}{section}</w:body></w:document>'
    types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}
    defaults = ''.join(f'<Default Extension="{k[1:]}" ContentType="{v}"/>' for k, v in types.items())
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', XMLH + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   f'<Default Extension="xml" ContentType="application/xml"/>{defaults}<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                   '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>')
        z.writestr('_rels/.rels', _rels([('rId1', f'{REL}/officeDocument', 'word/document.xml'), ('rId2', 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties', 'docProps/core.xml')]))
        z.writestr('docProps/core.xml', XMLH + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   f'<dc:title>{escape(title)}</dc:title></cp:coreProperties>')
        z.writestr('word/document.xml', document)
        z.writestr('word/styles.xml', STYLES)
        z.writestr('word/numbering.xml', NUMBERING)
        z.writestr('word/footer1.xml', XMLH + f'<w:ftr {W_NS}><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:fldSimple w:instr="PAGE"><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p></w:ftr>')
        z.writestr('word/_rels/document.xml.rels', _rels([('rId1', f'{REL}/styles', 'styles.xml'), ('rId2', f'{REL}/numbering', 'numbering.xml'), ('rId9', f'{REL}/footer', 'footer1.xml')]
                                                        + [(f'rId{i + 11}', f'{REL}/image', f'media/image{i + 1}{m.suffix.lower()}') for i, m in enumerate(media)]))
        for i, m in enumerate(media):
            z.write(m, f'word/media/image{i + 1}{m.suffix.lower()}')


def word_count(text: str) -> int:
    return len(re.findall(r'[一-鿿]|[A-Za-z0-9]+', text))
