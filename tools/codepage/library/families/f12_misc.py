"""图片墙, 标志墙, 提示条, 文字, 按钮."""
from parts import FOUR, THREE, S, A, L, P, T, head, head_fields

PICS = '@forest|山里\n@sea|海边\n@city|老城\n@warm|午后\n@desk|书桌\n@abstract|形状'

ITEMS = [
    S('gal-masonry', '瀑布流', 'media', looks=THREE,
      html="<section class='g g-gal-mas%K'><div class='g-w'>" + head() + "<div class='g-mas'>{{#items}}<figure><img src='{{1}}' alt=''><figcaption>{{2}}</figcaption></figure>{{/items}}</div></div></section>",
      css=".g-mas{columns:3;column-gap:14px}.g-mas figure{margin:0 0 14px;break-inside:avoid;position:relative;border-radius:var(--g-r2);overflow:hidden}"
          ".g-mas img{width:100%;display:block;transition:transform .5s}.g-mas figure:nth-child(3n+1) img{aspect-ratio:3/4;object-fit:cover}.g-mas figure:nth-child(3n+2) img{aspect-ratio:1/1;object-fit:cover}"
          ".g-mas figure:nth-child(3n) img{aspect-ratio:4/3;object-fit:cover}.g-mas figure:hover img{transform:scale(1.04)}"
          ".g-mas figcaption{position:absolute;left:12px;bottom:12px;font-size:13px;font-weight:600;padding:4px 10px;border-radius:99px;background:rgba(255,255,255,.9);color:#111;opacity:0;transform:translateY(6px);transition:.25s}"
          ".g-mas figure:hover figcaption{opacity:1;transform:none}@media(max-width:760px){.g-mas{columns:2}}",
      fields=head_fields('相册', '这一年拍的') + [L('items', '图片（一行一个：图片|说明）', PICS)]),
    S('gal-square', '方格图片', 'media', looks=THREE,
      html="<section class='g g-gal-sq%K'><div class='g-w'>" + head() + "<div class='g-g3 g-sq'>{{#items}}<a href='{{1}}'><img src='{{1}}' alt=''><span>{{2}}</span></a>{{/items}}</div></div></section>",
      css=".g-sq{gap:8px}.g-sq a{position:relative;aspect-ratio:1/1;overflow:hidden;border-radius:var(--g-r);display:block}.g-sq img{width:100%;height:100%;object-fit:cover;transition:transform .5s}"
          ".g-sq a:hover img{transform:scale(1.06)}.g-sq span{position:absolute;inset:0;display:flex;align-items:flex-end;padding:16px;color:#fff;font-weight:600;background:linear-gradient(transparent 50%,rgba(0,0,0,.5));opacity:0;transition:opacity .25s}"
          ".g-sq a:hover span{opacity:1}@media(max-width:640px){.g-sq{grid-template-columns:1fr 1fr}}",
      fields=head_fields('作品', '点开看大图', with_lead=False) + [L('items', '图片（一行一个：图片|说明）', PICS)]),
    S('gal-feature', '一大四小', 'media', looks=THREE,
      html="<section class='g g-gal-ft%K'><div class='g-w'>" + head(center=False, lead=False) + "<div class='g-gft'><img class='g-img' src='{{pic1}}' alt=''><img class='g-img' src='{{pic2}}' alt=''>"
           "<img class='g-img' src='{{pic3}}' alt=''><img class='g-img' src='{{pic4}}' alt=''><img class='g-img' src='{{pic5}}' alt=''></div></div></section>",
      css=".g-gft{display:grid;grid-template-columns:2fr 1fr 1fr;grid-template-rows:220px 220px;gap:12px}.g-gft img:first-child{grid-row:span 2}"
          "@media(max-width:700px){.g-gft{grid-template-columns:1fr 1fr;grid-template-rows:200px 140px 140px}.g-gft img:first-child{grid-column:span 2;grid-row:auto}}",
      fields=head_fields('房间', '看看住的地方', with_lead=False) + [P('pic1', '大图', '@forest'), P('pic2', '小图一', '@warm'), P('pic3', '小图二', '@desk'), P('pic4', '小图三', '@sea'), P('pic5', '小图四', '@city')]),
    S('gal-strip', '横向图片条', 'media', looks=THREE,
      html="<section class='g g-gal-strip%K'><div class='g-w'>" + head(center=False, lead=False) + "</div><div class='g-gs'>{{#items}}<figure><img src='{{1}}' alt=''><figcaption>{{2}}</figcaption></figure>{{/items}}</div></section>",
      css=".g-gs{display:flex;gap:16px;overflow-x:auto;padding:0 max(28px,calc((100% - 1064px)/2)) 8px;scroll-snap-type:x proximity;scrollbar-width:thin}"
          ".g-gs figure{flex:0 0 300px;margin:0;scroll-snap-align:start}.g-gs img{width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:var(--g-r2);display:block}"
          ".g-gs figcaption{font-size:14px;color:var(--g-mute);margin-top:10px}",
      fields=head_fields('往右滑', '更多照片', with_lead=False) + [L('items', '图片（一行一个：图片|说明）', PICS)]),
    S('gal-polaroid', '拍立得', 'media', looks=THREE,
      html="<section class='g g-gal-pol%K'><div class='g-w'>" + head() + "<div class='g-pol'>{{#items}}<figure><img src='{{1}}' alt=''><figcaption>{{2}}</figcaption></figure>{{/items}}</div></div></section>",
      css=".g-pol{display:flex;flex-wrap:wrap;justify-content:center;gap:28px 20px}.g-pol figure{width:220px;margin:0;padding:12px 12px 16px;background:#fff;color:#333;box-shadow:0 10px 30px rgba(0,0,0,.14);"
          "transition:transform .3s}.g-pol figure:nth-child(odd){transform:rotate(-3deg)}.g-pol figure:nth-child(even){transform:rotate(2.5deg)}.g-pol figure:hover{transform:rotate(0) scale(1.05);z-index:1}"
          ".g-pol img{width:100%;aspect-ratio:1/1;object-fit:cover;display:block}.g-pol figcaption{text-align:center;margin-top:12px;font-size:15px}",
      fields=head_fields('那年夏天', '贴在墙上的照片') + [L('items', '照片（一行一个：图片|说明）', '@sea|第一天\n@forest|上山\n@warm|晚饭\n@city|回家')]),
    S('gal-captions', '图片配长说明', 'media', looks=THREE,
      html="<section class='g g-gal-cap%K'><div class='g-w'>" + head(center=False) + "<div class='g-g2 g-gc'>{{#items}}<figure><img class='g-img' src='{{1}}' alt=''><figcaption><b>{{2}}</b><span>{{3}}</span></figcaption></figure>{{/items}}</div></div></section>",
      css=".g-gc{gap:40px 28px}.g-gc figure{margin:0}.g-gc .g-img{aspect-ratio:3/2}.g-gc figcaption{display:flex;flex-direction:column;gap:4px;margin-top:16px}.g-gc b{font-size:17px}"
          ".g-gc span{color:var(--g-mute);font-size:15px}",
      fields=head_fields('项目', '两件我们喜欢的作品') + [L('items', '图片（一行一个：图片|标题|说明）', '@desk|工作室官网|简单的白色，大大的作品图。\n@warm|面包店|暖色调，菜单和地图放在最前面。')]),
    S('logo-row', '一排标志', 'logo', looks=THREE,
      html="<section class='g g-logo-row%K'><div class='g-w'><p class='g-lr-t'>{{title}}</p><div class='g-lr'>{{#items}}<span>{{1}}</span>{{/items}}</div></div></section>",
      css=".g-logo-row{padding:56px 0}.g-lr-t{text-align:center;font-size:14px;color:var(--g-faint)}.g-lr{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:20px 56px;margin-top:24px}"
          ".g-lr span{font-size:22px;font-weight:750;letter-spacing:-.04em;color:var(--g-faint);transition:color .2s}.g-lr span:nth-child(3n){font-style:italic;font-weight:600}"
          ".g-lr span:nth-child(3n+2){letter-spacing:.12em;font-size:16px;text-transform:uppercase}.g-lr span:hover{color:var(--g-ink)}",
      fields=[T('title', '上方小字', '他们都在用'), L('items', '名字（一行一个）', '北风\nNORTH\n青石\n远山\nSUMMIT\n小满')]),
    S('logo-grid', '标志格子', 'logo', looks=THREE,
      html="<section class='g g-logo-grid%K'><div class='g-w'>" + head(lead=False) + "<div class='g-lg'>{{#items}}<span>{{1}}</span>{{/items}}</div></div></section>",
      css=".g-lg{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--g-line);border-radius:var(--g-r2);overflow:hidden}"
          ".g-lg span{display:flex;align-items:center;justify-content:center;height:120px;font-size:21px;font-weight:750;letter-spacing:-.04em;color:var(--g-mute);border-right:1px solid var(--g-line);"
          "border-bottom:1px solid var(--g-line);margin:0 -1px -1px 0;background:var(--g-card);transition:background .2s,color .2s}.g-lg span:hover{background:var(--g-soft);color:var(--g-ink)}"
          "@media(max-width:640px){.g-lg{grid-template-columns:1fr 1fr}}",
      fields=head_fields('合作伙伴', '一起做事的朋友', with_lead=False) + [L('items', '名字（一行一个）', '北风\n青石\n远山\n小满\n知行\n白鹭\n山海\n日出')]),
    S('logo-marquee', '滚动标志', 'logo', looks=THREE,
      html="<section class='g g-logo-mq%K'><p class='g-lmq-t'>{{title}}</p><div class='g-lmq'><div>{{#items}}<span>{{1}}</span>{{/items}}{{#items}}<span aria-hidden='true'>{{1}}</span>{{/items}}</div></div></section>",
      css=".g-logo-mq{padding:56px 0}.g-lmq-t{text-align:center;font-size:14px;color:var(--g-faint);margin-bottom:26px}"
          ".g-lmq{overflow:hidden;-webkit-mask:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent);mask:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)}"
          ".g-lmq>div{display:flex;width:max-content;animation:g-lmq 28s linear infinite}.g-lmq span{font-size:22px;font-weight:750;letter-spacing:-.04em;color:var(--g-faint);padding:0 36px}"
          "@keyframes g-lmq{to{transform:translateX(-50%)}}@media (prefers-reduced-motion:reduce){.g-lmq>div{animation:none}}",
      fields=[T('title', '上方小字', '一千多个团队的选择'), L('items', '名字（一行一个）', '北风\n青石\n远山\n小满\n知行\n白鹭\n山海\n日出')]),
    S('notice-bar', '顶部提示条', 'notice', looks=FOUR,
      html="<div class='g g-nt-bar%K'><div class='g-w g-ntb'><span class='g-tag'>{{tag}}</span><p>{{text}}</p><a href='{{url}}'>{{link}} →</a></div></div>",
      css=".g-nt-bar{padding:12px 0;border-bottom:1px solid var(--g-line)}.g-ntb{display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;font-size:14.5px}"
          ".g-ntb .g-tag{background:var(--g-acc);color:var(--g-on)}.g-ntb a{color:var(--g-ink);font-weight:600;text-decoration:none}",
      fields=[T('tag', '标签', '新'), T('text', '文字', '幻灯片组件来了，可以在网页里放一组 PPT。'), T('link', '链接文字', '看看'), T('url', '链接', '#')]),
    S('notice-info', '信息提示', 'notice', looks=('',),
      html="<div class='g g-nt-msg%K'><div class='g-wn'>{{#items}}<div class='g-ntm g-ntm-{{1}}'><b>{{2}}</b><span>{{3}}</span></div>{{/items}}</div></div>",
      css=".g-nt-msg{padding:32px 0}.g-nt-msg .g-wn{display:flex;flex-direction:column;gap:10px}.g-ntm{display:flex;gap:12px;padding:14px 18px;border-radius:var(--g-r);font-size:15px;border:1px solid;align-items:baseline}"
          ".g-ntm b{flex:none}.g-ntm-info{background:#eef4ff;border-color:#cddcfb;color:#1d3f8a}.g-ntm-ok{background:#ecf8f1;border-color:#c6e9d4;color:#17603a}"
          ".g-ntm-warn{background:#fff7e8;border-color:#f6dfb0;color:#7a4b06}.g-ntm-error{background:#fdeeee;border-color:#f5cccc;color:#8a1f1f}",
      fields=[L('items', '提示（一行一个：种类 info/ok/warn/error|粗体|内容）', 'info|提示：|周末照常营业。\nok|好了：|你的报名已经收到。\nwarn|注意：|活动当天可能下雨，记得带伞。\nerror|抱歉：|这个时间已经约满了。')]),
    S('notice-ribbon', '斜角缎带', 'notice', looks=('', 'ink'),
      html="<div class='g g-nt-rib%K'><div class='g-w'><div class='g-card g-rib'><span class='g-rib-r'>{{ribbon}}</span><h3 class='g-h3'>{{title}}</h3><p class='g-p'>{{text}}</p></div></div></div>",
      css=".g-nt-rib{padding:48px 0}.g-rib{position:relative;overflow:hidden;max-width:620px;margin:0 auto;padding:36px 40px}"
          ".g-rib-r{position:absolute;right:-42px;top:20px;transform:rotate(45deg);background:var(--g-acc);color:var(--g-on);font-size:12.5px;font-weight:700;padding:6px 48px;letter-spacing:.06em}",
      fields=[T('ribbon', '缎带文字', '限时'), T('title', '标题', '这个月报名，送一本手册'), A('text', '说明', '纸质版，寄到家里。')]),
    S('text-display', '一句大标语', 'text', looks=FOUR,
      html="<section class='g g-tx-disp%K'><div class='g-w'><p class='g-txd'>{{text}}</p></div></section>",
      css=".g-txd{font-size:clamp(34px,5.6vw,72px);line-height:1.12;letter-spacing:-.04em;font-weight:700;max-width:1000px;text-wrap:balance}"
          ".g-txd:first-line{color:var(--g-ink)}.g-tx-disp .g-txd{color:var(--g-faint)}",
      fields=[A('text', '标语（第一行会深一些）', '我们相信好的工具应该安静地待在一边，在你需要的时候刚好出现。')]),
    S('text-intro', '左标题右段落', 'text', looks=FOUR,
      html="<section class='g g-tx-intro%K'><div class='g-w g-txi'><div><div class='g-eb'>{{eyebrow}}</div><h2 class='g-h'>{{title}}</h2></div><div>{{#paras}}<p>{{1}}</p>{{/paras}}</div></div></section>",
      css=".g-txi{display:grid;grid-template-columns:1fr 1.2fr;gap:64px}.g-txi p{font-size:17.5px;line-height:1.8;color:var(--g-mute)}.g-txi p+p{margin-top:18px}"
          "@media(max-width:760px){.g-txi{grid-template-columns:1fr;gap:24px}}",
      fields=[T('eyebrow', '小标题', '关于'), T('title', '标题', '一个小而专注的工作室'), L('paras', '段落（一行一段）', '我们只做网页，也只想把网页做好。\n每个项目都从一次长谈开始，直到我们比你还了解你要说的话。')]),
    S('text-highlight', '荧光笔标题', 'text', looks=('', 'soft'),
      html="<section class='g g-tx-hl%K'><div class='g-wn'><h2 class='g-h1'>{{before}}<mark>{{mark}}</mark>{{after}}</h2><p class='g-lead'>{{text}}</p></div></section>",
      css=".g-tx-hl{text-align:center}.g-tx-hl .g-lead{max-width:560px;margin:22px auto 0}"
          ".g-tx-hl mark{color:inherit;background:linear-gradient(transparent 58%,color-mix(in srgb,var(--cp-primary) 30%,transparent) 58%,color-mix(in srgb,var(--cp-primary) 30%,transparent) 92%,transparent 92%);padding:0 .06em}",
      fields=[T('before', '前面的字', '做网页，'), T('mark', '划重点的字', '本来就该简单'), T('after', '后面的字', ''), A('text', '说明', '这是我们做这个工具的唯一理由。')]),
    S('text-numbered', '编号段落', 'text', looks=FOUR,
      html="<section class='g g-tx-num%K'><div class='g-wn'>" + head(center=False, lead=False) + "<ol class='g-txn'>{{#items}}<li><b>{{1}}</b><p>{{2}}</p></li>{{/items}}</ol></div></section>",
      css=".g-txn{list-style:none;padding:0;margin:0;counter-reset:t}.g-txn li{counter-increment:t;display:grid;grid-template-columns:56px 1fr;padding:22px 0;border-top:1px solid var(--g-line)}"
          ".g-txn li:before{content:counter(t,decimal-leading-zero);font-size:14px;font-weight:600;color:var(--g-hl);padding-top:3px;grid-row:span 2}.g-txn b{font-size:17px}"
          ".g-txn p{color:var(--g-mute);margin-top:4px;font-size:15.5px}",
      fields=head_fields('须知', '来之前看一看', with_lead=False) + [L('items', '条目（一行一个：标题|说明）', '准时|迟到十五分钟以上，位置会留给下一位。\n安静|阅览区请不要打电话。\n带走垃圾|我们没有清洁工，大家一起保持。')]),
    S('text-callout', '重点框', 'text', looks=('', 'soft'),
      html="<section class='g g-tx-call%K'><div class='g-wn'><div class='g-txc'><b>{{title}}</b><p>{{text}}</p></div></div></section>",
      css=".g-tx-call{padding:40px 0}.g-txc{border-left:4px solid var(--g-hl);padding:18px 24px;background:var(--g-card);border-radius:0 var(--g-r) var(--g-r) 0;box-shadow:0 1px 0 var(--g-line)}"
          ".g-txc b{display:block;margin-bottom:6px}.g-txc p{color:var(--g-mute);line-height:1.75}",
      fields=[T('title', '标题', '小提示'), A('text', '内容', '按住 Ctrl 再按 D，可以把选中的组件复制一份。')]),
    S('btn-group', '一组按钮', 'button', looks=THREE,
      html="<div class='g g-btn-grp%K'><div class='g-w g-bg'><a class='g-b g-b1' href='{{url1}}'>{{b1}}</a><a class='g-b g-b2' href='{{url2}}'>{{b2}}</a><a class='g-b3' href='{{url3}}'>{{b3}}</a></div></div>",
      css=".g-btn-grp{padding:28px 0}.g-bg{display:flex;align-items:center;gap:14px;flex-wrap:wrap}",
      fields=[T('b1', '主按钮', '开始'), T('url1', '主按钮链接', '#'), T('b2', '次按钮', '看例子'), T('url2', '次按钮链接', '#'), T('b3', '文字链接', '了解更多'), T('url3', '文字链接地址', '#')]),
    S('btn-pill-big', '大胶囊按钮', 'button', looks=THREE,
      html="<div class='g g-btn-pill%K'><div class='g-w' style='text-align:center'><a class='g-bp' href='{{url}}'><span>{{text}}</span><i>→</i></a></div></div>",
      css=".g-btn-pill{padding:36px 0}.g-bp{display:inline-flex;align-items:center;gap:14px;height:64px;padding:0 10px 0 30px;border-radius:99px;background:var(--g-acc);color:var(--g-on);"
          "font-size:18px;font-weight:650;text-decoration:none;transition:transform .2s,box-shadow .2s}.g-bp:hover{transform:translateY(-2px);box-shadow:0 14px 30px color-mix(in srgb,var(--g-acc) 35%,transparent)}"
          ".g-bp i{width:46px;height:46px;border-radius:50%;background:var(--g-on);color:var(--g-acc);display:flex;align-items:center;justify-content:center;font-style:normal;transition:transform .2s}.g-bp:hover i{transform:translateX(3px)}",
      fields=[T('text', '按钮文字', '现在就开始'), T('url', '链接', '#')]),
    S('btn-links', '箭头链接列表', 'button', looks=THREE,
      html="<div class='g g-btn-links%K'><div class='g-wn'>{{#items}}<a class='g-bl' href='{{2}}'><span>{{1}}</span><i>↗</i></a>{{/items}}</div></div>",
      css=".g-btn-links{padding:40px 0}.g-bl{display:flex;justify-content:space-between;align-items:center;padding:20px 4px;border-bottom:1px solid var(--g-line);text-decoration:none;color:var(--g-ink);font-size:clamp(18px,2.2vw,24px);font-weight:600;letter-spacing:-.02em;transition:padding .25s}"
          ".g-bl:first-child{border-top:1px solid var(--g-line)}.g-bl:hover{padding-left:14px}.g-bl i{font-style:normal;color:var(--g-faint);transition:transform .25s,color .25s}.g-bl:hover i{transform:translate(3px,-3px);color:var(--g-hl)}",
      fields=[L('items', '链接（一行一个：文字|地址）', '看作品|#\n读博客|#\n写信给我|mailto:hi@example.com\n下载简历|#')]),
]
