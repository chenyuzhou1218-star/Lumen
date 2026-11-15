"""卡片: rows of things to click, ten ways."""
from kit import ICON_HELP
from parts import FOUR, THREE, S, L, T, head, head_fields

POSTS = ('@city|生活|一个人去旅行，要带什么|整理了十年出门的经验，一张清单就够。|5 分钟|#\n'
         '@forest|自然|周末去山里走走|离城市一小时，就有一片安静的森林。|8 分钟|#\n'
         '@sea|随笔|海边的第七天|不看手机的一周，我学会了等日落。|6 分钟|#')

ITEMS = [
    S('card-posts', '文章卡片', 'card',
      html="<section class='g g-card-posts%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<a class='g-cp' href='{{6}}'><div class='g-cp-pic'><img class='g-img' src='{{1}}' alt=''></div>"
           "<span class='g-tag'>{{2}}</span><h3 class='g-h3'>{{3}}</h3><p class='g-p'>{{4}}</p><span class='g-cp-m'>阅读 {{5}}</span></a>{{/items}}</div></div></section>",
      css=".g-cp{display:block;text-decoration:none;color:inherit}.g-cp-pic{aspect-ratio:16/10;overflow:hidden;border-radius:var(--g-r2);margin-bottom:18px}"
          ".g-cp-pic .g-img{transition:transform .5s cubic-bezier(.2,.7,.2,1)}.g-cp:hover .g-cp-pic .g-img{transform:scale(1.05)}"
          ".g-cp .g-h3{margin-top:12px;transition:color .2s}.g-cp:hover .g-h3{color:var(--g-hl)}.g-cp-m{display:block;margin-top:14px;font-size:13px;color:var(--g-faint)}",
      fields=head_fields('最新文章', '写给想慢一点的人') + [L('items', '文章（一行一个：图片|分类|标题|摘要|阅读时间|链接）', POSTS)]),
    S('card-products', '商品卡片', 'card',
      html="<section class='g g-card-prod%K'><div class='g-w'>" + head(lead=False) + "<div class='g-g4'>{{#items}}<a class='g-cpr' href='{{5}}'><div class='g-cpr-pic'><img src='{{1}}' alt=''>"
           "<span class='g-cpr-tag'>{{4}}</span></div><h3>{{2}}</h3><span class='g-num'>{{3}}</span></a>{{/items}}</div></div></section>",
      css=".g-cpr{display:block;text-decoration:none;color:inherit}.g-cpr-pic{position:relative;aspect-ratio:1/1;border-radius:var(--g-r2);overflow:hidden;background:var(--g-soft)}"
          ".g-cpr-pic img{width:100%;height:100%;object-fit:cover;transition:transform .5s}.g-cpr:hover img{transform:scale(1.05)}"
          ".g-cpr-tag{position:absolute;left:12px;top:12px;font-size:12px;font-weight:600;padding:4px 9px;border-radius:99px;background:var(--g-card);color:var(--g-ink)}"
          ".g-cpr h3{font-size:15.5px;font-weight:600;margin:14px 0 4px;letter-spacing:-.01em}.g-cpr .g-num{font-size:15px;color:var(--g-mute);font-weight:500;letter-spacing:0}",
      fields=head_fields('新品', '这一季的新东西', with_lead=False) + [L('items', '商品（一行一个：图片|名称|价格|角标|链接）',
                                                                     '@product|随身音箱 · 黑|¥ 399|新品|#\n@product|随身音箱 · 灰|¥ 399|新品|#\n@product|旅行款|¥ 299|热卖|#\n@product|桌面款|¥ 499|限量|#')]),
    S('card-profile', '人物卡片', 'card', looks=FOUR,
      html="<section class='g g-card-prof%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<div class='g-card g-lift g-cpf'><img src='{{1}}' alt=''><h3 class='g-h3'>{{2}}</h3>"
           "<span class='g-cpf-r'>{{3}}</span><p class='g-p'>{{4}}</p></div>{{/items}}</div></div></section>",
      css=".g-cpf{text-align:center;padding:36px 28px}.g-cpf img{width:88px;height:88px;border-radius:50%;object-fit:cover;margin:0 auto 18px;box-shadow:0 0 0 5px var(--g-soft)}"
          ".g-cpf-r{display:block;font-size:13.5px;color:var(--g-hl);font-weight:600;margin-top:4px}",
      fields=head_fields('讲者', '这次来分享的人') + [L('items', '人物（一行一个：头像|名字|身份|介绍）',
                                                 '@face1|林远|设计师|做了十年界面，喜欢把复杂的东西拆开讲。\n@face2|陈晓|产品经理|相信好产品是改出来的。\n@face3|周舟|工程师|写代码，也写诗。')]),
    S('card-hlist', '横向列表', 'card', looks=FOUR,
      html="<section class='g g-card-hl%K'><div class='g-wn'>" + head(center=False) + "<div class='g-chl'>{{#items}}<a class='g-chl-i' href='{{5}}'><img src='{{1}}' alt=''>"
           "<div><span class='g-tag'>{{2}}</span><h3 class='g-h3'>{{3}}</h3><p class='g-p'>{{4}}</p></div></a>{{/items}}</div></div></section>",
      css=".g-chl{display:flex;flex-direction:column}.g-chl-i{display:flex;gap:24px;align-items:center;padding:20px 0;border-bottom:1px solid var(--g-line);text-decoration:none;color:inherit}"
          ".g-chl-i:first-child{border-top:1px solid var(--g-line)}.g-chl-i img{width:150px;aspect-ratio:4/3;object-fit:cover;border-radius:var(--g-r);flex:none}"
          ".g-chl .g-h3{margin-top:8px;transition:color .2s}.g-chl-i:hover .g-h3{color:var(--g-hl)}"
          "@media(max-width:560px){.g-chl-i{align-items:flex-start}.g-chl-i img{width:96px}}",
      fields=head_fields('更多', '也许你还想看', with_lead=False) + [L('items', '条目（一行一个：图片|标签|标题|说明|链接）',
                                                               '@city|指南|第一次做网页，从哪里开始|五个步骤，一个下午。|#\n@abstract|技巧|让页面看起来更整齐|对齐、留白、字号，三件事。|#\n@desk|案例|一家面包店的网页|从菜单到地图，只用了九个组件。|#')]),
    S('card-icon-links', '图标链接卡', 'card', icons=True,
      html="<section class='g g-card-il%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<a class='g-card g-lift g-cil' href='{{4}}'><span class='g-ib'><i class='g-i g-i-{{1}}'></i></span>"
           "<h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p><span class='g-cil-go'>→</span></a>{{/items}}</div></div></section>",
      css=".g-cil{display:block;text-decoration:none;color:inherit;position:relative}.g-cil .g-h3{margin-top:20px}"
          ".g-cil-go{position:absolute;right:26px;top:30px;font-size:18px;color:var(--g-faint);transition:transform .2s,color .2s}.g-cil:hover .g-cil-go{transform:translateX(4px);color:var(--g-ink)}",
      fields=head_fields('帮助中心', '你想了解什么？') + [L('items', f'卡片（一行一个：图标|标题|说明|链接。{ICON_HELP}）',
                                                     'rocket|开始使用|从零做出第一页。|#\nbook|使用手册|每个按钮是做什么的。|#\nchat|常见问题|别人也问过的事。|#\ncode|给开发者|命令行和文件格式。|#\nusers|社区|看看别人做了什么。|#\nmail|联系我们|找不到答案就写信。|#')]),
    S('card-overlay', '图上文字卡', 'card', looks=('',),
      html="<section class='g g-card-ov%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<a class='g-cov' href='{{4}}'><img src='{{1}}' alt=''><div><span>{{2}}</span><h3>{{3}}</h3></div></a>{{/items}}</div></div></section>",
      css=".g-cov{position:relative;display:block;aspect-ratio:3/4;border-radius:var(--g-r2);overflow:hidden;color:#fff;text-decoration:none}"
          ".g-cov img{width:100%;height:100%;object-fit:cover;transition:transform .6s cubic-bezier(.2,.7,.2,1)}.g-cov:hover img{transform:scale(1.06)}"
          ".g-cov div{position:absolute;inset:auto 0 0;padding:70px 24px 24px;background:linear-gradient(transparent,rgba(0,0,0,.66))}"
          ".g-cov span{font-size:13px;opacity:.85}.g-cov h3{font-size:22px;letter-spacing:-.02em;margin-top:4px}",
      fields=head_fields('目的地', '这个季节去哪里') + [L('items', '卡片（一行一个：图片|小字|标题|链接）', '@forest|三天两晚|山里的木屋|#\n@sea|五天四晚|安静的海湾|#\n@city|两天一晚|老城散步|#')]),
    S('card-tags', '标签卡片', 'card', looks=FOUR,
      html="<section class='g g-card-tags%K'><div class='g-w'>" + head(center=False) + "<div class='g-g2'>{{#items}}<a class='g-card g-lift g-ctg' href='{{5}}'><div class='g-ctg-top'>"
           "<span class='g-tag'>{{1}}</span><span class='g-tag'>{{2}}</span></div><h3 class='g-h3'>{{3}}</h3><p class='g-p'>{{4}}</p></a>{{/items}}</div></div></section>",
      css=".g-ctg{display:block;text-decoration:none;color:inherit}.g-ctg-top{display:flex;gap:6px;margin-bottom:22px}.g-ctg .g-h3{font-size:21px}",
      fields=head_fields('招聘', '我们在找这些人', with_lead=False) + [L('items', '卡片（一行一个：标签一|标签二|标题|说明|链接）',
                                                                 '设计|全职|界面设计师|和工程师坐在一起，把想法做成好用的东西。|#\n工程|全职|前端工程师|写干净的代码，关心每一毫秒。|#\n运营|兼职|社区运营|陪用户聊天，把他们的话带回来。|#\n工程|实习|测试实习生|找到别人没发现的问题。|#')]),
    S('card-minimal', '纯文字卡', 'card',
      html="<section class='g g-card-min%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<div class='g-cmin'><h3 class='g-h3'>{{1}}</h3><p class='g-p'>{{2}}</p></div>{{/items}}</div></div></section>",
      css=".g-cmin{padding:30px 0 0;border-top:1px solid var(--g-ink)}.g-cmin .g-h3{font-size:20px}.g-cmin .g-p{margin-top:12px}",
      fields=head_fields('我们相信') + [L('items', '卡片（一行一个：标题|说明）', '简单|能一步做完的事，不要两步。\n诚实|做不到的，就说做不到。\n长久|今天做的东西，十年后还能打开。')]),
    S('card-events', '活动日期卡', 'card', looks=FOUR,
      html="<section class='g g-card-ev%K'><div class='g-wn'>" + head(center=False) + "<div class='g-cev'>{{#items}}<a class='g-cev-i' href='{{6}}'><div class='g-cev-d'><b class='g-num'>{{1}}</b><span>{{2}}</span></div>"
           "<div><h3 class='g-h3'>{{3}}</h3><p class='g-p'>{{4}}</p></div><span class='g-b g-b2'>{{5}}</span></a>{{/items}}</div></div></section>",
      css=".g-cev{display:flex;flex-direction:column;gap:12px}.g-cev-i{display:flex;align-items:center;gap:24px;padding:18px 20px 18px 18px;border:1px solid var(--g-line);"
          "border-radius:var(--g-r2);background:var(--g-card);text-decoration:none;color:inherit;transition:border-color .2s,box-shadow .2s}"
          ".g-cev-i:hover{border-color:var(--g-faint);box-shadow:0 10px 26px rgba(0,0,0,.06)}"
          ".g-cev-d{width:64px;height:68px;flex:none;border-radius:var(--g-r);background:var(--g-soft);display:flex;flex-direction:column;align-items:center;justify-content:center}"
          ".g-cev-d b{font-size:26px;line-height:1}.g-cev-d span{font-size:12px;color:var(--g-mute);margin-top:4px}.g-cev-i>div:nth-child(2){flex:1}.g-cev .g-p{margin-top:4px}"
          ".g-cev .g-b{height:38px;padding:0 15px;font-size:14px}@media(max-width:600px){.g-cev .g-b{display:none}}",
      fields=head_fields('近期活动', '一起来玩', with_lead=False) + [L('items', '活动（一行一个：日|月|标题|时间地点|按钮|链接）',
                                                                '12|十一月|周末读书会|下午两点 · 城东书店|报名|#\n19|十一月|手作陶艺|上午十点 · 河边工作室|报名|#\n03|十二月|冬日徒步|早上八点 · 北山入口|报名|#')]),
    S('card-stack-num', '编号卡片', 'card', looks=THREE,
      html="<section class='g g-card-sn%K'><div class='g-w'>" + head() + "<div class='g-g4'>{{#items}}<div class='g-card g-csn'><span class='g-num'>{{1}}</span><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-csn{position:relative;overflow:hidden;padding-top:84px}.g-csn .g-num{position:absolute;top:14px;right:18px;font-size:64px;line-height:1;color:var(--g-soft)}",
      fields=head_fields('四个阶段', '我们怎么陪你走完') + [L('items', '卡片（一行一个：编号|标题|说明）', '01|聊|先听你讲，不急着给方案。\n02|画|把想法画出来，一起改。\n03|做|一周一次给你看进度。\n04|陪|上线以后，有问题随时找。')]),
]
