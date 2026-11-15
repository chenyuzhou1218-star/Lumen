"""首屏: the first thing people see, fourteen ways."""
from parts import FOUR, S, A, L, P, T

BTNS = "<div class='g-acts'><a class='g-b g-b1' href='{{url}}'>{{button}}</a><a class='g-b g-b2' href='{{url2}}'>{{button2}}</a></div>"


def base_fields(title='把想法，变成一个好看的网页', text='拖一拖、改改字，几分钟做出一页能发给别人看的网页。不用写代码，也不用等。',
                badge='新版本', badge_text='几百种组件都能用了', two=True):
    out = []
    if badge is not None:
        out += [T('badge', '徽标', badge), T('badge_text', '徽标旁的话', badge_text)]
    out += [T('title', '大标题', title), A('text', '说明', text), T('button', '按钮', '马上开始'), T('url', '按钮链接', '#')]
    if two:
        out += [T('button2', '第二个按钮', '看看例子'), T('url2', '第二个按钮链接', '#')]
    return out


PILL = "<div class='g-pill'><b>{{badge}}</b>{{badge_text}}</div>"

ITEMS = [
    S('hero-badge', '居中带徽标', 'hero',
      html="<header class='g g-hero-badge%K'><div class='g-wn'>" + PILL + "<h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS + "</div></header>",
      css=".g-hero-badge{text-align:center;padding:136px 0 120px}.g-hero-badge .g-acts{justify-content:center}.g-hero-badge .g-lead{max-width:600px;margin:22px auto 0}",
      fields=base_fields()),
    S('hero-side-pic', '左字右图', 'hero',
      html="<header class='g g-hero-sp%K'><div class='g-w g-split'><div>" + PILL + "<h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS
           + "</div><div class='g-hsp-pic'><img class='g-img' src='{{pic}}' alt=''></div></div></header>",
      css=".g-hero-sp{padding:104px 0}.g-hero-sp .g-h1{font-size:clamp(38px,5.2vw,60px)}.g-hsp-pic{aspect-ratio:5/4.4}"
          ".g-hsp-pic .g-img{box-shadow:0 30px 70px rgba(0,0,0,.14)}",
      fields=base_fields() + [P('pic', '图片', '@desk')]),
    S('hero-pic-left', '左图右字', 'hero',
      html="<header class='g g-hero-pl%K'><div class='g-w g-split'><div class='g-hpl-pic'><img class='g-img' src='{{pic}}' alt=''></div><div>"
           "<div class='g-eb'>{{eyebrow}}</div><h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS + "</div></div></header>",
      css=".g-hero-pl{padding:104px 0}.g-hero-pl .g-split{grid-template-columns:1fr 1.05fr}.g-hero-pl .g-h1{font-size:clamp(36px,5vw,58px)}"
          ".g-hpl-pic{aspect-ratio:1/1;border-radius:50% 50% var(--g-r2) var(--g-r2);overflow:hidden}.g-hpl-pic .g-img{border-radius:0}",
      fields=[T('eyebrow', '小标题', '你好，我是小林')] + base_fields('我做干净、好用的东西', '设计师，也写一点代码。喜欢把复杂的事情讲清楚。', None) + [P('pic', '图片', '@forest')]),
    S('hero-signup', '带邮箱输入', 'hero',
      html="<header class='g g-hero-su%K'><div class='g-wn'>" + PILL + "<h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>"
           "<form class='g-su' action='{{url}}' method='post'><input name='email' type='email' required placeholder='{{hint}}' aria-label='{{hint}}'>"
           "<button class='g-b g-b1' type='submit'>{{button}}</button></form><p class='g-su-note'>{{note}}</p></div></header>",
      css=".g-hero-su{text-align:center;padding:132px 0 116px}.g-hero-su .g-lead{max-width:580px;margin:22px auto 0}"
          ".g-su{display:flex;gap:8px;max-width:460px;margin:34px auto 0;padding:6px;background:var(--g-card);border:1px solid var(--g-line);"
          "border-radius:calc(var(--g-r) + 6px);box-shadow:0 10px 30px rgba(0,0,0,.06)}"
          ".g-su input{flex:1;min-width:0;border:0;background:transparent;font:inherit;font-size:15px;padding:0 12px;color:var(--g-ink);outline:none}"
          ".g-su input::placeholder{color:var(--g-faint)}.g-su .g-b{height:42px}.g-su-note{font-size:13px;color:var(--g-faint);margin-top:14px}"
          "@media(max-width:480px){.g-su{flex-direction:column}.g-su input{height:42px}}",
      fields=base_fields('第一个知道上线的消息', '我们还在做最后的打磨。留个邮箱，上线那天告诉你。', '即将上线', '还差一点点', False)
      + [T('hint', '输入框提示', '你的邮箱'), T('note', '下面的小字', '只发一封，不会打扰你。')]),
    S('hero-stats', '带数字', 'hero',
      html="<header class='g g-hero-st%K'><div class='g-w'><div class='g-hst-top'><h1 class='g-h1'>{{title}}</h1><div><p class='g-lead'>{{text}}</p>" + BTNS
           + "</div></div><div class='g-hst-nums'>{{#stats}}<div><strong class='g-num'>{{1}}</strong><span>{{2}}</span></div>{{/stats}}</div></div></header>",
      css=".g-hero-st{padding:112px 0 88px}.g-hst-top{display:grid;grid-template-columns:1.3fr 1fr;gap:56px;align-items:end}"
          ".g-hst-top .g-lead{margin-top:0}.g-hst-nums{display:grid;grid-template-columns:repeat(4,1fr);margin-top:80px;border-top:1px solid var(--g-line)}"
          ".g-hst-nums>div{padding:28px 24px 0 0}.g-hst-nums strong{display:block;font-size:clamp(30px,3.6vw,44px);line-height:1.1}"
          ".g-hst-nums span{font-size:14px;color:var(--g-mute)}"
          "@media(max-width:860px){.g-hst-top{grid-template-columns:1fr;gap:20px}.g-hst-nums{grid-template-columns:1fr 1fr;margin-top:48px}}",
      fields=base_fields('做网页，本来就该这么简单', '几百种现成的组件，拖进来就是一页。手机上一样好看。', None)
      + [L('stats', '数字（一行一个：数字|说明）', '600+|种组件\n10|套配色\n3 分钟|做好一页\n0|行代码')]),
    S('hero-giant', '超大字', 'hero',
      html="<header class='g g-hero-gi%K'><div class='g-w'><p class='g-hgi-top'><span>{{eyebrow}}</span><span>{{side}}</span></p><h1>{{title}}</h1>"
           "<div class='g-hgi-foot'><p class='g-lead'>{{text}}</p><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></div></header>",
      css=".g-hero-gi{padding:72px 0 88px}.g-hgi-top{display:flex;justify-content:space-between;font-size:14px;color:var(--g-mute);border-bottom:1px solid var(--g-line);padding-bottom:18px}"
          ".g-hero-gi h1{font-size:clamp(56px,13vw,184px);line-height:.92;letter-spacing:-.06em;font-weight:750;margin:56px 0 48px;text-wrap:balance}"
          ".g-hgi-foot{display:flex;justify-content:space-between;align-items:flex-end;gap:32px;flex-wrap:wrap}.g-hgi-foot .g-lead{max-width:460px;margin:0}",
      fields=[T('eyebrow', '左上角', '工作室 · 2026'), T('side', '右上角', '设计 / 网页 / 品牌'), T('title', '大字', '少即是多'),
              A('text', '说明', '我们只做一件事：把你想说的话，放进一个干净的网页里。'), T('button', '按钮', '一起聊聊'), T('url', '按钮链接', '#')]),
    S('hero-cover', '整张背景图', 'hero', looks=('',),
      html="<header class='g g-hero-cv%K' style='--g-cv:url(\"{{pic}}\")'><div class='g-wn'><div class='g-eb'>{{eyebrow}}</div><h1 class='g-h1'>{{title}}</h1>"
           "<p class='g-lead'>{{text}}</p>" + BTNS + "</div></header>",
      css=".g-hero-cv{--g-ink:#fff;--g-mute:rgba(255,255,255,.82);--g-line:rgba(255,255,255,.45);--g-acc:#fff;--g-on:#111;--g-hl:#fff;"
          "background:linear-gradient(180deg,rgba(0,0,0,.18),rgba(0,0,0,.55)),var(--g-cv) center/cover;min-height:620px;display:flex;align-items:flex-end;text-align:left;padding:120px 0 96px}"
          ".g-hero-cv .g-wn{max-width:1120px;width:100%}.g-hero-cv .g-h1{max-width:760px}.g-hero-cv .g-lead{max-width:560px}"
          ".g-hero-cv .g-b2{-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);background:rgba(255,255,255,.12)}",
      fields=[T('eyebrow', '小标题', '夏天去海边')] + base_fields('看一次真正的日落', '三天两晚，住在海边，看潮起潮落。名额不多。', None) + [P('pic', '背景图', '@sea')]),
    S('hero-phone', '手机样机', 'hero',
      html="<header class='g g-hero-ph%K'><div class='g-w g-split'><div>" + PILL + "<h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS
           + "</div><div class='g-hph-wrap'><div class='g-hph'><img src='{{pic}}' alt=''></div><div class='g-hph-card'><strong class='g-num'>{{num}}</strong><span>{{num_text}}</span></div></div></div></header>",
      css=".g-hero-ph{padding:96px 0}.g-hero-ph .g-h1{font-size:clamp(38px,5vw,58px)}.g-hph-wrap{position:relative;display:flex;justify-content:center}"
          ".g-hph{width:min(300px,70vw);aspect-ratio:9/18.5;border-radius:44px;padding:11px;background:#16171b;box-shadow:0 40px 80px rgba(0,0,0,.25),inset 0 0 0 2px #2c2e35}"
          ".g-hph img{width:100%;height:100%;object-fit:cover;border-radius:34px;display:block}"
          ".g-hph-card{position:absolute;left:4%;bottom:14%;background:var(--g-card);border:1px solid var(--g-line);border-radius:var(--g-r2);padding:16px 20px;"
          "box-shadow:0 18px 40px rgba(0,0,0,.12);color:var(--g-ink)}.g-hph-card strong{display:block;font-size:26px;line-height:1.1}.g-hph-card span{font-size:13px;color:var(--g-mute)}",
      fields=base_fields('口袋里的记账本', '每一笔都记得清清楚楚，月底一看就明白钱去哪了。', '手机应用', '现在可以下载') + [P('pic', '手机画面', '@app'), T('num', '浮动卡片数字', '¥ 2,480'), T('num_text', '浮动卡片说明', '这个月省下的')]),
    S('hero-reel', '视频封面', 'hero',
      html="<header class='g g-hero-vd%K'><div class='g-wn'>" + PILL + "<h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS
           + "</div><div class='g-w'><a class='g-hvd' href='{{video}}'><img class='g-img' src='{{pic}}' alt=''><span class='g-hvd-play'></span><span class='g-hvd-t'>{{video_text}}</span></a></div></header>",
      css=".g-hero-vd{text-align:center;padding:120px 0 96px}.g-hero-vd .g-acts{justify-content:center}.g-hero-vd .g-lead{max-width:600px;margin:22px auto 0}"
          ".g-hvd{position:relative;display:block;margin:64px auto 0;max-width:980px;aspect-ratio:16/9;border-radius:var(--g-r2);overflow:hidden;box-shadow:0 30px 70px rgba(0,0,0,.16)}"
          ".g-hvd .g-img{border-radius:0;transition:transform .5s}.g-hvd:hover .g-img{transform:scale(1.03)}"
          ".g-hvd-play{position:absolute;left:50%;top:50%;width:84px;height:84px;margin:-42px 0 0 -42px;border-radius:50%;background:rgba(255,255,255,.92);"
          "box-shadow:0 10px 30px rgba(0,0,0,.2);transition:transform .2s}.g-hvd:hover .g-hvd-play{transform:scale(1.07)}"
          ".g-hvd-play:after{content:'';position:absolute;left:34px;top:27px;border-style:solid;border-width:15px 0 15px 24px;border-color:transparent transparent transparent #111}"
          ".g-hvd-t{position:absolute;left:24px;bottom:20px;color:#fff;font-size:14px;font-weight:600;text-shadow:0 1px 6px rgba(0,0,0,.4)}",
      fields=base_fields('看两分钟，就会用', '从空白页到一个完整的网页，全程录下来了。', '视频', '两分钟上手') + [P('pic', '封面图', '@abstract'), T('video', '视频链接', '#'), T('video_text', '封面上的字', '两分钟上手 · 02:14')]),
    S('hero-logos', '下方带标志', 'hero',
      html="<header class='g g-hero-lg%K'><div class='g-wn'><h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS
           + "</div><div class='g-w'><p class='g-hlg-t'>{{logos_title}}</p><div class='g-hlg'>{{#logos}}<span>{{1}}</span>{{/logos}}</div></div></header>",
      css=".g-hero-lg{text-align:center;padding:128px 0 72px}.g-hero-lg .g-acts{justify-content:center}.g-hero-lg .g-lead{max-width:580px;margin:22px auto 0}"
          ".g-hlg-t{margin-top:96px;font-size:13px;color:var(--g-faint)}.g-hlg{display:flex;flex-wrap:wrap;justify-content:center;gap:16px 52px;margin-top:22px}"
          ".g-hlg span{font-size:21px;font-weight:700;letter-spacing:-.03em;color:var(--g-faint);transition:color .2s}.g-hlg span:hover{color:var(--g-ink)}",
      fields=base_fields('一起做事，更顺手', '任务、文件、消息放在同一个地方，谁在做什么一眼就知道。', None)
      + [T('logos_title', '标志上方的小字', '这些团队已经在用'), L('logos', '标志（一行一个名字）', '北风\n青石\n远山\n小满\n知行\n白鹭')]),
    S('hero-checks', '带对勾', 'hero', looks=FOUR,
      html="<header class='g g-hero-ck%K'><div class='g-w g-split'><div><div class='g-eb'>{{eyebrow}}</div><h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>"
           "<ul class='g-hck'>{{#points}}<li>{{1}}</li>{{/points}}</ul><div class='g-acts'><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></div>"
           "<div class='g-hck-pic'><img class='g-img' src='{{pic}}' alt=''></div></div></header>",
      css=".g-hero-ck{padding:104px 0}.g-hero-ck .g-h1{font-size:clamp(36px,4.8vw,56px)}.g-hck{list-style:none;padding:0;margin:26px 0 0;display:grid;gap:10px}"
          ".g-hck li{position:relative;padding-left:30px;font-size:16px}.g-hck li:before{content:'';position:absolute;left:0;top:3px;width:19px;height:19px;border-radius:50%;"
          "background:color-mix(in srgb,var(--g-hl) 16%,transparent)}.g-hck li:after{content:'';position:absolute;left:6.5px;top:7px;width:4px;height:8px;"
          "border:solid var(--g-hl);border-width:0 2px 2px 0;transform:rotate(45deg)}.g-hck-pic{aspect-ratio:4/4.6}",
      fields=[T('eyebrow', '小标题', '在家也能学')] + base_fields('每天二十分钟，学会做饭', '跟着视频一步一步来，不会的地方随时停下来看。', None, two=False)
      + [L('points', '要点（一行一个）', '一百道家常菜\n每道都有分步视频\n买菜清单自动列好'), P('pic', '图片', '@warm')]),
    S('hero-quote', '带评价', 'hero', looks=FOUR,
      html="<header class='g g-hero-qt%K'><div class='g-w g-split'><div><h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS
           + "</div><figure class='g-card g-hqt'><div class='g-stars'>★★★★★</div><blockquote>{{quote}}</blockquote><figcaption><img src='{{face}}' alt=''><span><b>{{who}}</b>{{role}}</span></figcaption></figure></div></header>",
      css=".g-hero-qt{padding:112px 0}.g-hero-qt .g-h1{font-size:clamp(36px,5vw,58px)}.g-hqt{margin:0;padding:36px;box-shadow:0 24px 60px rgba(0,0,0,.08)}"
          ".g-stars{color:#f5a623;letter-spacing:3px;font-size:18px}.g-hqt blockquote{margin:16px 0 26px;font-size:20px;line-height:1.55;letter-spacing:-.01em}"
          ".g-hqt figcaption{display:flex;align-items:center;gap:14px}.g-hqt img{width:48px;height:48px;border-radius:50%;object-fit:cover}"
          ".g-hqt span{display:flex;flex-direction:column;font-size:14px;color:var(--g-mute)}.g-hqt b{color:var(--g-ink);font-size:15px}",
      fields=base_fields('把时间留给真正重要的事', '自动整理收件箱，只把要你回的信放在最前面。', None)
      + [A('quote', '评价', '用了一个月，每天少看半小时邮件。最重要的信再也没漏过。'), P('face', '头像', '@face2'), T('who', '名字', '陈晓'), T('role', '身份', '产品经理')]),
    S('hero-grid', '网格底纹', 'hero',
      html="<header class='g g-hero-gr g-lines%K'><div class='g-wn'>" + PILL + "<h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS + "</div></header>",
      css=".g-hero-gr{text-align:center;padding:150px 0 140px;background-color:var(--g-bg)}.g-hero-gr .g-acts{justify-content:center}"
          ".g-hero-gr .g-lead{max-width:580px;margin:22px auto 0}"
          ".g-hero-gr:after{content:'';position:absolute;inset:0;z-index:-1;background:radial-gradient(60% 60% at 50% 40%,transparent,var(--g-bg) 92%)}"
          ".g-hero-gr .g-h1 b,.g-hero-gr .g-h1 em{font-style:normal;color:var(--g-hl)}",
      fields=base_fields('给开发者的工具箱', '命令行、接口、文档，一个地方全都有。开源，本地运行。', 'v2.0', '刚刚发布')),
    S('hero-collage', '拼贴卡片', 'hero',
      html="<header class='g g-hero-cl%K'><div class='g-w g-split'><div>" + PILL + "<h1 class='g-h1'>{{title}}</h1><p class='g-lead'>{{text}}</p>" + BTNS
           + "</div><div class='g-hcl'><img class='g-img g-hcl-a' src='{{pic1}}' alt=''><img class='g-img g-hcl-b' src='{{pic2}}' alt=''>"
           "<div class='g-card g-hcl-c'><span class='g-tag'>{{card_tag}}</span><strong>{{card_title}}</strong><div class='g-hcl-bar'><i></i></div></div></div></div></header>",
      css=".g-hero-cl{padding:104px 0}.g-hero-cl .g-h1{font-size:clamp(36px,5vw,58px)}.g-hcl{position:relative;aspect-ratio:1/1}"
          ".g-hcl-a{position:absolute;left:0;top:6%;width:62%;height:62%;box-shadow:0 24px 50px rgba(0,0,0,.14)}"
          ".g-hcl-b{position:absolute;right:0;bottom:4%;width:56%;height:56%;box-shadow:0 24px 50px rgba(0,0,0,.14)}"
          ".g-hcl-c{position:absolute;left:8%;bottom:10%;width:52%;padding:20px;box-shadow:0 18px 40px rgba(0,0,0,.12);display:flex;flex-direction:column;gap:10px}"
          ".g-hcl-c strong{font-size:16px}.g-hcl-bar{height:8px;border-radius:9px;background:var(--g-soft);overflow:hidden}.g-hcl-bar i{display:block;width:68%;height:100%;background:var(--g-hl);border-radius:9px}",
      fields=base_fields('一起去看更大的世界', '路线、住处、当地人才知道的小店，都整理好了。', '旅行', '春天的路线出来了')
      + [P('pic1', '图片一', '@forest'), P('pic2', '图片二', '@sea'), T('card_tag', '卡片标签', '准备中'), T('card_title', '卡片标题', '云南 · 七天')]),
]
