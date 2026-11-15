"""特点: what a product or a service does well, twelve ways."""
from kit import ICON_HELP
from parts import FOUR, S, A, L, P, T, head, head_fields

ICON3 = 'bolt|快|打开就能用，不用等，也不用学。\nshield|稳|每一步都有记录，出了问题能找回来。\nheart|省心|常用的都替你想好了，少点几下。'
ICON4 = ICON3 + '\nglobe|到处能用|电脑、平板、手机，打开浏览器就行。'
ICON6 = ICON4 + '\nchart|看得清|数字一目了然，变化一眼看出。\nusers|一起用|邀请同伴，各自负责各自的部分。'
HELP = f'特点（一行一个：图标|标题|说明。{ICON_HELP}）'

ITEMS = [
    S('feat-icons3', '图标三栏', 'feature', icons=True,
      html="<section class='g g-feat-icons3%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<div class='g-card g-lift'>"
           "<span class='g-ib'><i class='g-i g-i-{{1}}'></i></span><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-feat-icons3 .g-card{padding:30px 28px 32px}.g-feat-icons3 .g-h3{margin-top:22px}",
      fields=head_fields() + [L('items', HELP, ICON3)]),
    S('feat-icons4', '图标四栏', 'feature', icons=True,
      html="<section class='g g-feat-icons4%K'><div class='g-w'>" + head() + "<div class='g-g4'>{{#items}}<div>"
           "<i class='g-i g-i-{{1}}'></i><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-feat-icons4 .g-g4{gap:40px 32px}.g-feat-icons4 .g-i{width:28px;height:28px;color:var(--g-hl)}"
          ".g-feat-icons4 .g-h3{margin-top:18px;font-size:17px}.g-feat-icons4 .g-g4>div{padding-top:22px;border-top:1px solid var(--g-line)}",
      fields=head_fields('能做什么', '四件事，做到最好') + [L('items', HELP, ICON4)]),
    S('feat-six', '六宫格', 'feature', icons=True,
      html="<section class='g g-feat-six%K'><div class='g-w'>" + head() + "<div class='g-six'>{{#items}}<div>"
           "<span class='g-ib'><i class='g-i g-i-{{1}}'></i></span><div><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div></div>{{/items}}</div></div></section>",
      css=".g-six{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--g-line);border-radius:var(--g-r2);overflow:hidden;background:var(--g-card)}"
          ".g-six>div{display:flex;gap:18px;padding:32px 30px;border-right:1px solid var(--g-line);border-bottom:1px solid var(--g-line);margin:0 -1px -1px 0;transition:background .2s}"
          ".g-six>div:hover{background:var(--g-soft)}.g-six .g-ib{width:40px;height:40px}.g-six .g-h3{font-size:17px;margin-top:8px}"
          "@media(max-width:900px){.g-six{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.g-six{grid-template-columns:1fr}}",
      fields=head_fields('全部功能', '你需要的，都在这里') + [L('items', HELP, ICON6)]),
    S('feat-list', '左标题右列表', 'feature', icons=True,
      html="<section class='g g-feat-list%K'><div class='g-w g-split'><div>" + head(center=False)
           + "<a class='g-b g-b1' href='{{url}}'>{{button}}</a></div><div class='g-rows'>{{#items}}<div><span class='g-ib'><i class='g-i g-i-{{1}}'></i></span>"
           "<div><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div></div>{{/items}}</div></div></section>",
      css=".g-feat-list .g-split{align-items:start}.g-feat-list .g-head-l{margin-bottom:28px}"
          ".g-rows>div{display:flex;gap:20px;padding:26px 0;border-bottom:1px solid var(--g-line)}.g-rows>div:first-child{padding-top:4px}"
          ".g-rows .g-h3{margin-top:9px}",
      fields=head_fields('我们怎么做', '每一个细节，都替你想过', '不是功能堆在一起，而是每一步都顺手。') + [T('button', '按钮', '了解更多'), T('url', '按钮链接', '#'), L('items', HELP, ICON4)]),
    S('feat-zigzag', '图文交错', 'feature',
      html="<section class='g g-feat-zigzag%K'><div class='g-w'>" + head() + "<div class='g-zz'>{{#items}}<div class='g-zz-row'>"
           "<div class='g-zz-pic'><img class='g-img' src='{{1}}' alt=''></div><div><span class='g-tag'>{{2}}</span><h3 class='g-h'>{{3}}</h3><p class='g-lead'>{{4}}</p></div></div>{{/items}}</div></div></section>",
      css=".g-zz{display:flex;flex-direction:column;gap:88px}.g-zz-row{display:grid;grid-template-columns:1fr 1fr;gap:64px;align-items:center}"
          ".g-zz-row:nth-child(even) .g-zz-pic{order:2}.g-zz-pic{aspect-ratio:4/3}.g-zz .g-h{font-size:clamp(24px,3vw,34px);margin-top:16px}"
          "@media(max-width:800px){.g-zz{gap:56px}.g-zz-row{grid-template-columns:1fr;gap:28px}.g-zz-row:nth-child(even) .g-zz-pic{order:0}}",
      fields=head_fields('一步一步', '从想法到上线') + [L('items', '每一段（一行一个：图片|标签|标题|说明）',
                                                 '@desk|第一步|先把想法写下来|用最少的话讲清楚要做什么、给谁用。\n@abstract|第二步|拖出页面的样子|组件拖进来，改文字、换图片，马上看到效果。\n@city|第三步|发出去给大家看|导出一个文件，放到哪里都能打开。')]),
    S('feat-bento', '拼贴格', 'feature', icons=True,
      html="<section class='g g-feat-bento%K'><div class='g-w'>" + head() + "<div class='g-bento'>"
           "<div class='g-card g-bt-a'><h3 class='g-h3'>{{a_title}}</h3><p class='g-p'>{{a_text}}</p><img class='g-img' src='{{a_pic}}' alt=''></div>"
           "<div class='g-card g-bt-b'><span class='g-num'>{{b_num}}</span><p class='g-p'>{{b_text}}</p></div>"
           "<div class='g-card g-bt-c'><span class='g-ib'><i class='g-i g-i-{{c_icon}}'></i></span><h3 class='g-h3'>{{c_title}}</h3><p class='g-p'>{{c_text}}</p></div>"
           "<div class='g-card g-bt-d'><h3 class='g-h3'>{{d_title}}</h3><p class='g-p'>{{d_text}}</p><div class='g-bars'><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></div>"
           "</div></div></section>",
      css=".g-bento{display:grid;grid-template-columns:1.4fr 1fr 1fr;grid-template-rows:auto auto;gap:18px}"
          ".g-bt-a{grid-row:span 2;display:flex;flex-direction:column}.g-bt-a .g-img{margin-top:26px;flex:1;min-height:200px}"
          ".g-bt-b{display:flex;flex-direction:column;justify-content:flex-end;background:var(--g-acc);color:var(--g-on);border-color:transparent}"
          ".g-bt-b .g-num{font-size:clamp(44px,5vw,64px);line-height:1}.g-bt-b .g-p{color:inherit;opacity:.78}"
          ".g-bt-c .g-h3{margin-top:20px}.g-bt-d{grid-column:span 2}"
          ".g-bars{display:flex;align-items:flex-end;gap:10px;height:84px;margin-top:22px}"
          ".g-bars i{flex:1;border-radius:6px 6px 2px 2px;background:var(--g-soft)}.g-bars i:nth-child(1){height:34%}.g-bars i:nth-child(2){height:52%}"
          ".g-bars i:nth-child(3){height:44%}.g-bars i:nth-child(4){height:70%}.g-bars i:nth-child(5){height:62%}.g-bars i:nth-child(6){height:84%}"
          ".g-bars i:nth-child(7){height:100%;background:var(--g-hl)}"
          "@media(max-width:900px){.g-bento{grid-template-columns:1fr 1fr}.g-bt-a{grid-column:span 2;grid-row:auto}.g-bt-d{grid-column:span 2}}"
          "@media(max-width:640px){.g-bento{grid-template-columns:1fr}.g-bt-a,.g-bt-d{grid-column:auto}}",
      fields=head_fields('一眼看完', '重要的，都放在这一页') + [
          T('a_title', '大格标题', '所见即所得'), A('a_text', '大格说明', '拖一下就放好，改一个字马上就变。'), P('a_pic', '大格图片', '@desk'),
          T('b_num', '数字格数字', '3 分钟'), T('b_text', '数字格说明', '做好一个像样的页面'),
          T('c_icon', '图标格图标', 'shield'), T('c_title', '图标格标题', '不会丢'), A('c_text', '图标格说明', '每一步都能撤销，随时回到之前。'),
          T('d_title', '长格标题', '越用越快'), A('d_text', '长格说明', '常用的组件和配色，会排在你手边。')]),
    S('feat-numbered', '编号要点', 'feature',
      html="<section class='g g-feat-num%K'><div class='g-w'>" + head(center=False) + "<ol class='g-nlist'>{{#items}}<li><h3 class='g-h3'>{{1}}</h3><p class='g-p'>{{2}}</p></li>{{/items}}</ol></div></section>",
      css=".g-nlist{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:48px 40px;counter-reset:n}"
          ".g-nlist li{counter-increment:n;position:relative;padding-top:62px}"
          ".g-nlist li:before{content:counter(n,decimal-leading-zero);position:absolute;top:0;left:0;font-size:40px;font-weight:700;letter-spacing:-.04em;"
          "color:transparent;-webkit-text-stroke:1.3px var(--g-faint);line-height:1}"
          "@media(max-width:900px){.g-nlist{grid-template-columns:1fr 1fr}}@media(max-width:640px){.g-nlist{grid-template-columns:1fr;gap:36px}}",
      fields=head_fields('原则', '我们坚持的六件事', '少一点花样，多一点用心。') + [L('items', '要点（一行一个：标题|说明）',
                                                                        '说人话|界面上的每一个字，都让人一看就懂。\n不打扰|不弹窗，不催促，不在你忙的时候出声。\n能撤销|任何一步做错了，都能退回去。\n不收集|你的东西只在你的电脑上。\n快|打开就能用，点了马上有反应。\n好看|留白、对齐、字号，都认真调过。')]),
    S('feat-circles', '圆形图标居中', 'feature', icons=True,
      html="<section class='g g-feat-circ%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<div class='g-circ'><span><i class='g-i g-i-{{1}}'></i></span>"
           "<h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-circ{text-align:center;padding:8px 18px}.g-circ>span{display:inline-flex;align-items:center;justify-content:center;width:76px;height:76px;border-radius:50%;"
          "background:var(--g-card);border:1px solid var(--g-line);color:var(--g-hl);box-shadow:0 10px 26px rgba(0,0,0,.06);margin-bottom:24px}"
          ".g-circ .g-i{width:28px;height:28px}.g-circ .g-p{max-width:300px;margin-left:auto;margin-right:auto}",
      fields=head_fields('我们的承诺') + [L('items', HELP, ICON3)]),
    S('feat-cards-pic', '带图卡片', 'feature',
      html="<section class='g g-feat-pic%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<a class='g-card g-lift' href='{{4}}'>"
           "<div class='g-fp-pic'><img class='g-img' src='{{1}}' alt=''></div><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p><span class='g-b3'>看看</span></a>{{/items}}</div></div></section>",
      css=".g-feat-pic .g-card{padding:10px 10px 26px;text-decoration:none;color:inherit;display:block}"
          ".g-fp-pic{aspect-ratio:16/10;margin-bottom:22px}.g-fp-pic .g-img{border-radius:calc(var(--g-r2) - 4px)}"
          ".g-feat-pic .g-h3,.g-feat-pic .g-p,.g-feat-pic .g-b3{margin-left:16px;margin-right:16px}.g-feat-pic .g-b3{margin-top:18px;font-size:14px}",
      fields=head_fields('三种用法', '挑一个，马上开始') + [L('items', '卡片（一行一个：图片|标题|说明|链接）',
                                                   '@city|给公司|介绍、团队、联系方式，一页说清。|#\n@forest|给活动|时间、地点、报名，一目了然。|#\n@sea|给自己|作品、经历、想说的话。|#')]),
    S('feat-checks', '对勾清单', 'feature', looks=FOUR,
      html="<section class='g g-feat-checks%K'><div class='g-w g-split'>" + head(center=False) + "<ul class='g-checks'>{{#items}}<li>{{1}}</li>{{/items}}</ul></div></section>",
      css=".g-checks{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:16px 28px}"
          ".g-checks li{position:relative;padding-left:34px;font-size:16px;line-height:1.5}"
          ".g-checks li:before{content:'';position:absolute;left:0;top:1px;width:22px;height:22px;border-radius:50%;background:var(--g-acc)}"
          ".g-checks li:after{content:'';position:absolute;left:7.5px;top:6px;width:5px;height:10px;border:solid var(--g-on);border-width:0 2px 2px 0;transform:rotate(45deg)}"
          ".g-feat-checks .g-head-l{margin:0}@media(max-width:640px){.g-checks{grid-template-columns:1fr}}",
      fields=head_fields('都包括', '一次装好，全都有', '不用一个一个去找，下面这些打开就有。') + [L('items', '清单（一行一个）',
                                                                              '几百种组件\n十套配色\n手机上也好看\n一键导出网页\n随时撤销\n不用联网\n能交给 AI 改\n文件都在自己手里')]),
    S('feat-showcase', '大图配要点', 'feature', icons=True,
      html="<section class='g g-feat-show%K'><div class='g-w'>" + head() + "<div class='g-frame g-show-pic'><img class='g-img' src='{{pic}}' alt=''></div>"
           "<div class='g-g3 g-show-pts'>{{#items}}<div><i class='g-i g-i-{{1}}'></i><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-show-pic{aspect-ratio:16/8;max-width:980px;margin:0 auto}.g-show-pic .g-img{border-radius:var(--g-r2)}"
          ".g-show-pts{margin-top:64px;gap:36px}.g-show-pts .g-i{color:var(--g-hl);width:24px;height:24px}.g-show-pts .g-h3{margin-top:14px;font-size:17px}",
      fields=head_fields('全新', '一个窗口，做完一整页') + [P('pic', '大图', '@desk'), L('items', HELP, ICON3)]),
    S('feat-tabs', '左侧切换', 'feature', icons=True,
      html="<section class='g g-feat-tabs%K'><div class='g-w g-split'><div>" + head(center=False) + "<div class='g-tlist'>{{#items}}<div>"
           "<i class='g-i g-i-{{1}}'></i><div><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div></div>{{/items}}</div></div>"
           "<div class='g-frame g-tabs-pic'><img class='g-img' src='{{pic}}' alt=''></div></div></section>",
      css=".g-feat-tabs .g-head-l{margin-bottom:26px}.g-tlist{display:flex;flex-direction:column;gap:6px}"
          ".g-tlist>div{display:flex;gap:16px;padding:18px 20px;border-radius:var(--g-r2);border:1px solid transparent;transition:background .2s,border-color .2s}"
          ".g-tlist>div:first-child,.g-tlist>div:hover{background:var(--g-card);border-color:var(--g-line);box-shadow:0 8px 22px rgba(0,0,0,.05)}"
          ".g-tlist .g-i{color:var(--g-hl);margin-top:1px}.g-tlist .g-h3{font-size:16px}.g-tlist .g-p{margin-top:4px;font-size:14.5px}"
          ".g-tabs-pic{aspect-ratio:4/3.4}",
      fields=head_fields('怎么用', '三步，做好一页', '跟着做一遍，下次就熟了。') + [P('pic', '图片', '@abstract'), L('items', HELP, ICON3)]),
]
