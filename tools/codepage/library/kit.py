"""What every generated component shares: the looks, the icons, the pictures, the motion.

A component is written once, as a structure (html with {{fields}}, its own css), and comes in several looks. A look is
a class on the component's root that sets a few colours of its own (--g-bg, --g-ink, --g-card ...) from the page's
theme, so the same structure is a white, a grey, an inverted, a brand-coloured or a glowing section and still follows
whatever theme the page has. Nothing here is a copy of another product's design.
"""
from __future__ import annotations

from urllib.parse import quote

# (key, name). The first is the structure as it is; the others are classes g-k-<key>.
LOOKS = [('', '常规'), ('soft', '灰底'), ('ink', '反色'), ('brand', '主色'), ('glow', '渐变')]
LOOK_NAMES = dict(LOOKS)

MUTE = 'color-mix(in srgb,var(--g-ink) 62%,var(--g-bg))'

CORE_CSS = (
    # the colours a look may change
    ".g{--g-bg:var(--cp-bg);--g-ink:var(--cp-ink);--g-card:var(--cp-bg);--g-soft:var(--cp-soft);--g-line:var(--cp-line);"
    "--g-acc:var(--cp-primary);--g-on:var(--cp-bg);--g-hl:var(--cp-primary);"
    "--g-mute:color-mix(in srgb,var(--g-ink) 62%,var(--g-bg));--g-faint:color-mix(in srgb,var(--g-ink) 40%,var(--g-bg));"
    "--g-r:var(--cp-radius);--g-r2:calc(var(--cp-radius)*1.6);"
    "background:var(--g-paint,var(--g-bg));color:var(--g-ink);padding:96px 0;position:relative;isolation:isolate}"
    ".g-k-soft{--g-bg:var(--cp-soft);--g-card:var(--cp-bg);--g-soft:color-mix(in srgb,var(--cp-soft) 93%,var(--cp-ink))}"
    ".g-k-ink{--g-bg:var(--cp-ink);--g-ink:var(--cp-bg);--g-card:color-mix(in srgb,var(--cp-bg) 7%,var(--cp-ink));"
    "--g-soft:color-mix(in srgb,var(--cp-bg) 10%,var(--cp-ink));--g-line:color-mix(in srgb,var(--cp-bg) 15%,var(--cp-ink));"
    "--g-acc:var(--cp-bg);--g-on:var(--cp-ink);--g-hl:color-mix(in srgb,var(--cp-primary) 55%,var(--cp-bg))}"
    ".g-k-brand{--g-bg:var(--cp-primary);--g-ink:var(--cp-bg);--g-card:color-mix(in srgb,var(--cp-bg) 11%,var(--cp-primary));"
    "--g-soft:color-mix(in srgb,var(--cp-bg) 16%,var(--cp-primary));--g-line:color-mix(in srgb,var(--cp-bg) 26%,var(--cp-primary));"
    "--g-acc:var(--cp-bg);--g-on:var(--cp-primary);--g-hl:var(--cp-bg)}"
    ".g-k-glow{--g-card:color-mix(in srgb,var(--cp-bg) 72%,transparent);"
    "--g-paint:radial-gradient(900px 480px at 88% -12%,color-mix(in srgb,var(--cp-primary) 20%,transparent),transparent 62%),"
    "radial-gradient(760px 460px at -8% 112%,color-mix(in srgb,var(--cp-primary) 12%,transparent),transparent 60%),var(--cp-bg)}"
    ".g-k-glow .g-card{-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px)}"
    # layout
    ".g-w{max-width:1120px;margin:0 auto;padding:0 28px}.g-wn{max-width:780px;margin:0 auto;padding:0 28px}"
    ".g-head{text-align:center;max-width:720px;margin:0 auto 56px}.g-head-l{max-width:640px;margin:0 0 48px}"
    ".g-eb{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:600;letter-spacing:.04em;color:var(--g-hl);margin-bottom:16px}"
    ".g-eb:before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}"
    ".g-pill{display:inline-flex;align-items:center;gap:8px;height:30px;padding:0 13px;border:1px solid var(--g-line);border-radius:99px;"
    "font-size:13px;font-weight:500;color:var(--g-mute);background:var(--g-card);margin-bottom:24px}"
    ".g-pill b{color:var(--g-hl);font-weight:600}"
    ".g-h{font-size:clamp(30px,4.2vw,46px);line-height:1.12;letter-spacing:-.035em;font-weight:700;margin:0;text-wrap:balance}"
    ".g-h1{font-size:clamp(40px,6.4vw,72px);line-height:1.04;letter-spacing:-.045em;font-weight:700;margin:0;text-wrap:balance}"
    ".g-h3{font-size:19px;line-height:1.3;letter-spacing:-.015em;font-weight:650;margin:0}"
    ".g-lead{font-size:clamp(17px,1.9vw,19px);line-height:1.65;color:var(--g-mute);margin-top:18px;text-wrap:pretty}"
    ".g-p{font-size:15px;line-height:1.65;color:var(--g-mute);margin-top:8px}"
    ".g-acts{display:flex;gap:12px;flex-wrap:wrap;margin-top:34px}.g-head .g-acts{justify-content:center}"
    # buttons
    ".g-b{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:46px;padding:0 22px;border-radius:var(--g-r);"
    "font:inherit;font-size:15px;font-weight:600;text-decoration:none;white-space:nowrap;border:1px solid transparent;cursor:pointer;"
    "transition:transform .18s,box-shadow .18s,background .18s,border-color .18s}"
    ".g-b:hover{transform:translateY(-1px)}.g-b1{background:var(--g-acc);color:var(--g-on);box-shadow:0 1px 2px rgba(0,0,0,.14)}"
    ".g-b1:hover{box-shadow:0 8px 22px color-mix(in srgb,var(--g-acc) 30%,transparent)}"
    ".g-b2{background:transparent;color:var(--g-ink);border-color:var(--g-line)}.g-b2:hover{border-color:var(--g-faint)}"
    ".g-b3{color:var(--g-ink);font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:6px;font-size:15px}"
    ".g-b3:after{content:'→';transition:transform .18s}.g-b3:hover:after{transform:translateX(3px)}"
    # surfaces
    ".g-card{background:var(--g-card);border:1px solid var(--g-line);border-radius:var(--g-r2);padding:28px}"
    ".g-lift{transition:transform .28s cubic-bezier(.2,.7,.2,1),box-shadow .28s,border-color .28s}"
    ".g-lift:hover{transform:translateY(-4px);box-shadow:0 18px 40px rgba(0,0,0,.09);border-color:var(--g-faint)}"
    ".g-img{display:block;width:100%;height:100%;object-fit:cover;border-radius:var(--g-r2);background:var(--g-soft)}"
    ".g-frame{border-radius:calc(var(--g-r2) + 6px);padding:6px;background:var(--g-card);border:1px solid var(--g-line);"
    "box-shadow:0 30px 70px rgba(0,0,0,.12)}"
    ".g-tag{display:inline-flex;align-items:center;height:24px;padding:0 9px;border-radius:99px;background:var(--g-soft);"
    "font-size:12px;font-weight:600;color:var(--g-mute)}"
    ".g-num{font-variant-numeric:tabular-nums;letter-spacing:-.04em;font-weight:700}"
    ".g-dots{background-image:radial-gradient(color-mix(in srgb,var(--g-ink) 16%,transparent) 1px,transparent 1.2px);background-size:22px 22px}"
    ".g-lines{background-image:linear-gradient(color-mix(in srgb,var(--g-ink) 7%,transparent) 1px,transparent 1px),"
    "linear-gradient(90deg,color-mix(in srgb,var(--g-ink) 7%,transparent) 1px,transparent 1px);background-size:44px 44px}"
    # grids
    ".g-g2,.g-g3,.g-g4{display:grid;gap:18px}.g-g2{grid-template-columns:repeat(2,minmax(0,1fr))}"
    ".g-g3{grid-template-columns:repeat(3,minmax(0,1fr))}.g-g4{grid-template-columns:repeat(4,minmax(0,1fr))}"
    ".g-split{display:grid;grid-template-columns:1.05fr 1fr;gap:64px;align-items:center}"
    "@media(max-width:900px){.g-g4{grid-template-columns:repeat(2,minmax(0,1fr))}.g-g3{grid-template-columns:repeat(2,minmax(0,1fr))}"
    ".g-split{grid-template-columns:1fr;gap:40px}}"
    "@media(max-width:640px){.g{padding:68px 0}.g-g2,.g-g3,.g-g4{grid-template-columns:1fr}.g-w,.g-wn{padding:0 20px}"
    ".g-head{margin-bottom:40px}.g-card{padding:24px}}"
)

