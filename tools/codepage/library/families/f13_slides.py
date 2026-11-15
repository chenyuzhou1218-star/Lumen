"""幻灯片: a deck of 16:9 slides inside the page, and the slides to fill it.

The deck holds one list of components per slide, as many as there are ({{slot:*}} in render.js / codepage.py). In the
builder every slide is shown, one under another, so things can be dropped into each; in the page people get, the
deck shows one slide at a time: arrows, keys, swipe, a counter, full screen, and printing puts one slide on a page.

The slides are sized by the width they are shown at (container units), so the same slide is right in the page, in
full screen and in a thumbnail.
"""
from kit import ICON_HELP
from parts import S, A, L, P, T

DECK_JS = (
    "document.querySelectorAll('.cp-deck').forEach(function(d){var st=d.querySelector('.cp-deck-stage'),s=st.querySelectorAll(':scope>.cp-slide'),"
    "n=s.length,i=0,b=d.querySelector('.cp-deck-n b'),x0=null;if(!n)return;d.querySelector('.cp-deck-n i').textContent=n;d.classList.add('on');d.tabIndex=0;"
    "function go(k){i=(k+n)%n;if(k>=n&&!d.dataset.loop)i=n-1;if(k<0&&!d.dataset.loop)i=0;s.forEach(function(e,j){e.classList.toggle('cur',j==i);e.classList.toggle('past',j<i)});"
    "b.textContent=i+1;d.querySelector('[data-deck=prev]').disabled=i==0;d.querySelector('[data-deck=next]').disabled=i==n-1}"
    "d.addEventListener('click',function(e){var a=e.target.closest('[data-deck]');if(a){var w=a.dataset.deck;if(w=='prev')go(i-1);if(w=='next')go(i+1);"
    "if(w=='full'){if(document.fullscreenElement)document.exitFullscreen();else if(d.requestFullscreen){d.requestFullscreen();d.focus()}}return}"
    "if(document.fullscreenElement==d&&!e.target.closest('a,button,input,textarea,select,summary'))go(i+1)});"
    "d.addEventListener('keydown',function(e){if(e.key=='ArrowRight'||e.key=='PageDown'||e.key==' '){go(i+1);e.preventDefault()}"
    "else if(e.key=='ArrowLeft'||e.key=='PageUp'){go(i-1);e.preventDefault()}else if(e.key=='Home'){go(0)}else if(e.key=='End'){go(n-1)}});"
    "st.addEventListener('pointerdown',function(e){x0=e.clientX});st.addEventListener('pointerup',function(e){if(x0===null)return;var dx=e.clientX-x0;x0=null;"
    "if(Math.abs(dx)>50)go(i+(dx<0?1:-1))});var t=parseFloat(d.dataset.auto)||0;if(t>0)setInterval(function(){if(!d.matches(':hover')&&document.visibilityState=='visible')"
    "go(i+1<n?i+1:0)},t*1000);go(0)});"
)

