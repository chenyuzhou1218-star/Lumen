"""互动: things that move or answer a click. Each works without script in the builder and comes alive in the page."""
from parts import THREE, S, A, L, P, T, head, head_fields

TABS_JS = ("document.querySelectorAll('.g-tabs').forEach(function(t){var b=t.querySelectorAll('.g-tab-b button'),p=t.querySelectorAll('.g-tab-p>div');"
           "t.classList.add('g-js');function go(i){b.forEach(function(x,j){x.classList.toggle('on',i==j)});p.forEach(function(x,j){x.classList.toggle('on',i==j)})}"
           "b.forEach(function(x,i){x.addEventListener('click',function(){go(i)})});go(0)});")
SLIDE_JS = ("document.querySelectorAll('.g-car').forEach(function(c){var r=c.querySelector('.g-car-r');c.querySelectorAll('[data-go]').forEach(function(b){"
            "b.addEventListener('click',function(){r.scrollBy({left:(b.dataset.go=='1'?1:-1)*r.clientWidth*.8,behavior:'smooth'})})})});")
COMPARE_JS = ("document.querySelectorAll('.g-cmp').forEach(function(c){var i=c.querySelector('input');function s(){c.style.setProperty('--x',i.value+'%')}"
              "i.addEventListener('input',s);s()});")
COUNT_JS = ("(function(){var n=document.querySelectorAll('.g-cnt [data-to]');if(!('IntersectionObserver' in window))return;"
            "var io=new IntersectionObserver(function(es){es.forEach(function(e){if(!e.isIntersecting)return;io.unobserve(e.target);var el=e.target,"
            "to=parseFloat(el.dataset.to)||0,t0=performance.now();function f(t){var k=Math.min(1,(t-t0)/1400);k=1-Math.pow(1-k,3);"
            "el.textContent=Math.round(to*k).toLocaleString();if(k<1)requestAnimationFrame(f)}requestAnimationFrame(f)})},{threshold:.4});"
            "n.forEach(function(e){e.textContent='0';io.observe(e)})})();")
GLOW_JS = ("document.querySelectorAll('.g-glow-c').forEach(function(c){c.addEventListener('pointermove',function(e){var r=c.getBoundingClientRect();"
           "c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')})});")