# Line icons on a 24 grid, drawn for this library. A field holding the name ("bolt") shows the icon: <i class='g-i g-i-{{1}}'>.
ICONS = {
    'bolt': 'M13 2.5 4.5 13.5H12l-1 8 8.5-11H12z',
    'shield': 'M12 2.8 4.5 5.6v5.6c0 4.6 3.1 8.6 7.5 10 4.4-1.4 7.5-5.4 7.5-10V5.6z M9 12l2.2 2.2L15.5 10',
    'chart': 'M4 20h16 M7 16v-5 M12 16V7 M17 16v-8',
    'globe': 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M3.5 12h17 M12 3c2.6 2.6 3.8 5.6 3.8 9s-1.2 6.4-3.8 9c-2.6-2.6-3.8-5.6-3.8-9S9.4 5.6 12 3z',
    'heart': 'M12 20s-7.5-4.4-7.5-10.1A4.3 4.3 0 0 1 12 7.4a4.3 4.3 0 0 1 7.5 2.5C19.5 15.6 12 20 12 20z',
    'star': 'm12 3.2 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z',
    'users': 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M2.8 20c.6-3.4 3.1-5.5 6.2-5.5s5.6 2.1 6.2 5.5 M16 4.3a3.4 3.4 0 0 1 0 6.4 M18.2 14.8c1.7.8 2.8 2.6 3.1 5.2',
    'lock': 'M6 10.5h12v9.5H6z M8.5 10.5V7.8a3.5 3.5 0 0 1 7 0v2.7 M12 14.3v2.2',
    'cloud': 'M7.5 18.5h9.8a4 4 0 0 0 .4-8 5.6 5.6 0 0 0-10.8 1.4A3.3 3.3 0 0 0 7.5 18.5z',
    'code': 'm8.5 7.5-4.5 4.5 4.5 4.5 M15.5 7.5l4.5 4.5-4.5 4.5 M13.4 5l-2.8 14',
    'camera': 'M4 8h3.5l1.6-2.5h5.8L16.5 8H20v11H4z M12 16.5a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4z',
    'chat': 'M4.5 5.5h15v10h-8.2L7 19.2v-3.7H4.5z M8.5 10.5h7',
    'clock': 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z M12 7.5V12l3 2',
    'leaf': 'M5 19c0-8 5-13.5 14-14 .4 9-5 14-12 14H5z M5 19c3-3.8 6-6.3 9.5-8',
    'rocket': 'M14.5 4.5c2.6-.9 4.4-.8 5-.5.3.6.4 2.4-.5 5L13 15.5l-4.5-4.5z M8.5 11 5.5 11 3.5 13.5l3.6 1 M13 15.5V18.5l-2.5 2-1-3.6 M6.5 17.5 4 20',
    'spark': 'M12 3v4.5 M12 16.5V21 M3 12h4.5 M16.5 12H21 M6 6l2.8 2.8 M15.2 15.2 18 18 M18 6l-2.8 2.8 M8.8 15.2 6 18',
    'check': 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z m-3.6 8.7 2.4 2.4 4.6-4.9',
    'gift': 'M4 9h16v3.5H4z M5.5 12.5H18.5V20h-13z M12 9v11 M12 9C10.5 5.5 7 5.3 7 7.2 7 8.6 9.8 9 12 9zm0 0c1.5-3.5 5-3.7 5-1.8 0 1.4-2.8 1.8-5 1.8z',
    'phone': 'M8 3h8v18H8z M11 18h2',
    'mail': 'M4 6h16v12H4z m.4.4L12 12.5l7.6-6.1',
    'pin': 'M12 21s-6.5-6.2-6.5-11.2a6.5 6.5 0 0 1 13 0C18.5 14.8 12 21 12 21z M12 12.3a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
    'book': 'M5 4.5h5.5A2.5 2.5 0 0 1 13 7v13a2 2 0 0 0-2-2H5z M19 4.5h-5.5A2.5 2.5 0 0 0 11 7v13a2 2 0 0 1 2-2h6z',
    'cart': 'M3.5 4.5h2.4l2 10.5h10.3l1.8-7.5H7 M9.5 19.6a.6.6 0 1 0 0-1.2.6.6 0 0 0 0 1.2z M17 19.6a.6.6 0 1 0 0-1.2.6.6 0 0 0 0 1.2z',
    'music': 'M9 17.5V5.5l10-2v12 M9 17.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z M19 15.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z',
    'cup': 'M5 8h11v6.5a4.5 4.5 0 0 1-4.5 4.5h-2A4.5 4.5 0 0 1 5 14.5z M16 9.5h1.5a2.5 2.5 0 0 1 0 5H16 M8.5 3.5v2 M11.5 3.5v2',
    'home': 'M4 11 12 4.5l8 6.5 M6 9.5V20h12V9.5 M10 20v-5.5h4V20',
    'layers': 'm12 3.5 8.5 4.5-8.5 4.5L3.5 8z m-8.5 8.3 8.5 4.5 8.5-4.5 M3.5 15.5 12 20l8.5-4.5',
    'search': 'M10.8 4a6.8 6.8 0 1 0 0 13.6 6.8 6.8 0 0 0 0-13.6z m4.9 11.7 4.3 4.3',
    'gear': 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M12 2.8v2.6 M12 18.6v2.6 M2.8 12h2.6 M18.6 12h2.6 M5.5 5.5l1.8 1.8 M16.7 16.7l1.8 1.8 M18.5 5.5l-1.8 1.8 M7.3 16.7l-1.8 1.8',
    'bell': 'M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z M10 20.5h4',
    'sun': 'M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z M12 2.5v2 M12 19.5v2 M2.5 12h2 M19.5 12h2 M5.3 5.3l1.4 1.4 M17.3 17.3l1.4 1.4 M18.7 5.3l-1.4 1.4 M6.7 17.3l-1.4 1.4',
    'flag': 'M5.5 21V4 M5.5 4.5h12l-2.5 4 2.5 4h-12',
    'target': 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z M12 11.2a.8.8 0 1 0 0 1.6.8.8 0 0 0 0-1.6z',
    'wand': 'm4 20 11-11 M13 7l2-2 2 2-2 2z M18 3.5v2 M20.5 6h-2 M19.5 10.5v2 M9.5 3.5v2',
    'arrow': 'M5 12h14 M13 6l6 6-6 6',
}