DECK_CSS = (
    ".cp-deck{max-width:1120px;margin:0 auto;padding:48px 28px}.cp-deck-stage{position:relative;counter-reset:cp-sl}"
    ".cp-slide{position:relative;aspect-ratio:16/9;overflow:hidden;border-radius:14px;background:var(--cp-bg);display:flex;flex-direction:column;container-type:inline-size;"
    "box-shadow:0 0 0 1px var(--cp-line),0 24px 60px rgba(0,0,0,.10);counter-increment:cp-sl}.cp-slide+.cp-slide{margin-top:28px}"
    ".cp-slide>.cp-slot{flex:1;display:flex;flex-direction:column;min-height:0}.cp-slide>.cp-slot>.cp-block{flex:1;display:flex;flex-direction:column;min-height:0}"
    ".cp-slide .g-slc{aspect-ratio:auto;flex:1;border-radius:0}.cp-slide .g:not(.g-sl){padding:5cqw 0}"
    ".cp-deck-bar{display:none;align-items:center;justify-content:center;gap:8px;margin-top:18px}"
    ".cp-deck-bar button{width:40px;height:40px;border-radius:50%;border:1px solid var(--cp-line);background:var(--cp-bg);color:var(--cp-ink);font:inherit;font-size:18px;"
    "line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:border-color .15s,opacity .15s}"
    ".cp-deck-bar button:hover{border-color:color-mix(in srgb,var(--cp-ink) 40%,var(--cp-bg))}.cp-deck-bar button:disabled{opacity:.35;cursor:default}"
    ".cp-deck-n{min-width:64px;text-align:center;font-size:14px;color:color-mix(in srgb,var(--cp-ink) 62%,var(--cp-bg));font-variant-numeric:tabular-nums}"
    ".cp-deck-n b{color:var(--cp-ink)}.cp-deck-n i{font-style:normal}.cp-deck-bar [data-deck=full]{margin-left:10px;font-size:15px}"
    ".cp-deck.on{outline:none}.cp-deck.on .cp-deck-stage{aspect-ratio:16/9}"
    ".cp-deck.on .cp-slide{position:absolute;inset:0;margin:0;opacity:0;visibility:hidden;transform:translateX(3%);transition:opacity .5s cubic-bezier(.2,.7,.2,1),transform .5s cubic-bezier(.2,.7,.2,1),visibility .5s}"
    ".cp-deck.on .cp-slide.past{transform:translateX(-3%)}.cp-deck.on .cp-slide.cur{opacity:1;visibility:visible;transform:none}.cp-deck.on .cp-deck-bar{display:flex}"
    ".cp-deck:fullscreen{max-width:none;padding:0;background:#000;display:flex;flex-direction:column;justify-content:center}"
    ".cp-deck:fullscreen .cp-deck-stage{width:min(100vw,177.78vh);margin:0 auto}.cp-deck:fullscreen .cp-slide{border-radius:0;box-shadow:none}"
    ".cp-deck:fullscreen .cp-deck-bar{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);margin:0;padding:6px;border-radius:99px;background:rgba(20,20,22,.7);"
    "opacity:0;transition:opacity .3s}.cp-deck:fullscreen:hover .cp-deck-bar{opacity:1}.cp-deck:fullscreen .cp-deck-bar button{background:transparent;border-color:transparent;color:#fff}"
    ".cp-deck:fullscreen .cp-deck-n,.cp-deck:fullscreen .cp-deck-n b{color:#fff}"
    "@media print{@page{size:landscape;margin:0}.cp-deck{padding:0;max-width:none}.cp-deck .cp-deck-stage{aspect-ratio:auto}"
    ".cp-deck .cp-slide,.cp-deck.on .cp-slide{position:relative;opacity:1;visibility:visible;transform:none;margin:0;border-radius:0;box-shadow:none;break-after:page}"
    ".cp-deck-bar{display:none!important}}"
    "@media(max-width:640px){.cp-deck{padding:28px 14px}.cp-slide{border-radius:10px}}"
)

# what every slide shares: sized by its own width
SL = ("<div class='g-slc'><div class='g g-sl g-s-{id}%K'>{body}</div></div>")
SL_CSS = (".g-slc{container-type:inline-size;aspect-ratio:16/9;display:flex;flex-direction:column;overflow:hidden}"
          ".g-sl{flex:1;padding:6cqw 7cqw;display:flex;flex-direction:column;justify-content:center;min-height:0}"
          ".g-sl .g-sl-k{font-size:1.5cqw;font-weight:600;letter-spacing:.06em;color:var(--g-hl);margin-bottom:1.6cqw}"
          ".g-sl .g-sl-h{font-size:4.4cqw;line-height:1.12;letter-spacing:-.035em;font-weight:700;margin:0;text-wrap:balance}"
          ".g-sl .g-sl-p{font-size:2cqw;line-height:1.6;color:var(--g-mute);margin-top:1.6cqw;text-wrap:pretty}"
          ".g-sl .g-sl-foot{position:absolute;left:7cqw;right:7cqw;bottom:3.2cqw;display:flex;justify-content:space-between;font-size:1.25cqw;color:var(--g-faint)}")


KIT = [{'id': 'g-slide', 'css': SL_CSS, 'needs': 'g-icons'}]  # once on a page, however many kinds of slide


def sl(id, name, body, css, fields, icons=False):
    return S(f'sl-{id}', name, 'slides', html=SL.replace('{id}', id).replace('{body}', body), css=css, fields=fields, needs='g-slide')


