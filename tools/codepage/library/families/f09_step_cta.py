"""步骤和时间线, and 号召 (the part that asks people to do something)."""
from parts import FOUR, S, A, L, P, T, head, head_fields

STEPS = '选一个模板|几十个现成的开头，挑一个最像的。\n换成你的话|点哪里改哪里，图片拖进来就换。\n发出去|导出一个文件，放到哪里都能打开。'

ITEMS = [
    S('step-line', '竖向时间线', 'step', looks=FOUR,
      html="<section class='g g-st-line%K'><div class='g-wn'>" + head() + "<ol class='g-tl2'>{{#items}}<li><span class='g-tl2-d'>{{1}}</span><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></li>{{/items}}</ol></div></section>",
      css=".g-tl2{list-style:none;margin:0;padding:0;position:relative}.g-tl2:before{content:'';position:absolute;left:7px;top:8px;bottom:8px;width:2px;background:var(--g-line)}"
          ".g-tl2 li{position:relative;padding:0 0 40px 44px}.g-tl2 li:last-child{padding-bottom:0}"
          ".g-tl2 li:before{content:'';position:absolute;left:0;top:5px;width:16px;height:16px;border-radius:50%;background:var(--g-bg);border:3px solid var(--g-hl);box-sizing:border-box}"
          ".g-tl2-d{font-size:13px;font-weight:600;color:var(--g-hl);letter-spacing:.02em}.g-tl2 .g-h3{margin-top:4px}",
      fields=head_fields('一路走来', '我们的十年') + [L('items', '事件（一行一个：时间|标题|说明）', '2016|在一间小屋里开始|三个人，一台电脑。\n2019|第一万个用户|大多是朋友介绍来的。\n2023|搬进新办公室|终于有了一扇大窗户。\n2026|几百种组件|做网页，变得更简单了。')]),
    S('step-row', '横向步骤', 'step',
      html="<section class='g g-st-row%K'><div class='g-w'>" + head() + "<ol class='g-sr2'>{{#items}}<li><h3 class='g-h3'>{{1}}</h3><p class='g-p'>{{2}}</p></li>{{/items}}</ol></div></section>",
      css=".g-sr2{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:32px;counter-reset:s}"
          ".g-sr2 li{counter-increment:s;position:relative;padding-top:64px}"
          ".g-sr2 li:before{content:counter(s);position:absolute;left:0;top:0;width:42px;height:42px;border-radius:50%;background:var(--g-acc);color:var(--g-on);"
          "display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px}"
          ".g-sr2 li:after{content:'';position:absolute;left:58px;right:-16px;top:21px;height:1px;background:var(--g-line)}.g-sr2 li:last-child:after{display:none}"
          "@media(max-width:760px){.g-sr2{grid-template-columns:1fr}.g-sr2 li:after{display:none}}",
      fields=head_fields('怎么开始', '三步就好') + [L('items', '步骤（一行一个：标题|说明）', STEPS)]),
    S('step-cards', '步骤卡片', 'step', looks=FOUR,
      html="<section class='g g-st-cards%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<div class='g-card g-stc'><span class='g-tag'>第 {{1}} 步</span><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-stc .g-h3{margin-top:18px;font-size:20px}.g-stc{position:relative}",
      fields=head_fields('流程', '从报名到出发') + [L('items', '步骤（一行一个：第几|标题|说明）', '1|填表报名|两分钟，留下名字和电话。\n2|电话确认|我们会在一天内打给你。\n3|收拾行李|清单我们发给你，照着带就行。')]),
    S('step-roadmap', '路线图', 'step', looks=FOUR,
      html="<section class='g g-st-road%K'><div class='g-w'>" + head(center=False) + "<div class='g-g4 g-rm'>{{#items}}<div><span class='g-rm-q'>{{1}}</span><h3 class='g-h3'>{{2}}</h3><ul><li>{{3}}</li><li>{{4}}</li></ul></div>{{/items}}</div></div></section>",
      css=".g-rm>div{border-top:3px solid var(--g-line);padding-top:20px}.g-rm>div:first-child{border-color:var(--g-hl)}.g-rm-q{font-size:13px;font-weight:600;color:var(--g-mute)}"
          ".g-rm .g-h3{margin-top:6px;font-size:17px}.g-rm ul{margin:12px 0 0;padding-left:18px;color:var(--g-mute);font-size:14.5px;line-height:1.9}",
      fields=head_fields('接下来', '今年要做的事', with_lead=False) + [L('items', '阶段（一行一个：时间|标题|要点一|要点二）',
                                                                  '一季度 · 已完成|打好基础|新的编辑器|几百种组件\n二季度 · 进行中|更快|打开更快|手机上编辑\n三季度|一起做|多人编辑|评论\n四季度|更多|更多模板|更多语言')]),
    S('step-changelog', '更新记录', 'step', looks=('', 'soft'),
      html="<section class='g g-st-log%K'><div class='g-wn'>" + head(center=False, lead=False) + "<div class='g-cl'>{{#items}}<div><div class='g-cl-d'><b>{{1}}</b><span>{{2}}</span></div>"
           "<div><h3 class='g-h3'>{{3}}</h3><p class='g-p'>{{4}}</p></div></div>{{/items}}</div></div></section>",
      css=".g-cl>div{display:grid;grid-template-columns:140px 1fr;gap:28px;padding:28px 0;border-top:1px solid var(--g-line)}"
          ".g-cl-d b{display:inline-block;font-size:13px;padding:2px 9px;border-radius:99px;background:var(--g-soft)}.g-cl-d span{display:block;margin-top:8px;font-size:13px;color:var(--g-faint)}"
          "@media(max-width:600px){.g-cl>div{grid-template-columns:1fr;gap:10px}}",
      fields=head_fields('更新', '最近改了什么', with_lead=False) + [L('items', '记录（一行一个：版本|日期|标题|说明）',
                                                                 'v2.4|11 月 8 日|几百种新组件|每一种都有五种样子可以选。\nv2.3|10 月 20 日|幻灯片|在网页里放一组可以翻页的幻灯片。\nv2.2|9 月 30 日|上下拖高度|组件的高度也可以拖了。')]),
    S('cta-banner', '居中号召', 'cta',
      html="<section class='g g-cta-ban%K'><div class='g-wn'><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p><div class='g-acts'><a class='g-b g-b1' href='{{url}}'>{{button}}</a>"
           "<a class='g-b g-b2' href='{{url2}}'>{{button2}}</a></div></div></section>",
      css=".g-cta-ban{text-align:center}.g-cta-ban .g-acts{justify-content:center}.g-cta-ban .g-lead{max-width:540px;margin:18px auto 0}",
      fields=[T('title', '标题', '现在就做你的第一页'), A('text', '说明', '不用注册，打开就能用。做好了随时导出。'), T('button', '按钮', '开始'), T('url', '按钮链接', '#'),
              T('button2', '第二个按钮', '先看看例子'), T('url2', '第二个按钮链接', '#')]),
    S('cta-box', '卡片号召', 'cta', looks=('', 'soft', 'glow'),
      html="<section class='g g-cta-box%K'><div class='g-w'><div class='g-ctb'><div><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p></div>"
           "<a class='g-b' href='{{url}}'>{{button}}</a></div></div></section>",
      css=".g-ctb{display:flex;align-items:center;justify-content:space-between;gap:40px;padding:56px;border-radius:calc(var(--g-r2) + 8px);background:var(--cp-ink);color:var(--cp-bg);"
          "position:relative;overflow:hidden}.g-ctb:after{content:'';position:absolute;right:-80px;top:-120px;width:360px;height:360px;border-radius:50%;"
          "background:radial-gradient(circle,color-mix(in srgb,var(--cp-primary) 55%,transparent),transparent 70%);opacity:.7}"
          ".g-ctb>*{position:relative;z-index:1}.g-ctb .g-lead{color:color-mix(in srgb,var(--cp-bg) 72%,var(--cp-ink));margin-top:12px}"
          ".g-ctb .g-b{background:var(--cp-bg);color:var(--cp-ink);flex:none}@media(max-width:760px){.g-ctb{flex-direction:column;align-items:flex-start;padding:36px}}",
      fields=[T('title', '标题', '准备好了吗？'), A('text', '说明', '把想说的话，放进一个好看的网页里。'), T('button', '按钮', '开始做'), T('url', '按钮链接', '#')]),
    S('cta-email', '订阅号召', 'cta',
      html="<section class='g g-cta-mail%K'><div class='g-w g-split'><div><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p></div>"
           "<form class='g-cm' action='{{url}}' method='post'><input name='email' type='email' required placeholder='{{hint}}' aria-label='{{hint}}'><button class='g-b g-b1' type='submit'>{{button}}</button>"
           "<small>{{note}}</small></form></div></section>",
      css=".g-cm{display:flex;flex-wrap:wrap;gap:10px}.g-cm input{flex:1;min-width:200px;height:50px;padding:0 16px;border:1px solid var(--g-line);border-radius:var(--g-r);"
          "background:var(--g-card);color:var(--g-ink);font:inherit;font-size:15px;outline:none}.g-cm input:focus{border-color:var(--g-hl)}"
          ".g-cm .g-b{height:50px}.g-cm small{flex-basis:100%;font-size:13px;color:var(--g-faint)}",
      fields=[T('title', '标题', '每周一封，好东西'), A('text', '说明', '新组件、新模板，还有别人做的好看的网页。'), T('hint', '输入框提示', '你的邮箱'),
              T('button', '按钮', '订阅'), T('url', '提交到', '#'), T('note', '小字', '随时可以退订。')]),
    S('cta-image', '配图号召', 'cta', looks=FOUR,
      html="<section class='g g-cta-img%K'><div class='g-w'><div class='g-card g-cti'><div class='g-cti-t'><div class='g-eb'>{{eyebrow}}</div><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p>"
           "<div class='g-acts'><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></div><img class='g-img' src='{{pic}}' alt=''></div></div></section>",
      css=".g-cti{display:grid;grid-template-columns:1fr 1fr;padding:0;overflow:hidden}.g-cti-t{padding:56px}.g-cti .g-img{border-radius:0;min-height:320px}"
          "@media(max-width:760px){.g-cti{grid-template-columns:1fr}.g-cti-t{padding:32px}}",
      fields=[T('eyebrow', '小标题', '下一站'), T('title', '标题', '这个周末，去山里'), A('text', '说明', '早上出发，晚上回来。午饭我们准备。'), T('button', '按钮', '报名'),
              T('url', '按钮链接', '#'), P('pic', '图片', '@forest')]),
    S('cta-strip', '一行号召', 'cta', looks=FOUR,
      html="<section class='g g-cta-strip%K'><div class='g-w g-cs'><p><b>{{title}}</b> {{text}}</p><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></section>",
      css=".g-cta-strip{padding:36px 0;border-top:1px solid var(--g-line);border-bottom:1px solid var(--g-line)}.g-cs{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap}"
          ".g-cs p{font-size:18px;color:var(--g-mute)}.g-cs b{color:var(--g-ink)}",
      fields=[T('title', '粗体部分', '还有疑问？'), T('text', '后面的话', '我们很乐意聊聊。'), T('button', '按钮', '约个时间'), T('url', '按钮链接', '#')]),
    S('cta-app', '下载按钮', 'cta', looks=FOUR,
      html="<section class='g g-cta-app%K'><div class='g-wn'><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p><div class='g-ca'>"
           "<a href='{{url1}}'><svg viewBox='0 0 24 24'><path d='M16.4 12.6c0-2.4 2-3.5 2-3.6-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9-.7 0-1.8-.9-3-.8C6.9 7.3 5.5 8.2 4.7 9.6c-1.6 2.8-.4 7 1.2 9.3.8 1.1 1.7 2.4 2.9 2.3 1.2 0 1.6-.7 3-.7s1.8.7 3 .7c1.3 0 2.1-1.1 2.8-2.3.9-1.3 1.3-2.6 1.3-2.6s-2.5-1-2.5-3.7zM14.2 5.6c.6-.8 1.1-1.9 1-2.9-.9 0-2 .6-2.7 1.4-.6.7-1.1 1.8-1 2.8 1 .1 2.1-.5 2.7-1.3z'/></svg><span><small>{{small1}}</small>{{label1}}</span></a>"
           "<a href='{{url2}}'><svg viewBox='0 0 24 24'><path d='M4.5 3.3 13.6 12l-9.1 8.7c-.3-.2-.5-.6-.5-1V4.3c0-.4.2-.8.5-1zm10.3 7.6 2.6-2.5 3 1.7c.8.5.8 1.3 0 1.8l-3 1.7-2.6-2.7zm-1.2 1.1 2.4 2.4-10.7 6.1zm0-2.2L5.2 3.6l10.7 6.1z'/></svg><span><small>{{small2}}</small>{{label2}}</span></a></div></div></section>",
      css=".g-cta-app{text-align:center}.g-cta-app .g-lead{max-width:520px;margin:18px auto 0}.g-ca{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:32px}"
          ".g-ca a{display:flex;align-items:center;gap:10px;height:54px;padding:0 20px 0 16px;border-radius:calc(var(--g-r) + 2px);background:var(--g-acc);color:var(--g-on);text-decoration:none;"
          "transition:transform .18s}.g-ca a:hover{transform:translateY(-2px)}.g-ca svg{width:24px;height:24px;fill:currentColor}"
          ".g-ca span{display:flex;flex-direction:column;text-align:left;font-weight:600;font-size:16px;line-height:1.15}.g-ca small{font-size:11px;font-weight:500;opacity:.75}",
      fields=[T('title', '标题', '装在手机里'), A('text', '说明', '在路上也能改网页，回到电脑前接着做。'), T('small1', '第一个按钮小字', '下载'), T('label1', '第一个按钮', 'iPhone 版'),
              T('url1', '第一个链接', '#'), T('small2', '第二个按钮小字', '下载'), T('label2', '第二个按钮', '安卓版'), T('url2', '第二个链接', '#')]),
    S('cta-split-two', '两个入口', 'cta', looks=FOUR,
      html="<section class='g g-cta-two%K'><div class='g-w g-g2'><a class='g-card g-lift g-c2' href='{{url1}}'><span class='g-tag'>{{tag1}}</span><h3 class='g-h'>{{title1}}</h3><p class='g-p'>{{text1}}</p><span class='g-b3'>{{go1}}</span></a>"
           "<a class='g-card g-lift g-c2' href='{{url2}}'><span class='g-tag'>{{tag2}}</span><h3 class='g-h'>{{title2}}</h3><p class='g-p'>{{text2}}</p><span class='g-b3'>{{go2}}</span></a></div></section>",
      css=".g-c2{display:block;text-decoration:none;color:inherit;padding:40px}.g-c2 .g-h{font-size:clamp(24px,2.8vw,32px);margin-top:18px}.g-c2 .g-b3{margin-top:26px}",
      fields=[T('tag1', '左边标签', '个人'), T('title1', '左边标题', '给自己做一页'), A('text1', '左边说明', '作品、经历、联系方式。'), T('go1', '左边链接字', '开始'), T('url1', '左边链接', '#'),
              T('tag2', '右边标签', '团队'), T('title2', '右边标题', '给团队做官网'), A('text2', '右边说明', '产品、价格、团队、招聘。'), T('go2', '右边链接字', '开始'), T('url2', '右边链接', '#')]),
]
