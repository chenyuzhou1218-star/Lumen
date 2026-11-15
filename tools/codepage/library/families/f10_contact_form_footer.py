"""联系, 表单, 页脚."""
from kit import ICON_HELP
from parts import FOUR, THREE, S, A, L, P, T, head, head_fields

ITEMS = [
    S('contact-cards', '联系方式卡片', 'contact', icons=True, looks=FOUR,
      html="<section class='g g-co-cards%K'><div class='g-w'>" + head() + "<div class='g-g3'>{{#items}}<a class='g-card g-lift g-coc' href='{{4}}'><span class='g-ib'><i class='g-i g-i-{{1}}'></i></span>"
           "<h3 class='g-h3'>{{2}}</h3><p class='g-p'>{{3}}</p></a>{{/items}}</div></div></section>",
      css=".g-coc{display:block;text-decoration:none;color:inherit}.g-coc .g-h3{margin-top:18px}",
      fields=head_fields('联系我们', '有事就找我们', '工作日一般当天回复。') + [L('items', f'方式（一行一个：图标|标题|内容|链接。{ICON_HELP}）',
                                                                           'mail|写信|hi@example.com|mailto:hi@example.com\nphone|打电话|010-1234 5678|tel:01012345678\npin|来坐坐|城东路 18 号 · 二楼|#')]),
    S('contact-form-side', '表单加信息', 'contact', icons=True, looks=FOUR,
      html="<section class='g g-co-fs%K'><div class='g-w g-split'><div>" + head(center=False) + "<ul class='g-co-l'>{{#items}}<li><i class='g-i g-i-{{1}}'></i><span><b>{{2}}</b>{{3}}</span></li>{{/items}}</ul></div>"
           "<form class='g-card g-co-f' action='{{url/mailto:email}}' method='post'><label>名字<input name='name' required></label><label>邮箱<input name='email' type='email' required></label>"
           "<label>想说的话<textarea name='message' rows='4' required></textarea></label><button class='g-b g-b1' type='submit'>{{button}}</button></form></div></section>",
      css=".g-co-fs .g-split{align-items:start}.g-co-l{list-style:none;padding:0;margin:0;display:grid;gap:20px}.g-co-l li{display:flex;gap:14px}.g-co-l .g-i{color:var(--g-hl);margin-top:2px}"
          ".g-co-l span{display:flex;flex-direction:column;font-size:15px;color:var(--g-mute)}.g-co-l b{color:var(--g-ink);font-size:15px}"
          ".g-co-f{display:flex;flex-direction:column;gap:16px;padding:32px}.g-co-f label{display:flex;flex-direction:column;gap:7px;font-size:14px;font-weight:600}"
          ".g-co-f input,.g-co-f textarea{font:inherit;font-size:15px;font-weight:400;padding:11px 14px;border:1px solid var(--g-line);border-radius:var(--g-r);background:var(--g-bg);color:var(--g-ink);outline:none}"
          ".g-co-f input:focus,.g-co-f textarea:focus{border-color:var(--g-hl)}.g-co-f textarea{resize:vertical}",
      fields=head_fields('联系', '聊聊你的想法', '填好表单，或者直接写信给我们。') + [L('items', f'信息（一行一个：图标|标题|内容。{ICON_HELP}）', 'mail|邮箱|hi@example.com\nphone|电话|010-1234 5678\nclock|时间|周一到周五 9:00–18:00'),
                                                                           T('button', '按钮', '发送'), T('email', '收信邮箱', 'hi@example.com'), T('url', '提交地址（有后端就填，比如 /api/contact；空着就发到上面的邮箱）', '')]),
    S('contact-map', '地址和地图', 'contact', looks=FOUR,
      html="<section class='g g-co-map%K'><div class='g-w g-split'><a class='g-co-m' href='{{map_url}}'><svg viewBox='0 0 400 300' preserveAspectRatio='xMidYMid slice'><rect width='400' height='300' fill='var(--g-soft)'/>"
           "<path d='M0 80h400M0 190h400M120 0v300M290 0v300M0 250l400-120' stroke='var(--g-line)' stroke-width='14'/><path d='M0 140h400M60 0v300M210 0v300' stroke='var(--g-card)' stroke-width='6'/>"
           "<circle cx='210' cy='140' r='34' fill='var(--g-hl)' opacity='.16'/><path d='M210 158s-18-17-18-30a18 18 0 0 1 36 0c0 13-18 30-18 30z' fill='var(--g-hl)'/><circle cx='210' cy='128' r='6' fill='var(--g-card)'/></svg>"
           "<span>在地图上打开 ↗</span></a><div>" + head(center=False, lead=False) + "<dl class='g-co-dl'>{{#items}}<dt>{{1}}</dt><dd>{{2}}</dd>{{/items}}</dl></div></div></section>",
      css=".g-co-m{position:relative;display:block;aspect-ratio:4/3;border-radius:var(--g-r2);overflow:hidden;border:1px solid var(--g-line)}.g-co-m svg{width:100%;height:100%;display:block}"
          ".g-co-m span{position:absolute;left:16px;bottom:16px;font-size:13px;font-weight:600;padding:7px 12px;border-radius:99px;background:var(--g-card);color:var(--g-ink);box-shadow:0 4px 14px rgba(0,0,0,.1)}"
          ".g-co-dl{display:grid;grid-template-columns:auto 1fr;gap:14px 28px;margin:0;font-size:15.5px}.g-co-dl dt{color:var(--g-faint)}.g-co-dl dd{margin:0}",
      fields=head_fields('地址', '来店里坐坐', with_lead=False) + [T('map_url', '地图链接', 'https://map.baidu.com/'),
                                                             L('items', '信息（一行一个：名称|内容）', '地址|城东路 18 号 · 二楼\n营业|每天 8:00–20:00\n电话|010-1234 5678\n交通|地铁 2 号线 B 口，步行 3 分钟')]),
    S('contact-offices', '多个地点', 'contact', looks=FOUR,
      html="<section class='g g-co-off%K'><div class='g-w'>" + head(center=False) + "<div class='g-g3'>{{#items}}<div class='g-coo'><h3 class='g-h3'>{{1}}</h3><p class='g-p'>{{2}}</p><a class='g-b3' href='{{4}}'>{{3}}</a></div>{{/items}}</div></div></section>",
      css=".g-coo{padding-top:22px;border-top:1px solid var(--g-line)}.g-coo .g-b3{margin-top:14px;font-size:14px}",
      fields=head_fields('办公室', '在这些城市找到我们', with_lead=False) + [L('items', '地点（一行一个：城市|地址|链接文字|链接）',
                                                                       '北京|朝阳区望京街 9 号|看地图|#\n上海|徐汇区漕溪路 88 号|看地图|#\n深圳|南山区科技园 12 栋|看地图|#')]),
    S('form-login', '登录卡片', 'form', looks=THREE,
      html="<section class='g g-fm-login%K'><div class='g-w'><form class='g-card g-fl' action='{{url}}' method='post'><h2 class='g-h3'>{{title}}</h2><p class='g-p'>{{text}}</p>"
           "<label>邮箱<input name='email' type='email' autocomplete='email' required></label><label>密码<input name='password' type='password' autocomplete='current-password' required></label>"
           "<button class='g-b g-b1' type='submit'>{{button}}</button><p class='g-fl-f'>{{foot}} <a href='{{foot_url}}'>{{foot_link}}</a></p></form></div></section>",
      css=".g-fl{max-width:400px;margin:0 auto;padding:36px;display:flex;flex-direction:column;gap:14px;box-shadow:0 24px 60px rgba(0,0,0,.07)}.g-fl .g-h3{font-size:24px}.g-fl>.g-p{margin:-6px 0 8px}"
          ".g-fl label{display:flex;flex-direction:column;gap:7px;font-size:14px;font-weight:600}"
          ".g-fl input{font:inherit;font-size:15px;font-weight:400;height:46px;padding:0 14px;border:1px solid var(--g-line);border-radius:var(--g-r);background:var(--g-bg);color:var(--g-ink);outline:none}"
          ".g-fl input:focus{border-color:var(--g-hl);box-shadow:0 0 0 4px color-mix(in srgb,var(--g-hl) 14%,transparent)}.g-fl .g-b{margin-top:6px}"
          ".g-fl-f{text-align:center;font-size:14px;color:var(--g-mute)}.g-fl-f a{color:var(--g-hl);font-weight:600;text-decoration:none}",
      fields=[T('title', '标题', '欢迎回来'), A('text', '说明', '用邮箱和密码登录。'), T('button', '按钮', '登录'), T('url', '提交地址', '#'),
              T('foot', '底部文字', '还没有账号？'), T('foot_link', '底部链接文字', '注册一个'), T('foot_url', '底部链接', '#')]),
    S('form-signup', '注册表单', 'form', looks=THREE,
      html="<section class='g g-fm-signup%K'><div class='g-w g-split'><div>" + head(center=False) + "</div><form class='g-card g-fs2' action='{{url}}' method='post'>"
           "<div class='g-fs2-r'><label>名字<input name='name' required></label><label>城市<input name='city'></label></div><label>邮箱<input name='email' type='email' required></label>"
           "<label>你想做什么样的网页<select name='kind'>{{#kinds}}<option>{{1}}</option>{{/kinds}}</select></label><label class='g-fs2-c'><input type='checkbox' name='news'> {{check}}</label>"
           "<button class='g-b g-b1' type='submit'>{{button}}</button></form></div></section>",
      css=".g-fs2{display:flex;flex-direction:column;gap:14px;padding:32px}.g-fs2-r{display:grid;grid-template-columns:1fr 1fr;gap:12px}"
          ".g-fs2 label{display:flex;flex-direction:column;gap:7px;font-size:14px;font-weight:600}"
          ".g-fs2 input:not([type=checkbox]),.g-fs2 select{font:inherit;font-size:15px;font-weight:400;height:46px;padding:0 13px;border:1px solid var(--g-line);border-radius:var(--g-r);background:var(--g-bg);color:var(--g-ink);outline:none}"
          ".g-fs2 input:focus,.g-fs2 select:focus{border-color:var(--g-hl)}.g-fs2 .g-fs2-c{flex-direction:row;align-items:center;gap:9px;font-weight:400;color:var(--g-mute)}"
          ".g-fs2-c input{width:17px;height:17px;accent-color:var(--g-hl)}@media(max-width:480px){.g-fs2-r{grid-template-columns:1fr}}",
      fields=head_fields('报名', '加入第一批用户', '名额有限，我们会按报名的顺序发邀请。') + [L('kinds', '下拉选项（一行一个）', '个人主页\n小店\n活动页\n公司官网\n还没想好'),
                                                                                 T('check', '勾选框文字', '有新消息时发邮件告诉我'), T('button', '按钮', '报名'), T('url', '提交地址', '#')]),
    S('form-survey', '问卷单选', 'form', looks=THREE,
      html="<section class='g g-fm-survey%K'><div class='g-wn'>" + head() + "<form class='g-card g-sv' action='{{url}}' method='post'><p class='g-sv-q'>{{question}}</p><div class='g-sv-o'>{{#options}}"
           "<label><input type='radio' name='answer' value='{{1}}'><span>{{1}}</span></label>{{/options}}</div><textarea name='more' rows='3' placeholder='{{more_hint}}'></textarea>"
           "<button class='g-b g-b1' type='submit'>{{button}}</button></form></div></section>",
      css=".g-sv{display:flex;flex-direction:column;gap:18px;padding:32px}.g-sv-q{font-size:18px;font-weight:600}.g-sv-o{display:grid;grid-template-columns:1fr 1fr;gap:10px}"
          ".g-sv-o label{cursor:pointer}.g-sv-o input{position:absolute;opacity:0}.g-sv-o span{display:block;padding:14px 16px;border:1px solid var(--g-line);border-radius:var(--g-r);font-size:15px;transition:border-color .15s,background .15s}"
          ".g-sv-o span:hover{border-color:var(--g-faint)}.g-sv-o input:checked+span{border-color:var(--g-hl);background:color-mix(in srgb,var(--g-hl) 8%,transparent);font-weight:600}"
          ".g-sv-o input:focus-visible+span{box-shadow:0 0 0 3px color-mix(in srgb,var(--g-hl) 25%,transparent)}"
          ".g-sv textarea{font:inherit;font-size:15px;padding:12px 14px;border:1px solid var(--g-line);border-radius:var(--g-r);background:var(--g-bg);color:var(--g-ink);resize:vertical;outline:none}"
          ".g-sv .g-b{align-self:flex-start}@media(max-width:520px){.g-sv-o{grid-template-columns:1fr}}",
      fields=head_fields('一个小问题', '帮我们做得更好', '只需要十秒钟。') + [T('question', '问题', '你最常用它来做什么？'), L('options', '选项（一行一个）', '个人主页\n小店\n活动\n别的'),
                                                                     T('more_hint', '补充说明的提示', '还想说点什么（可以不填）'), T('button', '按钮', '提交'), T('url', '提交地址', '#')]),
    S('form-booking', '预约表单', 'form', looks=THREE,
      html="<section class='g g-fm-book%K'><div class='g-w g-split'><div>" + head(center=False) + "</div><form class='g-card g-bk' action='{{url}}' method='post'>"
           "<div class='g-bk-r'><label>日期<input name='date' type='date' required></label><label>时间<select name='time'>{{#times}}<option>{{1}}</option>{{/times}}</select></label></div>"
           "<div class='g-bk-r'><label>人数<input name='people' type='number' min='1' value='2'></label><label>电话<input name='phone' type='tel' required></label></div>"
           "<button class='g-b g-b1' type='submit'>{{button}}</button><small>{{note}}</small></form></div></section>",
      css=".g-bk{display:flex;flex-direction:column;gap:14px;padding:32px}.g-bk-r{display:grid;grid-template-columns:1fr 1fr;gap:12px}"
          ".g-bk label{display:flex;flex-direction:column;gap:7px;font-size:14px;font-weight:600}"
          ".g-bk input,.g-bk select{font:inherit;font-size:15px;font-weight:400;height:46px;padding:0 13px;border:1px solid var(--g-line);border-radius:var(--g-r);background:var(--g-bg);color:var(--g-ink);outline:none;min-width:0}"
          ".g-bk input:focus,.g-bk select:focus{border-color:var(--g-hl)}.g-bk small{font-size:13px;color:var(--g-faint);text-align:center}",
      fields=head_fields('订位', '给你留一张桌子', '周末人多，建议提前一天订。') + [L('times', '可选时间（一行一个）', '11:30\n12:30\n17:30\n18:30\n19:30'),
                                                                      T('button', '按钮', '订位'), T('url', '提交地址', '#'), T('note', '小字', '我们会打电话跟你确认。')]),
    S('form-feedback', '打分反馈', 'form', looks=THREE,
      html="<section class='g g-fm-fb%K'><div class='g-wn'><form class='g-card g-fb2' action='{{url}}' method='post'><h2 class='g-h3'>{{title}}</h2><div class='g-fb2-s'>"
           "<input type='radio' name='score' id='g-s5' value='5'><label for='g-s5'>★</label><input type='radio' name='score' id='g-s4' value='4'><label for='g-s4'>★</label>"
           "<input type='radio' name='score' id='g-s3' value='3'><label for='g-s3'>★</label><input type='radio' name='score' id='g-s2' value='2'><label for='g-s2'>★</label>"
           "<input type='radio' name='score' id='g-s1' value='1'><label for='g-s1'>★</label></div><textarea name='message' rows='3' placeholder='{{hint}}'></textarea>"
           "<button class='g-b g-b1' type='submit'>{{button}}</button></form></div></section>",
      css=".g-fb2{max-width:520px;margin:0 auto;text-align:center;display:flex;flex-direction:column;gap:18px;padding:36px}"
          ".g-fb2-s{display:flex;flex-direction:row-reverse;justify-content:center;gap:6px}.g-fb2-s input{position:absolute;opacity:0}"
          ".g-fb2-s label{font-size:36px;line-height:1;color:var(--g-line);cursor:pointer;transition:color .12s,transform .12s}.g-fb2-s label:hover{transform:scale(1.12)}"
          ".g-fb2-s label:hover,.g-fb2-s label:hover~label,.g-fb2-s input:checked~label{color:#f5a623}"
          ".g-fb2 textarea{font:inherit;font-size:15px;padding:12px 14px;border:1px solid var(--g-line);border-radius:var(--g-r);background:var(--g-bg);color:var(--g-ink);resize:vertical;outline:none;text-align:left}",
      fields=[T('title', '标题', '这次体验怎么样？'), T('hint', '输入框提示', '说说哪里好，哪里不好'), T('button', '按钮', '提交'), T('url', '提交地址', '#')]),
    S('form-newsletter', '订阅一行', 'form', looks=FOUR,
      html="<section class='g g-fm-nl%K'><div class='g-wn'><form class='g-nl' action='{{url}}' method='post'><div><b>{{title}}</b><span>{{text}}</span></div>"
           "<input name='email' type='email' required placeholder='{{hint}}' aria-label='{{hint}}'><button class='g-b g-b1' type='submit'>{{button}}</button></form></div></section>",
      css=".g-fm-nl{padding:56px 0}.g-nl{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.g-nl div{flex:1 1 220px;display:flex;flex-direction:column}"
          ".g-nl b{font-size:17px}.g-nl span{font-size:14px;color:var(--g-mute)}.g-nl input{flex:1 1 200px;height:46px;padding:0 14px;border:1px solid var(--g-line);border-radius:var(--g-r);"
          "background:var(--g-card);color:var(--g-ink);font:inherit;font-size:15px;outline:none}.g-nl input:focus{border-color:var(--g-hl)}",
      fields=[T('title', '标题', '订阅更新'), T('text', '说明', '每月一封，不多。'), T('hint', '输入框提示', '你的邮箱'), T('button', '按钮', '订阅'), T('url', '提交地址', '#')]),
    S('footer-four', '四栏页脚', 'footer', looks=FOUR,
      html="<footer class='g g-ft4%K'><div class='g-w'><div class='g-ft4-g'><div><b class='g-ft-logo'>{{brand}}</b><p class='g-p'>{{text}}</p></div>"
           "<div><h4>{{c1}}</h4>{{#l1}}<a href='{{2}}'>{{1}}</a>{{/l1}}</div><div><h4>{{c2}}</h4>{{#l2}}<a href='{{2}}'>{{1}}</a>{{/l2}}</div><div><h4>{{c3}}</h4>{{#l3}}<a href='{{2}}'>{{1}}</a>{{/l3}}</div></div>"
           "<div class='g-ft-bot'><span>{{copy}}</span><span>{{small}}</span></div></div></footer>",
      css=".g-ft4{padding:72px 0 32px;border-top:1px solid var(--g-line)}.g-ft4-g{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:40px}.g-ft-logo{font-size:19px;letter-spacing:-.03em}"
          ".g-ft4-g .g-p{max-width:300px;font-size:14.5px}.g-ft4 h4{font-size:13.5px;margin:0 0 14px;color:var(--g-ink)}"
          ".g-ft4-g a{display:block;font-size:14.5px;color:var(--g-mute);text-decoration:none;padding:4px 0}.g-ft4-g a:hover{color:var(--g-ink)}"
          ".g-ft-bot{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-top:56px;padding-top:24px;border-top:1px solid var(--g-line);font-size:13px;color:var(--g-faint)}"
          "@media(max-width:760px){.g-ft4-g{grid-template-columns:1fr 1fr}.g-ft4-g>div:first-child{grid-column:span 2}}",
      fields=[T('brand', '名字', '小满'), A('text', '介绍', '一个让做网页变简单的小工具。'), T('c1', '第一栏标题', '产品'), L('l1', '第一栏链接（一行一个：文字|地址）', '组件|#\n模板|#\n更新|#'),
              T('c2', '第二栏标题', '帮助'), L('l2', '第二栏链接（一行一个：文字|地址）', '手册|#\n问答|#\n联系|#'), T('c3', '第三栏标题', '关于'), L('l3', '第三栏链接（一行一个：文字|地址）', '团队|#\n招聘|#\n博客|#'),
              T('copy', '版权', '© 2026 小满'), T('small', '右下角', '用心做的')]),
    S('footer-center', '居中页脚', 'footer', looks=FOUR,
      html="<footer class='g g-ftc%K'><div class='g-wn'><b class='g-ft-logo'>{{brand}}</b><nav>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</nav><p>{{copy}}</p></div></footer>",
      css=".g-ftc{padding:56px 0;text-align:center;border-top:1px solid var(--g-line)}.g-ftc .g-ft-logo{font-size:19px;letter-spacing:-.03em}"
          ".g-ftc nav{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 26px;margin:20px 0}.g-ftc a{font-size:14.5px;color:var(--g-mute);text-decoration:none}.g-ftc a:hover{color:var(--g-ink)}"
          ".g-ftc p{font-size:13px;color:var(--g-faint)}",
      fields=[T('brand', '名字', '青石'), L('links', '链接（一行一个：文字|地址）', '首页|#\n作品|#\n日志|#\n关于|#\n联系|#'), T('copy', '版权', '© 2026 青石工作室')]),
    S('footer-big', '大字页脚', 'footer', looks=FOUR,
      html="<footer class='g g-ftb%K'><div class='g-w'><div class='g-ftb-top'><p class='g-h'>{{say}}</p><a class='g-b g-b1' href='{{url}}'>{{button}}</a></div>"
           "<div class='g-ftb-mid'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div><p class='g-ftb-word'>{{brand}}</p></div></footer>",
      css=".g-ftb{padding:88px 0 0;overflow:hidden}.g-ftb-top{display:flex;justify-content:space-between;align-items:flex-end;gap:32px;flex-wrap:wrap}.g-ftb-top .g-h{max-width:620px}"
          ".g-ftb-mid{display:flex;gap:28px;flex-wrap:wrap;margin-top:56px;padding-top:24px;border-top:1px solid var(--g-line)}.g-ftb-mid a{font-size:14.5px;color:var(--g-mute);text-decoration:none}"
          ".g-ftb-mid a:hover{color:var(--g-ink)}.g-ftb-word{font-size:clamp(80px,20vw,280px);font-weight:800;letter-spacing:-.07em;line-height:.8;margin:48px 0 -.12em;"
          "color:transparent;-webkit-text-stroke:1.5px var(--g-line);white-space:nowrap}",
      fields=[T('say', '大标题', '有想法？我们一起把它做出来。'), T('button', '按钮', '写信给我们'), T('url', '按钮链接', 'mailto:hi@example.com'),
              L('links', '链接（一行一个：文字|地址）', '作品|#\n团队|#\n招聘|#\n微博|#\n公众号|#'), T('brand', '底部大字', 'Studio')]),
    S('footer-news', '带订阅页脚', 'footer', looks=FOUR,
      html="<footer class='g g-ftn%K'><div class='g-w'><div class='g-ftn-g'><div><b class='g-ft-logo'>{{brand}}</b><p class='g-p'>{{text}}</p>"
           "<form class='g-ftn-f' action='{{url}}' method='post'><input name='email' type='email' required placeholder='{{hint}}' aria-label='{{hint}}'><button class='g-b g-b1' type='submit'>{{button}}</button></form></div>"
           "<div class='g-ftn-l'>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</div></div><div class='g-ft-bot'><span>{{copy}}</span></div></div></footer>",
      css=".g-ftn{padding:72px 0 32px;border-top:1px solid var(--g-line)}.g-ftn-g{display:grid;grid-template-columns:1.3fr 1fr;gap:56px}.g-ft-logo{font-size:19px;letter-spacing:-.03em}"
          ".g-ftn-f{display:flex;gap:8px;margin-top:22px;max-width:420px}.g-ftn-f input{flex:1;min-width:0;height:44px;padding:0 13px;border:1px solid var(--g-line);border-radius:var(--g-r);"
          "background:var(--g-card);color:var(--g-ink);font:inherit;font-size:14.5px;outline:none}.g-ftn-f .g-b{height:44px}"
          ".g-ftn-l{display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;align-content:start}.g-ftn-l a{font-size:14.5px;color:var(--g-mute);text-decoration:none;padding:4px 0}.g-ftn-l a:hover{color:var(--g-ink)}"
          ".g-ft-bot{margin-top:56px;padding-top:24px;border-top:1px solid var(--g-line);font-size:13px;color:var(--g-faint)}@media(max-width:760px){.g-ftn-g{grid-template-columns:1fr;gap:36px}}",
      fields=[T('brand', '名字', '远山'), A('text', '介绍', '每月一封信，讲我们最近在做的事。'), T('hint', '输入框提示', '你的邮箱'), T('button', '按钮', '订阅'), T('url', '提交地址', '#'),
              L('links', '链接（一行一个：文字|地址）', '产品|#\n价格|#\n博客|#\n帮助|#\n团队|#\n联系|#'), T('copy', '版权', '© 2026 远山')]),
    S('footer-social', '带社交图标', 'footer', looks=FOUR,
      html="<footer class='g g-fts%K'><div class='g-w g-fts-in'><span>{{copy}}</span><nav>{{#links}}<a href='{{2}}'>{{1}}</a>{{/links}}</nav><div class='g-fts-s'>"
           "<a href='{{s1}}' aria-label='分享'><svg viewBox='0 0 24 24'><circle cx='18' cy='5' r='2.6'/><circle cx='6' cy='12' r='2.6'/><circle cx='18' cy='19' r='2.6'/><path d='m8.3 13.3 7.4 4.4M15.7 6.3 8.3 10.7'/></svg></a>"
           "<a href='{{s2}}' aria-label='邮件'><svg viewBox='0 0 24 24'><path d='M4 6h16v12H4z'/><path d='m4.4 6.4 7.6 6.1 7.6-6.1'/></svg></a>"
           "<a href='{{s3}}' aria-label='代码仓库'><svg viewBox='0 0 24 24'><path d='m8.5 7.5-4.5 4.5 4.5 4.5M15.5 7.5l4.5 4.5-4.5 4.5'/></svg></a></div></div></footer>",
      css=".g-fts{padding:28px 0;border-top:1px solid var(--g-line)}.g-fts-in{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;font-size:13.5px;color:var(--g-faint)}"
          ".g-fts nav{display:flex;gap:22px;flex-wrap:wrap}.g-fts nav a{color:var(--g-mute);text-decoration:none}.g-fts nav a:hover{color:var(--g-ink)}"
          ".g-fts-s{display:flex;gap:6px}.g-fts-s a{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--g-mute);border:1px solid var(--g-line);transition:color .15s,border-color .15s}"
          ".g-fts-s a:hover{color:var(--g-ink);border-color:var(--g-faint)}.g-fts-s svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}",
      fields=[T('copy', '版权', '© 2026 日出'), L('links', '链接（一行一个：文字|地址）', '隐私|#\n条款|#\n联系|#'), T('s1', '第一个图标链接（分享）', '#'), T('s2', '第二个图标链接（邮件）', 'mailto:hi@example.com'), T('s3', '第三个图标链接（代码）', '#')]),
]