ITEMS = [
    S('deck', '幻灯片（翻页放映）', 'slides', looks=('',), js=DECK_JS,
      html="<div class='cp-deck' data-auto='{{auto}}'><div class='cp-deck-stage'>{{slot:*}}</div><div class='cp-deck-bar'>"
           "<button type='button' data-deck='prev' aria-label='上一页'>‹</button><span class='cp-deck-n'><b>1</b> / <i></i></span>"
           "<button type='button' data-deck='next' aria-label='下一页'>›</button><button type='button' data-deck='full' aria-label='全屏放映' title='全屏放映'>⛶</button></div></div>",
      css=DECK_CSS,
      fields=[T('auto', '自动翻页（几秒一页；0 是不自动）', '0')],
      tags='ppt 演示 放映 slides presentation',
      extra={'slides': True, 'kids': [['sl-cover'], ['sl-agenda'], ['sl-bullets'], ['sl-chart'], ['sl-end']]}),
    sl('cover', '封面页', "<div class='g-sl-k'>{{kicker}}</div><h1 class='g-sl-h'>{{title}}</h1><p class='g-sl-p'>{{text}}</p><div class='g-sl-foot'><span>{{who}}</span><span>{{date}}</span></div>",
       ".g-s-cover .g-sl-h{font-size:6.2cqw;max-width:80%}.g-s-cover:after{content:'';position:absolute;right:-8cqw;top:-10cqw;width:34cqw;height:34cqw;border-radius:50%;"
       "background:radial-gradient(circle,color-mix(in srgb,var(--cp-primary) 22%,transparent),transparent 70%)}",
       [T('kicker', '小标题', '年度回顾'), T('title', '标题', '我们这一年做了什么'), A('text', '副标题', '从三个人到一个团队，从一个想法到几百个组件。'), T('who', '左下角', '小满团队'), T('date', '右下角', '2026 年 11 月')]),
    sl('section', '章节页', "<span class='g-sl-num g-num'>{{num}}</span><h2 class='g-sl-h'>{{title}}</h2><p class='g-sl-p'>{{text}}</p>",
       ".g-s-section .g-sl-num{font-size:12cqw;line-height:1;color:transparent;-webkit-text-stroke:.18cqw var(--g-hl);margin-bottom:2cqw}",
       [T('num', '编号', '02'), T('title', '标题', '我们做对了哪些事'), A('text', '说明', '三件事，让用户留了下来。')]),
    sl('bullets', '要点页', "<div class='g-sl-k'>{{kicker}}</div><h2 class='g-sl-h'>{{title}}</h2><ul class='g-sl-ul'>{{#items}}<li>{{1}}</li>{{/items}}</ul>",
       ".g-sl-ul{list-style:none;margin:3cqw 0 0;padding:0;display:grid;gap:1.6cqw}.g-sl-ul li{position:relative;padding-left:3.4cqw;font-size:2.3cqw;line-height:1.45}"
       ".g-sl-ul li:before{content:'';position:absolute;left:0;top:.75cqw;width:1.3cqw;height:1.3cqw;border-radius:50%;background:var(--g-hl)}",
       [T('kicker', '小标题', '要点'), T('title', '标题', '这一年最重要的三件事'), L('items', '要点（一行一个）', '新编辑器上线，做一页只要三分钟\n组件从六十个增加到六百多个\n用户里有一半是朋友介绍来的')]),
    sl('two-col', '两栏页', "<h2 class='g-sl-h'>{{title}}</h2><div class='g-sl-2'><div><h3>{{left_title}}</h3><p>{{left}}</p></div><div><h3>{{right_title}}</h3><p>{{right}}</p></div></div>",
       ".g-sl-2{display:grid;grid-template-columns:1fr 1fr;gap:5cqw;margin-top:4cqw}.g-sl-2 h3{font-size:2.4cqw;margin:0 0 1.2cqw;letter-spacing:-.02em}"
       ".g-sl-2 p{font-size:1.9cqw;line-height:1.65;color:var(--g-mute)}.g-sl-2>div{border-top:.25cqw solid var(--g-ink);padding-top:2cqw}",
       [T('title', '标题', '两个方向'), T('left_title', '左栏标题', '做得更快'), A('left', '左栏内容', '打开更快，拖动更顺，导出只要一秒。'), T('right_title', '右栏标题', '做得更好看'), A('right', '右栏内容', '更多组件，更多配色，每个细节都重新调过。')]),
    sl('pic-right', '图文页', "<div class='g-sl-pr'><div><div class='g-sl-k'>{{kicker}}</div><h2 class='g-sl-h'>{{title}}</h2><p class='g-sl-p'>{{text}}</p></div><img src='{{pic}}' alt=''></div>",
       ".g-s-pic-right{padding:0}.g-sl-pr{display:grid;grid-template-columns:1fr 1fr;height:100%}.g-sl-pr>div{padding:6cqw 5cqw 6cqw 7cqw;display:flex;flex-direction:column;justify-content:center}"
       ".g-sl-pr img{width:100%;height:100%;object-fit:cover;display:block}",
       [T('kicker', '小标题', '新功能'), T('title', '标题', '在网页里放一组幻灯片'), A('text', '说明', '翻页、全屏、打印成 PDF，都可以。'), P('pic', '图片', '@desk')]),
    sl('pic-full', '整页图片', "<img class='g-sl-bg' src='{{pic}}' alt=''><div class='g-sl-cap'><h2 class='g-sl-h'>{{title}}</h2><p class='g-sl-p'>{{text}}</p></div>",
       ".g-s-pic-full{padding:0;justify-content:flex-end;color:#fff}.g-sl-bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}"
       ".g-sl-cap{position:relative;padding:12cqw 7cqw 5cqw;background:linear-gradient(transparent,rgba(0,0,0,.6))}.g-sl-cap .g-sl-p{color:rgba(255,255,255,.85)}",
       [P('pic', '图片', '@sea'), T('title', '标题', '我们去了海边'), A('text', '说明', '团建的第三天，所有人都晒黑了。')]),
    sl('big-num', '大数字页', "<span class='g-sl-big g-num'>{{num}}</span><p class='g-sl-p'>{{text}}</p>",
       ".g-s-big-num{text-align:center;align-items:center}.g-sl-big{font-size:17cqw;line-height:1;letter-spacing:-.06em;color:var(--g-hl)}"
       ".g-s-big-num .g-sl-p{font-size:2.6cqw;color:var(--g-ink);max-width:70%}",
       [T('num', '数字', '12,480'), A('text', '说明', '这一年，有这么多人做出了自己的第一个网页。')]),
    sl('quote', '引用页', "<blockquote class='g-sl-q'>{{quote}}</blockquote><p class='g-sl-who'>{{who}}</p>",
       ".g-sl-q{margin:0;font-size:3.8cqw;line-height:1.4;letter-spacing:-.025em;font-weight:600;max-width:86%;text-wrap:balance}"
       ".g-sl-q:before{content:'“';display:block;font-size:9cqw;line-height:.7;color:var(--g-hl)}.g-sl-who{margin-top:3cqw;font-size:1.8cqw;color:var(--g-mute)}",
       [A('quote', '引用', '好的工具应该安静地待在一边，在你需要的时候刚好出现。'), T('who', '出处', '—— 一位用户的留言')]),
    sl('chart', '柱状图页', "<div class='g-sl-k'>{{kicker}}</div><h2 class='g-sl-h'>{{title}}</h2><div class='g-sl-bars'>{{#items}}<div><b class='g-num'>{{2}}</b><i style='height:{{2}}%'></i><span>{{1}}</span></div>{{/items}}</div>",
       ".g-s-chart .g-sl-h{font-size:3.6cqw}.g-sl-bars{flex:1;display:flex;align-items:flex-end;gap:3cqw;margin-top:3cqw;min-height:0;border-bottom:.15cqw solid var(--g-line)}"
       ".g-sl-bars>div{flex:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;position:relative}"
       ".g-sl-bars i{width:100%;border-radius:1cqw 1cqw 0 0;background:color-mix(in srgb,var(--g-hl) 30%,var(--g-bg))}.g-sl-bars>div:last-child i{background:var(--g-hl)}"
       ".g-sl-bars b{font-size:1.7cqw;margin-bottom:.8cqw}.g-sl-bars span{position:absolute;bottom:-3cqw;font-size:1.5cqw;color:var(--g-mute)}.g-s-chart{padding-bottom:9cqw}",
       [T('kicker', '小标题', '增长'), T('title', '标题', '每季度新用户（百分比）'), L('items', '柱子（一行一个：名称|高度 0 到 100）', '一季度|32\n二季度|48\n三季度|66\n四季度|90')]),
    sl('timeline', '时间线页', "<h2 class='g-sl-h'>{{title}}</h2><div class='g-sl-tl'>{{#items}}<div><b>{{1}}</b><span>{{2}}</span></div>{{/items}}</div>",
       ".g-sl-tl{display:flex;margin-top:6cqw;position:relative}.g-sl-tl:before{content:'';position:absolute;left:0;right:0;top:1cqw;height:.2cqw;background:var(--g-line)}"
       ".g-sl-tl>div{flex:1;position:relative;padding-top:4cqw;padding-right:2cqw}.g-sl-tl>div:before{content:'';position:absolute;left:0;top:0;width:2.2cqw;height:2.2cqw;border-radius:50%;"
       "background:var(--g-bg);border:.45cqw solid var(--g-hl);box-sizing:border-box}.g-sl-tl b{display:block;font-size:2.2cqw}.g-sl-tl span{display:block;font-size:1.6cqw;color:var(--g-mute);margin-top:.6cqw}",
       [T('title', '标题', '一路走来'), L('items', '节点（一行一个：时间|事情）', '2016|开始\n2019|一万个用户\n2023|新办公室\n2026|六百个组件')]),
    sl('compare', '对比页', "<h2 class='g-sl-h'>{{title}}</h2><div class='g-sl-cmp'><div><span>{{a_tag}}</span><ul>{{#a}}<li>{{1}}</li>{{/a}}</ul></div><div><span>{{b_tag}}</span><ul>{{#b}}<li>{{1}}</li>{{/b}}</ul></div></div>",
       ".g-sl-cmp{display:grid;grid-template-columns:1fr 1fr;gap:2.4cqw;margin-top:3.4cqw}.g-sl-cmp>div{border-radius:1.6cqw;padding:3cqw;background:var(--g-soft)}"
       ".g-sl-cmp>div:last-child{background:var(--g-acc);color:var(--g-on)}.g-sl-cmp span{font-size:1.5cqw;font-weight:700;letter-spacing:.06em;opacity:.7}"
       ".g-sl-cmp ul{margin:1.6cqw 0 0;padding-left:2.2cqw;font-size:2cqw;line-height:1.8}",
       [T('title', '标题', '以前和现在'), T('a_tag', '左边标签', '以前'), L('a', '左边（一行一个）', '要写代码\n一页要一周\n改个字要找人'),
        T('b_tag', '右边标签', '现在'), L('b', '右边（一行一个）', '拖一拖就好\n一页三分钟\n想改就改')]),
    sl('cards', '三卡片页', "<h2 class='g-sl-h'>{{title}}</h2><div class='g-sl-cards'>{{#items}}<div><i class='g-i g-i-{{1}}'></i><b>{{2}}</b><span>{{3}}</span></div>{{/items}}</div>",
       ".g-sl-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:2.2cqw;margin-top:4cqw}.g-sl-cards>div{border:.12cqw solid var(--g-line);border-radius:1.6cqw;padding:2.8cqw;background:var(--g-card)}"
       ".g-sl-cards .g-i{width:3.4cqw;height:3.4cqw;color:var(--g-hl)}.g-sl-cards b{display:block;font-size:2.3cqw;margin-top:2cqw}.g-sl-cards span{display:block;font-size:1.6cqw;line-height:1.55;color:var(--g-mute);margin-top:.8cqw}",
       [T('title', '标题', '三个原则'), L('items', f'卡片（一行一个：图标|标题|说明。{ICON_HELP}）', 'bolt|快|打开就能用。\nshield|稳|每一步都能撤销。\nheart|好看|每个细节都调过。')], icons=True),
    sl('agenda', '目录页', "<div class='g-sl-ag'><h2 class='g-sl-h'>{{title}}</h2><ol>{{#items}}<li>{{1}}</li>{{/items}}</ol></div>",
       ".g-sl-ag{display:grid;grid-template-columns:1fr 1.4fr;gap:6cqw;align-items:center}.g-sl-ag ol{list-style:none;margin:0;padding:0;counter-reset:a}"
       ".g-sl-ag li{counter-increment:a;display:flex;gap:2.4cqw;align-items:baseline;font-size:2.4cqw;padding:1.5cqw 0;border-bottom:.12cqw solid var(--g-line)}"
       ".g-sl-ag li:before{content:counter(a,decimal-leading-zero);font-size:1.6cqw;font-weight:700;color:var(--g-hl)}",
       [T('title', '标题', '今天讲四件事'), L('items', '目录（一行一个）', '这一年的数字\n做对了什么\n还没做好的\n明年的计划')]),
    sl('table', '表格页', "<h2 class='g-sl-h'>{{title}}</h2><table class='g-sl-tb'><tr>{{#head}}<th>{{1}}</th>{{/head}}</tr>{{#rows}}<tr><td>{{1}}</td><td>{{2}}</td><td>{{3}}</td></tr>{{/rows}}</table>",
       ".g-sl-tb{width:100%;border-collapse:collapse;margin-top:3.4cqw;font-size:1.9cqw}.g-sl-tb th{text-align:left;font-size:1.5cqw;color:var(--g-mute);font-weight:600;padding:1.2cqw 1.4cqw;border-bottom:.2cqw solid var(--g-ink)}"
       ".g-sl-tb td{padding:1.4cqw;border-bottom:.12cqw solid var(--g-line)}.g-sl-tb td:last-child{font-weight:700;font-variant-numeric:tabular-nums}",
       [T('title', '标题', '三个城市'), L('head', '表头（一行一个，三个）', '城市\n开始时间\n用户'), L('rows', '行（一行一个：第一列|第二列|第三列）', '北京|2016|5,200\n上海|2018|4,100\n深圳|2020|3,180')]),
    sl('team', '团队页', "<h2 class='g-sl-h'>{{title}}</h2><div class='g-sl-team'>{{#items}}<div><img src='{{1}}' alt=''><b>{{2}}</b><span>{{3}}</span></div>{{/items}}</div>",
       ".g-sl-team{display:flex;gap:3cqw;margin-top:4cqw}.g-sl-team>div{flex:1;text-align:center}.g-sl-team img{width:12cqw;height:12cqw;border-radius:50%;object-fit:cover;display:block;margin:0 auto 1.4cqw}"
       ".g-sl-team b{display:block;font-size:2cqw}.g-sl-team span{font-size:1.5cqw;color:var(--g-mute)}",
       [T('title', '标题', '做这件事的人'), L('items', '成员（一行一个：照片|名字|职位）', '@face1|林远|设计\n@face2|陈晓|产品\n@face3|周舟|工程\n@face4|许宁|运营')]),
    sl('steps', '流程页', "<h2 class='g-sl-h'>{{title}}</h2><div class='g-sl-steps'>{{#items}}<div><b>{{1}}</b><span>{{2}}</span></div>{{/items}}</div>",
       ".g-sl-steps{display:flex;gap:1.2cqw;margin-top:4.4cqw}.g-sl-steps>div{flex:1;position:relative;padding:2.6cqw 3.4cqw 2.6cqw 2.6cqw;background:var(--g-soft);"
       "clip-path:polygon(0 0,calc(100% - 2.4cqw) 0,100% 50%,calc(100% - 2.4cqw) 100%,0 100%,2.4cqw 50%)}.g-sl-steps>div:first-child{clip-path:polygon(0 0,calc(100% - 2.4cqw) 0,100% 50%,calc(100% - 2.4cqw) 100%,0 100%)}"
       ".g-sl-steps>div:last-child{background:var(--g-acc);color:var(--g-on)}.g-sl-steps b{display:block;font-size:2.2cqw;padding-left:1.6cqw}.g-sl-steps span{display:block;font-size:1.5cqw;opacity:.75;margin-top:.6cqw;padding-left:1.6cqw}",
       [T('title', '标题', '一个想法怎么变成网页'), L('items', '步骤（一行一个：标题|说明）', '写下来|想说什么\n挑模板|最像的那个\n换内容|你的字和图\n发出去|导出一个文件')]),
    sl('code', '代码页', "<h2 class='g-sl-h'>{{title}}</h2><pre class='g-sl-code'><code>{{code}}</code></pre>",
       ".g-sl-code{margin:3cqw 0 0;padding:3cqw;border-radius:1.6cqw;background:#16171b;color:#e8e8ec;font:1.7cqw/1.7 Consolas,'Cascadia Code',monospace;overflow:hidden;white-space:pre-wrap}",
       [T('title', '标题', '用命令行也能做'), A('code', '代码', 'codepage init 我的网页\ncodepage check 我的网页\ncodepage build 我的网页 --pictures')]),
    sl('end', '结束页', "<h2 class='g-sl-h'>{{title}}</h2><p class='g-sl-p'>{{text}}</p><div class='g-sl-contact'>{{#items}}<span>{{1}}</span>{{/items}}</div>",
       ".g-s-end{text-align:center;align-items:center}.g-s-end .g-sl-h{font-size:7cqw}.g-sl-contact{display:flex;gap:1.4cqw;margin-top:3.6cqw;flex-wrap:wrap;justify-content:center}"
       ".g-sl-contact span{font-size:1.6cqw;padding:.9cqw 1.8cqw;border-radius:99px;border:.12cqw solid var(--g-line);background:var(--g-card)}",
       [T('title', '标题', '谢谢'), A('text', '说明', '有问题，现在就可以问。'), L('items', '联系方式（一行一个）', 'hi@example.com\n小满团队')]),
]
