"""How a family writes its structures (library/families/*.py)."""
from __future__ import annotations

from dataclasses import dataclass, field

ALL = ('', 'soft', 'ink', 'brand', 'glow')
FOUR = ('', 'soft', 'ink', 'brand')
THREE = ('', 'soft', 'ink')


@dataclass
class S:
    """One structure. html: its markup, with %K where the look's class goes on its root (class='g g-<id>%K');
    css: its own rules, scoped under .g-<id>."""
    id: str
    name: str
    cat: str
    html: str
    css: str = ''
    fields: list = field(default_factory=list)
    looks: tuple = ALL
    icons: bool = False
    js: str = ''
    tags: str = ''
    extra: dict = field(default_factory=dict)
    needs: str = ''  # a shared style sheet (a family's KIT) instead of g-core / g-icons


def T(key, label, value):
    return {'key': key, 'label': label, 'type': 'text', 'value': value}


def L(key, label, value):
    return {'key': key, 'label': label, 'type': 'lines', 'value': value}


def A(key, label, value):
    return {'key': key, 'label': label, 'type': 'area', 'value': value}


def P(key, label, value):
    return {'key': key, 'label': label, 'type': 'image', 'value': value}


def head(eyebrow=True, center=True, lead=True):
    """The usual title block: a small label, the title, a line under it."""
    cls = 'g-head' if center else 'g-head-l'
    return (f"<div class='{cls}'>" + ("<div class='g-eb'>{{eyebrow}}</div>" if eyebrow else '') + "<h2 class='g-h'>{{title}}</h2>"
            + ("<p class='g-lead'>{{text}}</p>" if lead else '') + '</div>')


def head_fields(eyebrow='为什么选我们', title='把复杂的事做简单', text='一句话说清楚这一部分在讲什么，让人愿意往下看。', with_eyebrow=True, with_lead=True):
    out = [T('eyebrow', '小标题', eyebrow)] if with_eyebrow else []
    out.append(T('title', '标题', title))
    if with_lead:
        out.append(A('text', '说明', text))
    return out
