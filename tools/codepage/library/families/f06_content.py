"""图文: words and pictures side by side, eight ways."""
from parts import FOUR, S, A, L, P, T

ITEMS = [
    S('content-left', '图左文右', 'content', looks=FOUR,
      html="<section class='g g-ct-l%K'><div class='g-w g-split'><div class='g-ct-pic'><img class='g-img' src='{{pic}}' alt=''></div><div><div class='g-eb'>{{eyebrow}}</div>"
           "<h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p><div class='g-acts'><a class='g-b3' href='{{url}}'>{{button}}</a></div></div></div></section>",
      css=".g-ct-l .g-split{grid-template-columns:1fr 1fr}.g-ct-pic{aspect-ratio:4/3.2}",
      fields=[T('eyebrow', '小标题', '我们的故事'), T('title', '标题', '从一间小厨房开始'), A('text', '说明', '十年前，我们在一间六平米的厨房里烤出第一炉面包。现在还是一样的配方，一样的早起。'),
              T('button', '链接文字', '读完整的故事'), T('url', '链接', '#'), P('pic', '图片', '@warm')]),
    S('content-right', '文左图右', 'content', looks=FOUR,
      html="<section class='g g-ct-r%K'><div class='g-w g-split'><div><div class='g-eb'>{{eyebrow}}</div><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p>"
           "<p class='g-p g-ct-more'>{{more}}</p></div><div class='g-ct-pic2'><img class='g-img' src='{{pic}}' alt=''></div></div></section>",
      css=".g-ct-pic2{aspect-ratio:1/1}.g-ct-more{margin-top:16px}",
      fields=[T('eyebrow', '小标题', '怎么做的'), T('title', '标题', '每一样都亲手做'), A('text', '说明', '面粉来自北边的一家磨坊，黄油每周送两次。'),
              A('more', '第二段', '我们不加任何改良剂，所以面包放到第二天会变硬——这是好事。'), P('pic', '图片', '@desk')]),
    S('content-article', '文章正文', 'content', looks=('', 'soft'),
      html="<article class='g g-ct-art%K'><div class='g-wn'><span class='g-tag'>{{tag}}</span><h1 class='g-h'>{{title}}</h1><p class='g-ct-meta'>{{meta}}</p>"
           "<p class='g-ct-intro'>{{intro}}</p><div class='g-ct-body'>{{#paras}}<p>{{1}}</p>{{/paras}}</div></div></article>",
      css=".g-ct-art .g-h{margin-top:18px;font-size:clamp(32px,4.6vw,50px)}.g-ct-meta{font-size:14px;color:var(--g-faint);margin-top:14px}"
          ".g-ct-intro{font-size:21px;line-height:1.6;margin-top:36px;padding-bottom:28px;border-bottom:1px solid var(--g-line);letter-spacing:-.01em}"
          ".g-ct-body p{font-size:17.5px;line-height:1.85;margin-top:22px;color:color-mix(in srgb,var(--g-ink) 86%,var(--g-bg))}",
      fields=[T('tag', '分类', '随笔'), T('title', '标题', '慢一点，也没关系'), T('meta', '作者和日期', '小林 · 2026 年 11 月 · 阅读 6 分钟'),
              A('intro', '导语', '有一阵子我总觉得来不及。后来发现，来不及的事，大多本来就不重要。'),
              L('paras', '正文（一行一段）', '那年秋天我搬到城东，每天走二十分钟去上班。路过一家面包店，一个修鞋摊，还有一棵很老的银杏。\n一开始我边走边看手机。后来手机没电了一次，我才第一次注意到那棵树。\n从那以后我每天都留一点时间，什么也不做，就走路。')]),
    S('content-cols', '两栏文字', 'content', looks=FOUR,
      html="<section class='g g-ct-cols%K'><div class='g-w'><h2 class='g-h g-ct-ch'>{{title}}</h2><div class='g-ct-two'><p>{{left}}</p><p>{{right}}</p></div></div></section>",
      css=".g-ct-ch{max-width:760px}.g-ct-two{columns:2;column-gap:56px;margin-top:40px}.g-ct-two p{font-size:16.5px;line-height:1.8;color:var(--g-mute);margin-bottom:18px;break-inside:avoid}"
          "@media(max-width:700px){.g-ct-two{columns:1}}",
      fields=[T('title', '标题', '我们为什么做这个工具'), A('left', '左边一段', '做网页这件事，本来不该这么难。可是对大多数人来说，打开一个空白的编辑器，就已经不知道从哪里开始了。'),
              A('right', '右边一段', '所以我们准备了几百个做好的部分。你要做的只是挑、拖、改字。剩下的，交给我们。')]),
    S('content-pullquote', '大引用配图', 'content', looks=FOUR,
      html="<section class='g g-ct-pq%K'><div class='g-w g-split'><div class='g-ct-pqp'><img class='g-img' src='{{pic}}' alt=''></div><blockquote><p>{{quote}}</p><footer>{{who}}</footer></blockquote></div></section>",
      css=".g-ct-pqp{aspect-ratio:4/5}.g-ct-pq blockquote{margin:0}.g-ct-pq blockquote p{font-size:clamp(24px,3vw,34px);line-height:1.4;letter-spacing:-.02em;font-weight:600}"
          ".g-ct-pq blockquote p:before{content:'“';display:block;font-size:72px;line-height:.6;color:var(--g-hl);margin-bottom:18px}"
          ".g-ct-pq footer{margin-top:26px;color:var(--g-mute);font-size:15px}",
      fields=[A('quote', '引用', '好的东西不需要很多。它只需要被认真地做出来。'), T('who', '出处', '—— 一位老木匠'), P('pic', '图片', '@forest')]),
    S('content-wide-pic', '大图配说明', 'content', looks=('', 'soft', 'ink'),
      html="<section class='g g-ct-wide%K'><div class='g-w'><figure><div class='g-ct-wp'><img class='g-img' src='{{pic}}' alt=''></div><figcaption><b>{{title}}</b><span>{{text}}</span></figcaption></figure></div></section>",
      css=".g-ct-wide figure{margin:0}.g-ct-wp{aspect-ratio:21/9}.g-ct-wide figcaption{display:flex;justify-content:space-between;gap:32px;margin-top:20px;font-size:15px}"
          ".g-ct-wide figcaption span{color:var(--g-mute);max-width:520px}@media(max-width:640px){.g-ct-wide figcaption{flex-direction:column;gap:6px}.g-ct-wp{aspect-ratio:4/3}}",
      fields=[P('pic', '图片', '@sea'), T('title', '标题', '黄昏，第七天'), A('text', '说明', '拍于南边的一个小渔村。那天的风很大，云走得很快。')]),
    S('content-side-note', '正文加侧栏', 'content', looks=('', 'soft'),
      html="<section class='g g-ct-side%K'><div class='g-w g-ct-sg'><div><h2 class='g-h'>{{title}}</h2>{{#paras}}<p class='g-ct-sp'>{{1}}</p>{{/paras}}</div>"
           "<aside class='g-card'><h3 class='g-h3'>{{side_title}}</h3><ul>{{#side}}<li>{{1}}</li>{{/side}}</ul></aside></div></section>",
      css=".g-ct-sg{display:grid;grid-template-columns:1fr 320px;gap:64px;align-items:start}.g-ct-sp{font-size:17px;line-height:1.8;margin-top:20px;color:color-mix(in srgb,var(--g-ink) 86%,var(--g-bg))}"
          ".g-ct-side aside{position:sticky;top:24px}.g-ct-side ul{margin:14px 0 0;padding-left:18px;color:var(--g-mute);font-size:15px;line-height:1.9}"
          "@media(max-width:860px){.g-ct-sg{grid-template-columns:1fr;gap:36px}}",
      fields=[T('title', '标题', '第一次做网页，需要准备什么'), L('paras', '正文（一行一段）', '其实只需要三样：想说的话、几张图片，和一个下午。\n先把要说的话写在纸上，一段一件事。然后挑一个模板，把话放进去。\n最后换上你自己的图片，导出，完成。'),
              T('side_title', '侧栏标题', '这篇讲了'), L('side', '侧栏要点（一行一个）', '准备文字\n挑模板\n换图片\n导出')]),
    S('content-mosaic', '拼图配文字', 'content', looks=FOUR,
      html="<section class='g g-ct-mos%K'><div class='g-w g-split'><div><div class='g-eb'>{{eyebrow}}</div><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p>"
           "<div class='g-acts'><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div></div><div class='g-ct-m'><img class='g-img' src='{{pic1}}' alt=''><img class='g-img' src='{{pic2}}' alt=''><img class='g-img' src='{{pic3}}' alt=''></div></div></section>",
      css=".g-ct-m{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:14px;aspect-ratio:1/1}.g-ct-m img:first-child{grid-row:span 2}",
      fields=[T('eyebrow', '小标题', '空间'), T('title', '标题', '一个让人想坐下来的地方'), A('text', '说明', '木头桌子、大窗户、安静的角落。带上书，或者什么都不带。'),
              T('button', '按钮', '看看位置'), T('url', '按钮链接', '#'), P('pic1', '图片一', '@desk'), P('pic2', '图片二', '@warm'), P('pic3', '图片三', '@forest')]),
]
