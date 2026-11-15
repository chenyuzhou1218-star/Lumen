"""导航栏: the bar at the top, seven ways."""
from parts import FOUR, S, L, T

LINKS = L('links', '链接（一行一个：文字|地址）', '产品|#\n例子|#\n价格|#\n关于|#')

ITEMS = [
    S('nav-pill', '悬浮胶囊', 'nav', looks=FOUR,
      html="<nav class='g g-nav-pill%K'><div class='g-w'><div class='g-np'><a class='g-np-logo' href='#'><i></i>{{brand}}</a>"
           "<div class='g-np-links'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></div></nav>",
      css=".g-nav-pill{padding:16px 0;background:transparent}.g-np{display:flex;align-items:center;gap:20px;padding:8px 8px 8px 20px;border:1px solid var(--g-line);"
          "border-radius:99px;background:var(--g-card);box-shadow:0 8px 28px rgba(0,0,0,.06)}"
          ".g-np-logo{display:flex;align-items:center;gap:9px;font-weight:700;letter-spacing:-.02em;text-decoration:none;color:var(--g-ink)}"
          ".g-np-logo i{width:20px;height:20px;border-radius:6px;background:var(--g-hl)}"
          ".g-np-links{display:flex;gap:4px;margin:0 auto;flex-wrap:wrap}.g-np-links a{padding:7px 14px;border-radius:99px;font-size:14.5px;text-decoration:none;color:var(--g-mute);transition:background .15s,color .15s}"
          ".g-np-links a:hover{background:var(--g-soft);color:var(--g-ink)}.g-nav-pill .g-b{height:38px;border-radius:99px;padding:0 18px;font-size:14px}"
          "@media(max-width:700px){.g-np{flex-wrap:wrap;border-radius:22px;padding:10px 10px 10px 16px}.g-np-links{order:3;width:100%;margin:0;justify-content:space-between}}",
      fields=[T('brand', '名字', '小满'), LINKS, T('button', '按钮', '开始用'), T('url', '按钮链接', '#')]),
    S('nav-split', '标志居中', 'nav', looks=FOUR,
      html="<nav class='g g-nav-split%K'><div class='g-w g-ns'><div class='g-ns-l'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div>"
           "<a class='g-ns-logo' href='#'>{{brand}}</a><div class='g-ns-r'><a href='{{url2}}'>{{button2}}</a><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></div></nav>",
      css=".g-nav-split{padding:0;border-bottom:1px solid var(--g-line)}.g-ns{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;min-height:72px;gap:20px}"
          ".g-ns-l{display:flex;gap:26px;flex-wrap:wrap}.g-ns a{text-decoration:none;font-size:14.5px;color:var(--g-mute)}.g-ns a:hover{color:var(--g-ink)}"
          ".g-ns .g-ns-logo{font-size:22px;font-weight:750;letter-spacing:-.04em;color:var(--g-ink)}"
          ".g-ns-r{display:flex;align-items:center;justify-content:flex-end;gap:20px}.g-ns-r .g-b{height:38px;padding:0 16px;font-size:14px;color:var(--g-on)}"
          "@media(max-width:760px){.g-ns{grid-template-columns:1fr auto;padding-top:12px;padding-bottom:12px}.g-ns-l{order:3;grid-column:1/-1;gap:18px}}",
      fields=[T('brand', '名字', '青 石'), L('links', '左边的链接（一行一个：文字|地址）', '作品|#\n日志|#\n关于|#'),
              T('button2', '右边的文字链接', '登录'), T('url2', '文字链接地址', '#'), T('button', '按钮', '联系我们'), T('url', '按钮链接', '#')]),
    S('nav-announce', '顶部通知条', 'nav', looks=FOUR,
      html="<nav class='g g-nav-ann%K'><a class='g-na-bar' href='{{note_url}}'>{{note}} <b>→</b></a><div class='g-w g-na'><a class='g-na-logo' href='#'>{{brand}}</a>"
           "<div class='g-na-links'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div><a class='g-b g-b2' href='{{url}}'>{{button}}</a></div></nav>",
      css=".g-nav-ann{padding:0;border-bottom:1px solid var(--g-line)}.g-na-bar{display:block;text-align:center;padding:9px 16px;font-size:13.5px;text-decoration:none;"
          "background:var(--g-acc);color:var(--g-on)}.g-na-bar b{display:inline-block;transition:transform .2s}.g-na-bar:hover b{transform:translateX(3px)}"
          ".g-na{display:flex;align-items:center;gap:32px;min-height:66px;flex-wrap:wrap}.g-na-logo{font-weight:750;font-size:18px;letter-spacing:-.03em;text-decoration:none;color:var(--g-ink)}"
          ".g-na-links{display:flex;gap:24px;flex:1;flex-wrap:wrap}.g-na-links a{text-decoration:none;font-size:14.5px;color:var(--g-mute)}.g-na-links a:hover{color:var(--g-ink)}"
          ".g-nav-ann .g-b{height:36px;padding:0 15px;font-size:14px}",
      fields=[T('note', '通知', '新版本上线了：几百种组件，免费用'), T('note_url', '通知链接', '#'), T('brand', '名字', '远山'), LINKS, T('button', '按钮', '登录'), T('url', '按钮链接', '#')]),
    S('nav-search', '带搜索框', 'nav', looks=FOUR,
      html="<nav class='g g-nav-srch%K'><div class='g-w g-nsr'><a class='g-nsr-logo' href='#'>{{brand}}</a><form class='g-nsr-f' action='{{search_url}}' method='get'>"
           "<input name='q' placeholder='{{hint}}' aria-label='{{hint}}'><kbd>/</kbd></form><div class='g-nsr-links'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div></div></nav>",
      css=".g-nav-srch{padding:0;border-bottom:1px solid var(--g-line)}.g-nsr{display:flex;align-items:center;gap:28px;min-height:68px;flex-wrap:wrap}"
          ".g-nsr-logo{font-weight:750;font-size:18px;letter-spacing:-.03em;text-decoration:none;color:var(--g-ink)}"
          ".g-nsr-f{flex:1;max-width:440px;position:relative}.g-nsr-f input{width:100%;height:40px;border:1px solid var(--g-line);border-radius:var(--g-r);background:var(--g-soft);"
          "padding:0 40px 0 14px;font:inherit;font-size:14px;color:var(--g-ink);outline:none;transition:border-color .15s,background .15s}"
          ".g-nsr-f input:focus{background:var(--g-card);border-color:var(--g-hl)}.g-nsr-f kbd{position:absolute;right:10px;top:9px;font:11px/20px inherit;padding:0 6px;"
          "border:1px solid var(--g-line);border-radius:5px;color:var(--g-faint)}"
          ".g-nsr-links{display:flex;gap:22px;margin-left:auto}.g-nsr-links a{text-decoration:none;font-size:14.5px;color:var(--g-mute)}.g-nsr-links a:hover{color:var(--g-ink)}"
          "@media(max-width:700px){.g-nsr{padding-top:12px;padding-bottom:12px;gap:14px}.g-nsr-f{order:3;max-width:none;flex-basis:100%}}",
      fields=[T('brand', '名字', '书架'), T('hint', '搜索框提示', '搜一本书、一个作者'), T('search_url', '搜索提交到', '#'), L('links', '链接（一行一个：文字|地址）', '分类|#\n新书|#\n我的|#')]),
    S('nav-tabs', '下划线标签', 'nav', looks=FOUR,
      html="<nav class='g g-nav-tabs%K'><div class='g-w'><div class='g-nt-top'><a class='g-nt-logo' href='#'>{{brand}}</a><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div>"
           "<div class='g-nt'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div></div></nav>",
      css=".g-nav-tabs{padding:0;border-bottom:1px solid var(--g-line)}.g-nt-top{display:flex;align-items:center;justify-content:space-between;min-height:62px}"
          ".g-nt-logo{font-weight:750;font-size:18px;letter-spacing:-.03em;text-decoration:none;color:var(--g-ink)}.g-nav-tabs .g-b{height:36px;padding:0 15px;font-size:14px}"
          ".g-nt{display:flex;gap:28px;overflow-x:auto;scrollbar-width:none}.g-nt a{padding:12px 0 13px;font-size:14.5px;text-decoration:none;color:var(--g-mute);"
          "border-bottom:2px solid transparent;white-space:nowrap;transition:color .15s,border-color .15s}"
          ".g-nt a:first-child{color:var(--g-ink);border-color:var(--g-ink);font-weight:600}.g-nt a:hover{color:var(--g-ink)}",
      fields=[T('brand', '名字', '工作台'), L('links', '标签（一行一个：文字|地址；第一个是当前页）', '总览|#\n项目|#\n成员|#\n报表|#\n设置|#'),
              T('button', '按钮', '新建'), T('url', '按钮链接', '#')]),
    S('nav-crumbs', '面包屑', 'nav', looks=('', 'soft'),
      html="<nav class='g g-nav-crumbs%K' aria-label='当前位置'><div class='g-w'><ol>{{#links}}<li><a href='{{2}}'>{{1}}</a></li>{{/links}}</ol></div></nav>",
      css=".g-nav-crumbs{padding:16px 0}.g-nav-crumbs ol{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px;font-size:14px}"
          ".g-nav-crumbs li{display:flex;align-items:center;gap:8px;color:var(--g-mute)}.g-nav-crumbs li+li:before{content:'/';color:var(--g-faint)}"
          ".g-nav-crumbs a{text-decoration:none;color:inherit}.g-nav-crumbs a:hover{color:var(--g-ink)}.g-nav-crumbs li:last-child a{color:var(--g-ink);font-weight:600}",
      fields=[L('links', '路径（一行一个：文字|地址；最后一个是当前页）', '首页|#\n文章|#\n怎么做一个好看的网页|#')]),
    S('nav-bar-two', '两个按钮', 'nav', looks=FOUR,
      html="<nav class='g g-nav-two%K'><div class='g-w g-n2'><a class='g-n2-logo' href='#'><svg viewBox='0 0 24 24'><circle cx='12' cy='12' r='9'/><path d='M7 12a5 5 0 0 1 10 0'/></svg>{{brand}}</a>"
           "<div class='g-n2-links'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div><div class='g-n2-btns'><a class='g-b g-b2' href='{{url2}}'>{{button2}}</a><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></div></nav>",
      css=".g-nav-two{padding:0;border-bottom:1px solid var(--g-line);position:sticky;top:0;z-index:20}.g-n2{display:flex;align-items:center;gap:36px;min-height:70px;flex-wrap:wrap}"
          ".g-n2-logo{display:flex;align-items:center;gap:9px;font-weight:750;font-size:18px;letter-spacing:-.03em;text-decoration:none;color:var(--g-ink)}"
          ".g-n2-logo svg{width:24px;height:24px;fill:none;stroke:var(--g-hl);stroke-width:2.4;stroke-linecap:round}"
          ".g-n2-links{display:flex;gap:26px;flex-wrap:wrap}.g-n2-links a{text-decoration:none;font-size:14.5px;color:var(--g-mute)}.g-n2-links a:hover{color:var(--g-ink)}"
          ".g-n2-btns{display:flex;gap:8px;margin-left:auto}.g-n2-btns .g-b{height:38px;padding:0 16px;font-size:14px}"
          "@media(max-width:760px){.g-n2{gap:12px 20px;padding-top:12px;padding-bottom:12px}.g-n2-links{order:3;width:100%}}",
      fields=[T('brand', '名字', '日出'), LINKS, T('button2', '第一个按钮', '登录'), T('url2', '第一个按钮链接', '#'), T('button', '第二个按钮', '免费注册'), T('url', '第二个按钮链接', '#')]),
]