def _svg_uri(path: str) -> str:
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.7' "
           f"stroke-linecap='round' stroke-linejoin='round'><path d='{path}'/></svg>")
    return 'data:image/svg+xml,' + quote(svg, safe=" '=:/,.-")


ICON_CSS = (
    ".g-i{display:inline-block;width:22px;height:22px;flex:none;background:currentColor;"
    "-webkit-mask:var(--g-i) center/contain no-repeat;mask:var(--g-i) center/contain no-repeat}"
    ".g-ib{display:inline-flex;align-items:center;justify-content:center;width:46px;height:46px;border-radius:calc(var(--g-r) + 2px);"
    "background:var(--g-soft);color:var(--g-hl);flex:none}"
    + ''.join(f'.g-i-{name}{{--g-i:url("{_svg_uri(path)}")}}' for name, path in ICONS.items())
)
ICON_HELP = '图标名：' + ' '.join(ICONS)


def _pic(svg: str) -> str:
    return 'data:image/svg+xml,' + quote(svg, safe=" '=:/,.-()")


def _scene(w, h, sky, hills, sun=None, extra=''):
    stops = ''.join(f"<stop offset='{o}' stop-color='{c}'/>" for o, c in sky)
    out = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid slice'>"
           f"<defs><linearGradient id='s' x1='0' y1='0' x2='0' y2='1'>{stops}</linearGradient></defs>"
           f"<rect width='{w}' height='{h}' fill='url(#s)'/>")
    if sun:
        out += f"<circle cx='{sun[0]}' cy='{sun[1]}' r='{sun[2]}' fill='{sun[3]}'/>"
    out += extra + ''.join(f"<path d='{d}' fill='{c}'/>" for d, c in hills) + '</svg>'
    return _pic(out)


