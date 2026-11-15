"""评价 and 团队: what people say, and who is behind it."""
from parts import FOUR, S, A, L, P, T, head, head_fields

QUOTES = ('@face1|林远|设计师|用了一个下午，就把工作室的网页换掉了。客户都问是谁做的。\n'
          '@face2|陈晓|面包店老板|我不会写代码，也做出了菜单和地图。上线那天订单多了一倍。\n'
          '@face3|周舟|老师|给学生做课程页，拖一拖就好，比做 PPT 还快。')
TEAM = '@face1|林远|设计\n@face2|陈晓|产品\n@face3|周舟|工程\n@face4|许宁|运营'

ITEMS = [
    S('proof-big', '一句大评价', 'proof',
      html="<section class='g g-pf-big%K'><div class='g-wn'><div class='g-stars'>★★★★★</div><blockquote>{{quote}}</blockquote>"
           "<div class='g-pf-who'><img src='{{face}}' alt=''><span><b>{{who}}</b>{{role}}</span></div></div></section>",
      css=".g-pf-big{text-align:center;padding:112px 0}.g-pf-big .g-stars{color:#f5a623;letter-spacing:4px;font-size:20px}"
          ".g-pf-big blockquote{margin:24px 0 36px;font-size:clamp(24px,3.4vw,38px);line-height:1.4;letter-spacing:-.025em;font-weight:600;text-wrap:balance}"
          ".g-pf-who{display:inline-flex;align-items:center;gap:14px;text-align:left}.g-pf-who img{width:52px;height:52px;border-radius:50%;object-fit:cover}"
          ".g-pf-who span{display:flex;flex-direction:column;font-size:14px;color:var(--g-mute)}.g-pf-who b{color:var(--g-ink);font-size:15.5px}",
      fields=[A('quote', '评价', '这是我用过最省心的工具。它不让我做选择，它直接把好看的给我。'), P('face', '头像', '@face4'), T('who', '名字', '许宁'), T('role', '身份', '独立摄影师')]),
    S('proof-three', '三张评价卡', 'proof',
      html="<section class='g g-pf-three%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<figure class='g-card g-pf-c'><blockquote>{{4}}</blockquote>"
           "<figcaption><img src='{{1}}' alt=''><span><b>{{2}}</b>{{3}}</span></figcaption></figure>{{/items}}</div></div></section>",
      css=".g-pf-c{margin:0;display:flex;flex-direction:column;justify-content:space-between;gap:28px}.g-pf-c blockquote{margin:0;font-size:16.5px;line-height:1.7}"
          ".g-pf-c figcaption{display:flex;align-items:center;gap:12px}.g-pf-c img{width:42px;height:42px;border-radius:50%;object-fit:cover}"
          ".g-pf-c span{display:flex;flex-direction:column;font-size:13.5px;color:var(--g-mute)}.g-pf-c b{color:var(--g-ink);font-size:14.5px}",
      fields=head_fields('大家怎么说', '用过的人，都回来了') + [L('items', '评价（一行一个：头像|名字|身份|评价）', QUOTES)]),
    S('proof-photo', '左照片右评价', 'proof', looks=FOUR,
      html="<section class='g g-pf-photo%K'><div class='g-w g-pf-pg'><img class='g-img' src='{{face}}' alt=''><div><blockquote>{{quote}}</blockquote>"
           "<p class='g-pf-pw'><b>{{who}}</b> · {{role}}</p></div></div></section>",
      css=".g-pf-pg{display:grid;grid-template-columns:300px 1fr;gap:64px;align-items:center}.g-pf-pg .g-img{aspect-ratio:4/5}"
          ".g-pf-photo blockquote{margin:0;font-size:clamp(22px,2.8vw,32px);line-height:1.45;letter-spacing:-.02em;font-weight:500}"
          ".g-pf-pw{margin-top:26px;color:var(--g-mute);font-size:15px}.g-pf-pw b{color:var(--g-ink)}"
          "@media(max-width:760px){.g-pf-pg{grid-template-columns:1fr;gap:32px}.g-pf-pg .g-img{max-width:240px}}",
      fields=[A('quote', '评价', '“我原以为要请人做，结果自己一个晚上就弄好了。最惊喜的是手机上也一样好看。”'), P('face', '照片', '@face3'), T('who', '名字', '周舟'), T('role', '身份', '小学老师')]),
    S('proof-wall', '评价墙', 'proof',
      html="<section class='g g-pf-wall%K'><div class='g-w'>" + head() + "<div class='g-pfw'>{{#items}}<figure class='g-card'><blockquote>{{4}}</blockquote>"
           "<figcaption><img src='{{1}}' alt=''><b>{{2}}</b><span>{{3}}</span></figcaption></figure>{{/items}}</div></div></section>",
      css=".g-pfw{columns:3;column-gap:18px}.g-pfw figure{break-inside:avoid;margin:0 0 18px;padding:24px}.g-pfw blockquote{margin:0;font-size:15.5px;line-height:1.7}"
          ".g-pfw figcaption{display:flex;align-items:center;gap:10px;margin-top:18px;font-size:13.5px}.g-pfw img{width:30px;height:30px;border-radius:50%;object-fit:cover}"
          ".g-pfw span{color:var(--g-faint)}@media(max-width:900px){.g-pfw{columns:2}}@media(max-width:600px){.g-pfw{columns:1}}",
      fields=head_fields('留言', '每天都有人写信来') + [L('items', '评价（一行一个：头像|名字|身份|评价）', QUOTES + '\n@face4|许宁|摄影师|作品集终于有了一个像样的家。\n@face1|阿北|学生|毕业设计的展示页就是用它做的，老师夸了。\n@face2|小米|店主|简单，好看，不用操心。')]),
    S('proof-rating', '评分总览', 'proof', looks=FOUR,
      html="<section class='g g-pf-rate%K'><div class='g-w g-split'><div class='g-pf-score'><strong class='g-num'>{{score}}</strong><div class='g-stars'>★★★★★</div><span>{{count}}</span></div>"
           "<div class='g-pf-bars'>{{#bars}}<div><span>{{1}}</span><div class='g-pf-bar'><i style='width:{{2}}%'></i></div><b class='g-num'>{{2}}%</b></div>{{/bars}}</div></div></section>",
      css=".g-pf-rate .g-split{grid-template-columns:auto 1fr;gap:72px}.g-pf-score{text-align:center}.g-pf-score strong{font-size:88px;line-height:1;display:block}"
          ".g-pf-score .g-stars{color:#f5a623;letter-spacing:3px;font-size:20px;margin:10px 0 6px}.g-pf-score span{font-size:14px;color:var(--g-mute)}"
          ".g-pf-bars{display:flex;flex-direction:column;gap:12px}.g-pf-bars>div{display:grid;grid-template-columns:48px 1fr 48px;gap:14px;align-items:center;font-size:14px}"
          ".g-pf-bar{height:8px;border-radius:99px;background:var(--g-soft);overflow:hidden}.g-pf-bar i{display:block;height:100%;background:#f5a623;border-radius:99px}"
          ".g-pf-bars b{font-weight:500;color:var(--g-mute);text-align:right}@media(max-width:760px){.g-pf-rate .g-split{grid-template-columns:1fr;gap:32px}}",
      fields=[T('score', '总分', '4.9'), T('count', '评价人数', '来自 2,318 条评价'), L('bars', '每一档（一行一个：几星|百分比数字）', '5 星|88\n4 星|9\n3 星|2\n2 星|1\n1 星|0')]),
    S('proof-logo-quote', '标志加评价', 'proof',
      html="<section class='g g-pf-lq%K'><div class='g-w'><div class='g-g2'>{{#items}}<figure class='g-card g-pf-lqc'><span class='g-pf-logo'>{{1}}</span><blockquote>{{2}}</blockquote>"
           "<figcaption><b>{{3}}</b> · {{4}}</figcaption></figure>{{/items}}</div></div></section>",
      css=".g-pf-lqc{margin:0;padding:36px}.g-pf-logo{font-size:22px;font-weight:750;letter-spacing:-.04em}.g-pf-lqc blockquote{margin:22px 0;font-size:18px;line-height:1.65}"
          ".g-pf-lqc figcaption{font-size:14px;color:var(--g-mute)}.g-pf-lqc figcaption b{color:var(--g-ink)}",
      fields=[L('items', '评价（一行一个：公司名|评价|名字|职位）', '北风|上线时间从两周缩短到两天，团队终于有时间做真正重要的事。|王川|技术负责人\n青石|每个同事都能改官网了，不用再排队等设计。|李想|市场总监')]),
    S('proof-chat', '聊天气泡', 'proof', looks=FOUR,
      html="<section class='g g-pf-chat%K'><div class='g-wn'>" + head(lead=False) + "<div class='g-pfc'>{{#items}}<div class='g-pfc-m'><img src='{{1}}' alt=''><div><b>{{2}}</b><p>{{3}}</p></div></div>{{/items}}</div></div></section>",
      css=".g-pfc{display:flex;flex-direction:column;gap:18px}.g-pfc-m{display:flex;gap:12px;align-items:flex-end;max-width:560px}"
          ".g-pfc-m:nth-child(even){flex-direction:row-reverse;margin-left:auto;text-align:right}.g-pfc-m img{width:36px;height:36px;border-radius:50%;object-fit:cover}"
          ".g-pfc-m b{font-size:12.5px;color:var(--g-faint);font-weight:500}.g-pfc-m p{margin-top:4px;padding:13px 17px;border-radius:20px 20px 20px 6px;background:var(--g-card);"
          "border:1px solid var(--g-line);font-size:15.5px;line-height:1.6;text-align:left}"
          ".g-pfc-m:nth-child(even) p{border-radius:20px 20px 6px 20px;background:var(--g-acc);color:var(--g-on);border-color:transparent}",
      fields=head_fields('真实的对话', '他们这样跟我们说', with_lead=False) + [L('items', '对话（一行一个：头像|名字|说的话）',
                                                                      '@face2|陈晓|请问可以加一个地图吗？想让客人找得到店。\n@face1|小满团队|可以的，在“其他”里有“地图链接”，拖进来填地址就好。\n@face2|陈晓|好了！太快了，谢谢你们。')]),
    S('team-grid', '团队头像', 'team', looks=FOUR,
      html="<section class='g g-team-grid%K'><div class='g-w'>" + head() + "<div class='g-g4'>{{#items}}<div class='g-tg'><div class='g-tg-pic'><img class='g-img' src='{{1}}' alt=''></div>"
           "<h3 class='g-h3'>{{2}}</h3><span>{{3}}</span></div>{{/items}}</div></div></section>",
      css=".g-tg-pic{aspect-ratio:4/5;margin-bottom:16px;overflow:hidden;border-radius:var(--g-r2)}.g-tg-pic .g-img{transition:transform .5s}.g-tg:hover .g-img{transform:scale(1.04)}"
          ".g-tg .g-h3{font-size:17px}.g-tg span{font-size:14px;color:var(--g-mute)}",
      fields=head_fields('团队', '做这件事的人') + [L('items', '成员（一行一个：照片|名字|职位）', TEAM)]),
    S('team-bio', '团队介绍卡', 'team', looks=FOUR,
      html="<section class='g g-team-bio%K'><div class='g-w'>" + head(center=False) + "<div class='g-g2'>{{#items}}<div class='g-card g-tb'><img src='{{1}}' alt=''><div><h3 class='g-h3'>{{2}}</h3>"
           "<span class='g-tb-r'>{{3}}</span><p class='g-p'>{{4}}</p></div></div>{{/items}}</div></div></section>",
      css=".g-tb{display:flex;gap:22px;align-items:flex-start}.g-tb img{width:84px;height:84px;border-radius:var(--g-r2);object-fit:cover;flex:none}.g-tb-r{font-size:13.5px;color:var(--g-hl);font-weight:600}",
      fields=head_fields('创始人', '我们是谁', with_lead=False) + [L('items', '成员（一行一个：照片|名字|职位|介绍）',
                                                              '@face1|林远|设计|以前在大公司画图标，现在只想做一个好用的工具。\n@face2|陈晓|产品|开过一家面包店，所以知道小店最需要什么。')]),
    S('team-list', '团队名单', 'team', looks=('', 'soft', 'ink'),
      html="<section class='g g-team-list%K'><div class='g-wn'>" + head(center=False, lead=False) + "<div class='g-tl'>{{#items}}<div><img src='{{1}}' alt=''><b>{{2}}</b><span>{{3}}</span><a href='{{4}}'>联系</a></div>{{/items}}</div></div></section>",
      css=".g-tl>div{display:flex;align-items:center;gap:16px;padding:16px 0;border-bottom:1px solid var(--g-line)}.g-tl img{width:44px;height:44px;border-radius:50%;object-fit:cover}"
          ".g-tl b{flex:1;font-weight:600}.g-tl span{color:var(--g-mute);font-size:14.5px;flex:1}.g-tl a{font-size:14px;color:var(--g-hl);text-decoration:none;font-weight:600}",
      fields=head_fields('联系人', '有事找谁', with_lead=False) + [L('items', '成员（一行一个：照片|名字|负责什么|联系链接）',
                                                              '@face1|林远|设计和合作|mailto:hi@example.com\n@face2|陈晓|订单和发票|mailto:hi@example.com\n@face3|周舟|技术问题|mailto:hi@example.com')]),
    S('team-round', '圆形头像', 'team', looks=FOUR,
      html="<section class='g g-team-round%K'><div class='g-w'>" + head() + "<div class='g-tr'>{{#items}}<div><img src='{{1}}' alt=''><b>{{2}}</b><span>{{3}}</span></div>{{/items}}</div></div></section>",
      css=".g-tr{display:flex;flex-wrap:wrap;justify-content:center;gap:40px 48px}.g-tr>div{text-align:center;width:150px}"
          ".g-tr img{width:120px;height:120px;border-radius:50%;object-fit:cover;margin:0 auto 14px;transition:transform .3s}.g-tr>div:hover img{transform:translateY(-4px)}"
          ".g-tr b{display:block;font-size:16px}.g-tr span{font-size:13.5px;color:var(--g-mute)}",
      fields=head_fields('我们', '一个小而认真的团队') + [L('items', '成员（一行一个：照片|名字|职位）', TEAM)]),
]