ITEMS = [
    S('play-tabs', '标签切换', 'play', looks=THREE, js=TABS_JS,
      html="<section class='g g-play-tabs%K'><div class='g-w'>" + head() + "<div class='g-tabs'><div class='g-tab-b'>{{#items}}<button type='button'>{{1}}</button>{{/items}}</div>"
           "<div class='g-tab-p'>{{#items}}<div class='g-card'><img class='g-img' src='{{3}}' alt=''><div><h3 class='g-h'>{{1}}</h3><p class='g-lead'>{{2}}</p></div></div>{{/items}}</div></div></div></section>",
      css=".g-tab-b{display:flex;gap:4px;justify-content:center;flex-wrap:wrap;padding:4px;border-radius:99px;background:var(--g-soft);width:max-content;max-width:100%;margin:0 auto 32px}"
          ".g-tab-b button{font:inherit;font-size:14.5px;font-weight:600;border:0;background:transparent;color:var(--g-mute);padding:9px 18px;border-radius:99px;cursor:pointer;transition:background .2s,color .2s}"
          ".g-tabs:not(.g-js) .g-tab-b button:first-child,.g-js .g-tab-b button.on{background:var(--g-card);color:var(--g-ink);box-shadow:0 1px 4px rgba(0,0,0,.1)}"
          ".g-tab-p>div{display:none;grid-template-columns:1.1fr 1fr;gap:48px;align-items:center;padding:20px}"
          ".g-tabs:not(.g-js) .g-tab-p>div:first-child,.g-js .g-tab-p>div.on{display:grid}.g-js .g-tab-p>div.on{animation:g-fade .4s}.g-tab-p .g-img{aspect-ratio:4/3}"
          ".g-tab-p .g-h{font-size:clamp(24px,3vw,32px)}@keyframes g-fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}"
          "@media(max-width:760px){.g-tab-p>div,.g-js .g-tab-p>div.on{grid-template-columns:1fr;gap:20px}}",
      fields=head_fields('看一看', '不同的人，不同的用法') + [L('items', '标签（一行一个：标题|说明|图片）',
                                                       '小店|菜单、地图、营业时间，一页放下。|@warm\n活动|时间地点和报名，转发出去就行。|@forest\n个人|作品、经历和联系方式。|@desk')]),
    S('play-carousel', '左右滑动', 'play', looks=THREE, js=SLIDE_JS,
      html="<section class='g g-play-car%K'><div class='g-w g-car'><div class='g-car-h'>" + head(center=False, lead=False) + "<div class='g-car-n'><button type='button' data-go='-1' aria-label='上一张'>←</button>"
           "<button type='button' data-go='1' aria-label='下一张'>→</button></div></div><div class='g-car-r'>{{#items}}<figure><img class='g-img' src='{{1}}' alt=''><figcaption><b>{{2}}</b>{{3}}</figcaption></figure>{{/items}}</div></div></section>",
      css=".g-car-h{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:32px}.g-car-h .g-head-l{margin:0}"
          ".g-car-n{display:flex;gap:8px}.g-car-n button{width:44px;height:44px;border-radius:50%;border:1px solid var(--g-line);background:var(--g-card);color:var(--g-ink);font-size:17px;cursor:pointer;transition:border-color .15s}"
          ".g-car-n button:hover{border-color:var(--g-faint)}.g-car-r{display:flex;gap:18px;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;padding-bottom:6px}"
          ".g-car-r::-webkit-scrollbar{display:none}.g-car-r figure{flex:0 0 min(380px,80%);margin:0;scroll-snap-align:start}.g-car-r .g-img{aspect-ratio:4/5}"
          ".g-car-r figcaption{display:flex;flex-direction:column;margin-top:14px;font-size:14px;color:var(--g-mute)}.g-car-r figcaption b{font-size:16px;color:var(--g-ink)}",
      fields=head_fields('作品', '最近做的几件东西', with_lead=False) + [L('items', '卡片（一行一个：图片|标题|说明）',
                                                                    '@forest|山中小屋|民宿的网页\n@sea|海边|旅行社的活动页\n@city|老城|城市导览\n@warm|面包店|菜单和地图\n@desk|工作室|设计师主页')]),
    S('play-marquee', '滚动文字带', 'play', looks=THREE,
      html="<section class='g g-play-mq%K'><div class='g-mq'><div>{{#items}}<span>{{1}}</span>{{/items}}{{#items}}<span aria-hidden='true'>{{1}}</span>{{/items}}</div></div></section>",
      css=".g-play-mq{padding:40px 0;overflow:hidden;border-top:1px solid var(--g-line);border-bottom:1px solid var(--g-line)}.g-mq{overflow:hidden;-webkit-mask:linear-gradient(90deg,transparent,#000 10%,#000 90%,transparent);mask:linear-gradient(90deg,transparent,#000 10%,#000 90%,transparent)}"
          ".g-mq>div{display:flex;width:max-content;animation:g-mq 30s linear infinite}.g-mq:hover>div{animation-play-state:paused}"
          ".g-mq span{font-size:clamp(28px,4vw,44px);font-weight:700;letter-spacing:-.03em;padding:0 32px;white-space:nowrap}.g-mq span:nth-child(even){color:transparent;-webkit-text-stroke:1.2px var(--g-ink)}"
          "@keyframes g-mq{to{transform:translateX(-50%)}}@media (prefers-reduced-motion:reduce){.g-mq>div{animation:none}}",
      fields=[L('items', '文字（一行一个）', '设计\n网页\n品牌\n插画\n动画\n文案')]),
    S('play-compare', '前后对比', 'play', looks=THREE, js=COMPARE_JS,
      html="<section class='g g-play-cmp%K'><div class='g-w'>" + head() + "<div class='g-cmp' style='--x:50%'><img class='g-cmp-a' src='{{after}}' alt=''><div class='g-cmp-b'><img src='{{before}}' alt=''></div>"
           "<span class='g-cmp-l'>{{before_label}}</span><span class='g-cmp-r'>{{after_label}}</span><input type='range' min='0' max='100' value='50' aria-label='拖动对比'><i></i></div></div></section>",
      css=".g-cmp{position:relative;max-width:900px;margin:0 auto;aspect-ratio:16/9;border-radius:var(--g-r2);overflow:hidden;user-select:none}"
          ".g-cmp img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.g-cmp-b{position:absolute;inset:0;clip-path:inset(0 calc(100% - var(--x)) 0 0)}"
          ".g-cmp-b img{filter:grayscale(1) contrast(.9)}.g-cmp input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:ew-resize;margin:0}"
          ".g-cmp i{position:absolute;top:0;bottom:0;left:var(--x);width:3px;margin-left:-1.5px;background:#fff;pointer-events:none;box-shadow:0 0 12px rgba(0,0,0,.3)}"
          ".g-cmp i:after{content:'↔';position:absolute;left:50%;top:50%;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;background:#fff;color:#111;display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 4px 14px rgba(0,0,0,.25)}"
          ".g-cmp span{position:absolute;top:14px;font-size:12.5px;font-weight:600;padding:4px 10px;border-radius:99px;background:rgba(0,0,0,.5);color:#fff;pointer-events:none}.g-cmp-l{left:14px}.g-cmp-r{right:14px}",
      fields=head_fields('改了什么', '拖一拖，看看前后') + [P('before', '之前的图', '@city'), P('after', '之后的图', '@sea'), T('before_label', '之前的标签', '之前'), T('after_label', '之后的标签', '之后')]),
    S('play-counter', '数字滚动', 'play', looks=THREE, js=COUNT_JS,
      html="<section class='g g-play-cnt%K'><div class='g-w'><div class='g-cnt'>{{#items}}<div><strong class='g-num'><span data-to='{{1}}'>{{1}}</span>{{2}}</strong><p>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-cnt{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:32px;text-align:center}.g-cnt strong{display:block;font-size:clamp(40px,5.4vw,64px);line-height:1}"
          ".g-cnt p{margin-top:10px;color:var(--g-mute);font-size:15px}",
      fields=[L('items', '数字（一行一个：数字|后面的符号|说明；数字只写阿拉伯数字）', '12000|+|个页面做出来了\n98|%|的人还会再用\n600|+|种组件')]),
    S('play-words', '轮换词', 'play', looks=THREE,
      html="<section class='g g-play-words%K'><div class='g-w'><h2 class='g-h1'>{{before}}<span class='g-rot'><span>{{#words}}<b>{{1}}</b>{{/words}}</span></span>{{after}}</h2>"
           "<p class='g-lead'>{{text}}</p></div></section>",
      css=".g-play-words{text-align:center;padding:120px 0}.g-play-words .g-lead{max-width:540px;margin:22px auto 0}.g-play-words .g-h1{font-size:clamp(32px,5.6vw,66px)}"
          ".g-rot{display:inline-block;height:1.08em;overflow:hidden;vertical-align:bottom;color:var(--g-hl)}"
          ".g-rot>span{display:flex;flex-direction:column;animation:g-rot 8s cubic-bezier(.7,0,.3,1) infinite}.g-rot b{display:block;height:1.08em;line-height:1.08em;font-weight:inherit}"
          "@keyframes g-rot{0%,20%{transform:translateY(0)}25%,45%{transform:translateY(-1.08em)}50%,70%{transform:translateY(-2.16em)}75%,95%{transform:translateY(-3.24em)}100%{transform:translateY(0)}}"
          "@media (prefers-reduced-motion:reduce){.g-rot>span{animation:none}}",
      fields=[T('before', '前面的字', '做一个'), L('words', '轮换的词（一行一个，四个最好）', '网页\n简历\n小店\n活动'), T('after', '后面的字', '，只要几分钟'),
              A('text', '说明', '挑一个模板，换上你的字和图，就好了。')]),
    S('play-flip', '翻转卡片', 'play', looks=THREE,
      html="<section class='g g-play-flip%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<div class='g-flip' tabindex='0'><div><div class='g-flip-f g-card'><span class='g-num'>{{1}}</span><h3 class='g-h3'>{{2}}</h3><small>翻过来看看 ↻</small></div>"
           "<div class='g-flip-b'><p>{{3}}</p></div></div></div>{{/items}}</div></div></section>",
      css=".g-flip{perspective:1000px;height:260px;outline:none}.g-flip>div{position:relative;height:100%;transition:transform .7s cubic-bezier(.2,.7,.2,1);transform-style:preserve-3d}"
          ".g-flip:hover>div,.g-flip:focus>div{transform:rotateY(180deg)}.g-flip-f,.g-flip-b{position:absolute;inset:0;-webkit-backface-visibility:hidden;backface-visibility:hidden;border-radius:var(--g-r2)}"
          ".g-flip-f{display:flex;flex-direction:column;justify-content:space-between}.g-flip-f .g-num{font-size:42px;color:var(--g-hl);line-height:1}.g-flip-f small{color:var(--g-faint);font-size:13px}"
          ".g-flip-b{transform:rotateY(180deg);background:var(--g-acc);color:var(--g-on);padding:28px;display:flex;align-items:center;font-size:17px;line-height:1.65}",
      fields=head_fields('小知识', '翻开看看') + [L('items', '卡片（一行一个：正面大字|正面标题|背面的话）', '01|为什么留白|空出来的地方，让眼睛有地方休息。\n02|为什么对齐|对齐了，看起来就像是认真做的。\n03|为什么少用颜色|颜色少，重要的东西才显眼。')]),
    S('play-panels', '展开图片', 'play', looks=THREE,
      html="<section class='g g-play-pan%K'><div class='g-w'>" + head() + "<div class='g-pan'>{{#items}}<a href='{{4}}'><img src='{{1}}' alt=''><div><b>{{2}}</b><span>{{3}}</span></div></a>{{/items}}</div></div></section>",
      css=".g-pan{display:flex;gap:10px;height:440px}.g-pan a{position:relative;flex:1;border-radius:var(--g-r2);overflow:hidden;transition:flex .6s cubic-bezier(.2,.7,.2,1);color:#fff;text-decoration:none}"
          ".g-pan a:first-child,.g-pan:hover a:hover{flex:3.2}.g-pan:hover a:first-child:not(:hover){flex:1}.g-pan img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}"
          ".g-pan div{position:absolute;left:0;right:0;bottom:0;padding:60px 22px 20px;background:linear-gradient(transparent,rgba(0,0,0,.6));display:flex;flex-direction:column;white-space:nowrap}"
          ".g-pan b{font-size:20px}.g-pan span{font-size:14px;opacity:.85}@media(max-width:700px){.g-pan{flex-direction:column;height:auto}.g-pan a{height:160px;flex:none!important}}",
      fields=head_fields('四季', '把鼠标放上去') + [L('items', '图片（一行一个：图片|标题|说明|链接）', '@forest|春|山里的新绿|#\n@sea|夏|海边的风|#\n@warm|秋|暖色的午后|#\n@city|冬|安静的城|#')]),
    S('play-popup', '点开的说明', 'play', looks=THREE,
      html="<section class='g g-play-pop%K'><div class='g-wn'><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p><details class='g-pop'><summary class='g-b g-b1'>{{button}}</summary>"
           "<div class='g-card'><h3 class='g-h3'>{{pop_title}}</h3><p class='g-p'>{{pop_text}}</p></div></details></div></section>",
      css=".g-play-pop{text-align:center}.g-play-pop .g-lead{max-width:520px;margin:16px auto 28px}.g-pop{display:inline-block;position:relative}.g-pop summary{list-style:none}"
          ".g-pop summary::-webkit-details-marker{display:none}.g-pop .g-card{position:absolute;left:50%;top:calc(100% + 12px);transform:translateX(-50%);width:min(360px,86vw);text-align:left;"
          "box-shadow:0 24px 60px rgba(0,0,0,.16);z-index:5;animation:g-pop .25s cubic-bezier(.2,.7,.2,1)}@keyframes g-pop{from{opacity:0;transform:translate(-50%,-6px)}}",
      fields=[T('title', '标题', '想知道怎么做的？'), A('text', '说明', '点一下按钮，下面会弹出说明。'), T('button', '按钮', '点我看看'), T('pop_title', '弹出的标题', '其实很简单'),
              A('pop_text', '弹出的内容', '选一个组件，拖到页面上，然后在右边改字就行。')]),
    S('play-glow', '跟随光晕卡片', 'play', looks=('ink', '', 'soft'), js=GLOW_JS, icons=True,
      html="<section class='g g-play-glow%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<div class='g-card g-glow-c'><span class='g-ib'><i class='g-i g-i-{{1}}'></i></span><h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></div>{{/items}}</div></div></section>",
      css=".g-glow-c{position:relative;overflow:hidden;--mx:50%;--my:0px}.g-glow-c:before{content:'';position:absolute;inset:0;opacity:0;transition:opacity .3s;pointer-events:none;"
          "background:radial-gradient(320px circle at var(--mx) var(--my),color-mix(in srgb,var(--cp-primary) 22%,transparent),transparent 60%)}.g-glow-c:hover:before{opacity:1}"
          ".g-glow-c>*{position:relative}.g-glow-c .g-h3{margin-top:20px}",
      fields=head_fields('为什么', '把鼠标移上去试试') + [L('items', '卡片（一行一个：图标|标题|说明）', 'bolt|快|打开就能用。\nshield|稳|每一步都能撤销。\nspark|好看|每个细节都调过。')]),
]