def _face(bg, skin, hair, shirt):
    return _pic(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 400'><rect width='400' height='400' fill='{bg}'/>"
                f"<path d='M70 400c8-78 62-118 130-118s122 40 130 118z' fill='{shirt}'/><rect x='172' y='230' width='56' height='60' rx='22' fill='{skin}'/>"
                f"<ellipse cx='200' cy='180' rx='70' ry='82' fill='{skin}'/><path d='M128 176c-6-62 30-104 76-104 50 0 78 38 72 104-10-34-40-52-72-54-34 2-62 20-76 54z' fill='{hair}'/></svg>")


# Pictures a new component starts with, so it looks finished before the user has a photo of their own.
PICTURES = {
    '@city': _scene(800, 500, [(0, '#dfe8f5'), (1, '#b8c8e2')], [
        ('M0 500V300h60v-80h50v120h40V180h70v160h30V250h60v250z', '#7f93b6'),
        ('M380 500V230h80v-70h60v110h40V200h70v140h40V280h130v220z', '#6a7fa5'),
        ('M0 500V400h800v100z', '#53668c')], sun=(640, 120, 46, '#f8f1dc')),
    '@sea': _scene(800, 500, [(0, '#fbe3c6'), (.55, '#f6b996'), (.56, '#5f86b0'), (1, '#2f4f78')],
                   [('M0 330q200-18 400 0t400 0v170H0z', '#46698f'), ('M0 400q200-14 400 0t400 0v100H0z', '#36557a')],
                   sun=(400, 260, 64, '#fff2d9')),
    '@forest': _scene(800, 500, [(0, '#e7f0e4'), (1, '#c4d8c0')], [
        ('M0 500V330l70-120 70 120 60-160 80 160 60-110 70 110 80-170 90 170 70-120 70 120 80-140v340z', '#5f8a68'),
        ('M0 500V400l90-90 90 90 80-120 90 120 90-80 100 80 100-130 80 130 80-80v200z', '#3f6b4c')], sun=(170, 110, 40, '#fbf6e4')),
    '@desk': _pic("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 500'><rect width='800' height='500' fill='#efe9e1'/>"
                  "<rect y='330' width='800' height='170' fill='#d9cbb8'/><rect x='250' y='120' width='300' height='190' rx='12' fill='#2a2c33'/>"
                  "<rect x='264' y='134' width='272' height='162' rx='4' fill='#e8edf7'/><rect x='282' y='154' width='120' height='12' rx='6' fill='#b9c6e0'/>"
                  "<rect x='282' y='178' width='220' height='8' rx='4' fill='#d3dbeb'/><rect x='282' y='196' width='190' height='8' rx='4' fill='#d3dbeb'/>"
                  "<rect x='282' y='226' width='96' height='52' rx='6' fill='#c9d5ee'/><rect x='390' y='226' width='96' height='52' rx='6' fill='#dde4f2'/>"
                  "<path d='M370 310h60l14 22h-88z' fill='#3a3d45'/><rect x='600' y='250' width='54' height='80' rx='10' fill='#fff'/>"
                  "<path d='M654 268h14a14 14 0 0 1 0 28h-14' stroke='#fff' stroke-width='8' fill='none'/><circle cx='150' cy='300' r='34' fill='#8fae8a'/>"
                  "<rect x='132' y='300' width='36' height='32' rx='6' fill='#b88a6a'/></svg>"),
    '@product': _pic("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 600'><defs><linearGradient id='b' x1='0' y1='0' x2='1' y2='1'>"
                     "<stop offset='0' stop-color='#f4f4f6'/><stop offset='1' stop-color='#e3e4ea'/></linearGradient></defs><rect width='600' height='600' fill='url(#b)'/>"
                     "<ellipse cx='300' cy='470' rx='170' ry='22' fill='#000' opacity='.08'/><rect x='200' y='150' width='200' height='310' rx='36' fill='#24262d'/>"
                     "<rect x='222' y='176' width='156' height='120' rx='18' fill='#3a3d47'/><circle cx='300' cy='370' r='44' fill='#30323a' stroke='#4a4d58' stroke-width='6'/>"
                     "<rect x='276' y='124' width='48' height='30' rx='8' fill='#3a3d47'/></svg>"),
    '@abstract': _pic("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 500'><rect width='800' height='500' fill='#eef0f7'/>"
                      "<circle cx='620' cy='120' r='180' fill='#c9d3f2'/><circle cx='180' cy='420' r='220' fill='#dfe3f3'/>"
                      "<rect x='300' y='160' width='240' height='240' rx='120' fill='#9fb0e6' opacity='.8'/><circle cx='420' cy='250' r='60' fill='#fff' opacity='.7'/></svg>"),
    '@warm': _pic("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 500'><rect width='800' height='500' fill='#f7ece2'/>"
                  "<circle cx='160' cy='110' r='170' fill='#f1cfb2'/><circle cx='690' cy='430' r='230' fill='#ebc0a0'/>"
                  "<path d='M260 380c60-140 220-220 360-150-80 10-170 70-200 170z' fill='#d98e6a' opacity='.85'/></svg>"),
    '@app': _pic("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 360 720'><rect width='360' height='720' rx='48' fill='#fff'/>"
                 "<rect x='24' y='64' width='150' height='18' rx='9' fill='#1c1d22'/><rect x='24' y='96' width='220' height='10' rx='5' fill='#d9dbe2'/>"
                 "<rect x='24' y='134' width='312' height='170' rx='22' fill='#eef1f8'/><path d='M44 270l50-46 40 30 52-62 60 50 70-40v94H44z' fill='#c3cdea'/>"
                 "<rect x='24' y='330' width='148' height='110' rx='20' fill='#f3f4f7'/><rect x='188' y='330' width='148' height='110' rx='20' fill='#1c1d22'/>"
                 "<rect x='40' y='350' width='60' height='10' rx='5' fill='#c9ccd6'/><rect x='40' y='390' width='90' height='24' rx='8' fill='#1c1d22'/>"
                 "<rect x='204' y='350' width='60' height='10' rx='5' fill='#5a5d68'/><rect x='204' y='390' width='90' height='24' rx='8' fill='#fff'/>"
                 "<rect x='24' y='466' width='312' height='64' rx='18' fill='#f3f4f7'/><rect x='24' y='544' width='312' height='64' rx='18' fill='#f3f4f7'/>"
                 "<circle cx='60' cy='498' r='16' fill='#d0d4e0'/><rect x='88' y='490' width='140' height='16' rx='8' fill='#d9dbe2'/>"
                 "<circle cx='60' cy='576' r='16' fill='#d0d4e0'/><rect x='88' y='568' width='110' height='16' rx='8' fill='#d9dbe2'/>"
                 "<rect x='120' y='684' width='120' height='6' rx='3' fill='#1c1d22'/></svg>"),
    '@face1': _face('#e6ebf3', '#f0c7a8', '#3a2c27', '#4f6a96'),
    '@face2': _face('#f3e9e4', '#e2b48f', '#1e1a1a', '#c76b54'),
    '@face3': _face('#e9f0ea', '#c9926c', '#2b2420', '#5d8a6a'),
    '@face4': _face('#efe9f3', '#f3d2b9', '#8a5a3c', '#6a5a9a'),
}

ANIM_CSS = (
    ".cp-js .cp-anim{opacity:0;transition:opacity .8s cubic-bezier(.2,.7,.2,1),transform .8s cubic-bezier(.2,.7,.2,1)}"
    ".cp-js .cp-anim-up{transform:translateY(32px)}.cp-js .cp-anim-zoom{transform:scale(.94)}"
    ".cp-js .cp-anim-left{transform:translateX(-44px)}.cp-js .cp-anim-right{transform:translateX(44px)}"
    ".cp-js .cp-anim.cp-in{opacity:1;transform:none}"
    "@media (prefers-reduced-motion:reduce){.cp-js .cp-anim{opacity:1;transform:none;transition:none}}"
)
# Shown as they come into view; without script, or in the builder, everything is simply there.
ANIM_JS = (
    "(function(){var d=document.documentElement,a=document.querySelectorAll('.cp-anim');"
    "if(!('IntersectionObserver' in window)){return}"
    "var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('cp-in');io.unobserve(e.target)}})},"
    "{threshold:.12,rootMargin:'0px 0px -6% 0px'});"
    "d.classList.add('cp-js');a.forEach(function(e){io.observe(e)})})();"
)
