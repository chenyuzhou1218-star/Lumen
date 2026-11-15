"""数字: numbers that make a point, seven ways."""
from parts import FOUR, S, A, L, T, head, head_fields

NUMS = '98%|的人用过之后推荐给朋友\n3 分钟|做好一个像样的页面\n600+|种现成的组件\n24 小时|有问题随时有人回'

ITEMS = [
    S('stat-row', '一排大数字', 'stat',
      html="<section class='g g-stat-row%K'><div class='g-w'><div class='g-sr'>{{#items}}<div><strong class='g-num'>{{1}}</strong><span>{{2}}</span></div>{{/items}}</div></div></section>",
      css=".g-stat-row{padding:72px 0}.g-sr{display:grid;grid-template-columns:repeat(4,1fr)}.g-sr>div{padding:6px 28px;border-left:1px solid var(--g-line)}"
          ".g-sr>div:first-child{border-left:0;padding-left:0}.g-sr strong{display:block;font-size:clamp(34px,4.4vw,52px);line-height:1.08}"
          ".g-sr span{display:block;margin-top:8px;font-size:15px;color:var(--g-mute)}"
          "@media(max-width:800px){.g-sr{grid-template-columns:1fr 1fr;gap:32px 0}.g-sr>div:nth-child(odd){border-left:0;padding-left:0}}",
      fields=[L('items', '数字（一行一个：数字|说明）', NUMS)]),
    S('stat-cards', '数字卡片', 'stat',
      html="<section class='g g-stat-cards%K'><div class='g-w'>" + head() + "<div class='g-g4'>{{#items}}<div class='g-card'><strong class='g-num'>{{1}}</strong><span>{{2}}</span></div>{{/items}}</div></div></section>",
      css=".g-stat-cards .g-card{padding:30px 26px}.g-stat-cards strong{display:block;font-size:clamp(32px,3.4vw,42px);line-height:1.1;color:var(--g-hl)}"
          ".g-stat-cards span{display:block;margin-top:10px;font-size:14.5px;color:var(--g-mute)}",
      fields=head_fields('数字说话', '一年来，我们做到了这些') + [L('items', '数字（一行一个：数字|说明）', NUMS)]),
    S('stat-split', '左字右数', 'stat',
      html="<section class='g g-stat-split%K'><div class='g-w g-split'>" + head(center=False) + "<div class='g-ss'>{{#items}}<div><strong class='g-num'>{{1}}</strong><span>{{2}}</span></div>{{/items}}</div></div></section>",
      css=".g-stat-split .g-head-l{margin:0}.g-ss{display:grid;grid-template-columns:1fr 1fr;gap:44px 36px}"
          ".g-ss>div{border-top:2px solid var(--g-ink);padding-top:18px}.g-ss strong{display:block;font-size:clamp(34px,4vw,48px);line-height:1.08}"
          ".g-ss span{display:block;margin-top:6px;font-size:15px;color:var(--g-mute)}",
      fields=head_fields('关于我们', '从三个人，到一个团队', '十年里我们只做一件事，也只想把这件事做好。') + [L('items', '数字（一行一个：数字|说明）', '2016|在一间小屋里开始\n120|位同事\n31|个城市有我们的用户\n1|个目标：好用')]),
    S('stat-bars', '横条对比', 'stat', looks=FOUR,
      html="<section class='g g-stat-bars%K'><div class='g-wn'>" + head(center=False) + "<div class='g-sb'>{{#items}}<div><div class='g-sb-t'><span>{{1}}</span><b class='g-num'>{{2}}%</b></div>"
           "<div class='g-sb-bar'><i style='width:{{2}}%'></i></div></div>{{/items}}</div></div></section>",
      css=".g-sb{display:flex;flex-direction:column;gap:24px}.g-sb-t{display:flex;justify-content:space-between;font-size:15px;margin-bottom:9px}.g-sb-t b{font-size:15px}"
          ".g-sb-bar{height:10px;border-radius:99px;background:var(--g-soft);overflow:hidden}.g-sb-bar i{display:block;height:100%;border-radius:99px;background:var(--g-hl)}",
      fields=head_fields('调查结果', '大家最在意什么', '我们问了 2,000 位用户，下面是他们的回答。') + [L('items', '横条（一行一个：名称|百分比数字）', '好用|86\n好看|72\n速度|64\n价格|38')]),
    S('stat-rings', '圆环进度', 'stat', looks=FOUR,
      html="<section class='g g-stat-rings%K'><div class='g-w'>" + head() + "<div class='g-g4'>{{#items}}<div class='g-ring'><div class='g-ring-c' style='--p:{{1}}'><b class='g-num'>{{1}}%</b></div>"
           "<h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-ring{text-align:center}.g-ring-c{width:132px;height:132px;margin:0 auto 22px;border-radius:50%;display:flex;align-items:center;justify-content:center;"
          "background:conic-gradient(var(--g-hl) calc(var(--p)*1%),var(--g-soft) 0);position:relative}"
          ".g-ring-c:before{content:'';position:absolute;inset:11px;border-radius:50%;background:var(--g-bg)}.g-ring-c b{position:relative;font-size:28px}"
          ".g-ring .g-h3{font-size:16px}.g-ring .g-p{font-size:14px}",
      fields=head_fields('进度', '今年的目标，完成了多少') + [L('items', '圆环（一行一个：百分比数字|标题|说明）', '92|准时交付|说好的日子，就是那天。\n78|新用户留下来|第一周之后还在用。\n64|问题当天解决|多数不过夜。\n100|数据在本地|没有一条上传。')]),
    S('stat-trend', '带涨跌', 'stat', looks=FOUR,
      html="<section class='g g-stat-trend%K'><div class='g-w'><div class='g-g4'>{{#items}}<div class='g-card'><span class='g-st-l'>{{1}}</span><strong class='g-num'>{{2}}</strong>"
           "<span class='g-st-d'>{{3}}</span></div>{{/items}}</div></div></section>",
      css=".g-stat-trend{padding:64px 0}.g-stat-trend .g-card{padding:22px 24px}.g-st-l{font-size:13.5px;color:var(--g-mute)}"
          ".g-stat-trend strong{display:block;font-size:32px;margin:6px 0 10px;line-height:1.1}"
          ".g-st-d{display:inline-flex;align-items:center;gap:4px;font-size:12.5px;font-weight:600;padding:3px 8px;border-radius:99px;color:#14804a;background:rgba(20,128,74,.1)}"
          ".g-st-d:before{content:'↑'}.g-k-ink .g-st-d,.g-k-brand .g-st-d{color:inherit;background:var(--g-soft)}",
      fields=[L('items', '数字（一行一个：名称|数字|变化）', '访问的人|12,480|比上月多 18%\n留言|326|比上月多 9%\n订阅|1,092|比上月多 24%\n平均停留|3分12秒|比上月多 6%')]),
    S('stat-big-one', '一个大数字', 'stat',
      html="<section class='g g-stat-one%K'><div class='g-w'><strong class='g-num'>{{num}}</strong><p class='g-lead'>{{text}}</p><span class='g-so-src'>{{source}}</span></div></section>",
      css=".g-stat-one{text-align:center;padding:112px 0}.g-stat-one strong{display:block;font-size:clamp(56px,11.5vw,160px);line-height:1;letter-spacing:-.05em;padding:0 .04em;overflow-wrap:anywhere;"
          "background:linear-gradient(180deg,var(--g-ink),color-mix(in srgb,var(--g-ink) 40%,var(--g-bg)));-webkit-background-clip:text;background-clip:text;color:transparent}"
          ".g-stat-one .g-lead{font-size:clamp(19px,2.4vw,24px);color:var(--g-ink);max-width:620px;margin:28px auto 0}.g-so-src{display:block;margin-top:18px;font-size:13px;color:var(--g-faint)}",
      fields=[T('num', '数字', '1,000,000'), A('text', '说明', '这么多页面，是用这个小工具做出来的。'), T('source', '来源', '截至今年十月')]),
]
