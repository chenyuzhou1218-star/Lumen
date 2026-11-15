"""价格表 (a block people drag into their own pages) and 问答."""
from parts import FOUR, S, A, L, T, head, head_fields

FAQ = ('要会写代码吗？|不用。拖、点、打字就够了。\n能在手机上看吗？|能。每个组件都会自己适应手机的宽度。\n'
       '做好的网页放在哪里？|导出是一个文件，放到任何能放网页的地方都行。\n可以改颜色和字体吗？|可以。在“外观”里换配色、字体和圆角。')

def _plan(n: int) -> str:
    return (f"<div class='g-card g-pr-c'><h3>{{{{p{n}_name}}}}</h3><div class='g-pr-p'><b class='g-num'>{{{{p{n}_price}}}}</b><span>{{{{p{n}_unit}}}}</span></div>"
            f"<ul>{{{{#p{n}_points}}}}<li>{{{{1}}}}</li>{{{{/p{n}_points}}}}</ul><a class='g-b g-b2' href='{{{{p{n}_url}}}}'>{{{{p{n}_button}}}}</a></div>")


def _plan_fields(n, name, price, unit, points, button):
    return [T(f'p{n}_name', f'第{n}档名称', name), T(f'p{n}_price', f'第{n}档价格', price), T(f'p{n}_unit', f'第{n}档单位', unit),
            L(f'p{n}_points', f'第{n}档包含（一行一个）', points), T(f'p{n}_button', f'第{n}档按钮', button), T(f'p{n}_url', f'第{n}档链接', '#')]


ITEMS = [
    S('price-three', '三档价格', 'price', looks=FOUR,
      html="<section class='g g-pr3%K'><div class='g-w'>" + head() + "<div class='g-g3 g-pr'>" + _plan(1) + _plan(2) + _plan(3) + "</div></div></section>",
      css=".g-pr-c{display:flex;flex-direction:column;padding:32px 30px}.g-pr-c h3{font-size:15px;font-weight:600;color:var(--g-mute)}"
          ".g-pr-p{display:flex;align-items:baseline;gap:8px;margin:14px 0 22px}.g-pr-p b{font-size:44px;line-height:1}.g-pr-p span{font-size:14px;color:var(--g-faint)}"
          ".g-pr-c ul{list-style:none;padding:20px 0 0;margin:0 0 28px;border-top:1px solid var(--g-line);flex:1;font-size:15px;line-height:2.1;color:var(--g-mute)}"
          ".g-pr-c li:before{content:'✓';color:var(--g-hl);font-weight:700;margin-right:10px}"
          ".g-pr-c:nth-child(2){border:2px solid var(--g-hl);box-shadow:0 24px 50px rgba(0,0,0,.08);transform:translateY(-8px)}"
          ".g-pr-c:nth-child(2) .g-b{background:var(--g-acc);color:var(--g-on);border-color:transparent}"
          "@media(max-width:900px){.g-pr-c:nth-child(2){transform:none}}",
      fields=head_fields('价格', '挑一个适合你的', '先用起来，需要更多的时候再换。')
      + _plan_fields(1, '入门', '¥ 0', '一个人用', '做三个页面\n导出网页\n十套配色', '开始用')
      + _plan_fields(2, '专业', '¥ 29', '每月', '不限页面\n自己的域名\n优先回复', '选这个')
      + _plan_fields(3, '团队', '¥ 99', '每月', '十个成员\n一起编辑\n历史版本', '联系我们')),
    S('price-two', '两档对比', 'price', looks=FOUR,
      html="<section class='g g-pr2%K'><div class='g-wn'>" + head() + "<div class='g-g2'>{{#plans}}<div class='g-card g-pr2-c'><span class='g-tag'>{{1}}</span><b class='g-num'>{{2}}</b><p class='g-p'>{{3}}</p>"
           "<a class='g-b g-b1' href='{{5}}'>{{4}}</a></div>{{/plans}}</div></div></section>",
      css=".g-pr2-c{display:flex;flex-direction:column;align-items:flex-start;padding:32px}.g-pr2-c b{font-size:46px;margin:18px 0 6px;line-height:1}.g-pr2-c .g-p{flex:1;margin-bottom:26px}"
          ".g-pr2-c .g-b{width:100%}.g-pr2-c:first-child .g-b{background:transparent;color:var(--g-ink);border-color:var(--g-line)}",
      fields=head_fields('两种选择', '按月，还是按年') + [L('plans', '方案（一行一个：名称|价格|说明|按钮|链接）', '按月|¥ 29|随时可以停。|按月付|#\n按年|¥ 290|相当于送两个月。|按年付|#')]),
    S('price-table', '功能对比表', 'price', looks=('', 'soft'),
      html="<section class='g g-prt%K'><div class='g-w'>" + head() + "<div class='g-prt-w'><table><thead><tr><th></th>{{#cols}}<th>{{1}}</th>{{/cols}}</tr></thead>"
           "<tbody>{{#rows}}<tr><td>{{1}}</td><td>{{2}}</td><td>{{3}}</td><td>{{4}}</td></tr>{{/rows}}</tbody></table></div></div></section>",
      css=".g-prt-w{overflow-x:auto;border:1px solid var(--g-line);border-radius:var(--g-r2);background:var(--g-card)}.g-prt table{width:100%;border-collapse:collapse;font-size:15px;min-width:560px}"
          ".g-prt th,.g-prt td{padding:16px 22px;text-align:center;border-bottom:1px solid var(--g-line)}.g-prt th{font-size:14px;color:var(--g-mute);font-weight:600}"
          ".g-prt td:first-child,.g-prt th:first-child{text-align:left}.g-prt tbody tr:last-child td{border-bottom:0}.g-prt tbody tr:hover{background:var(--g-soft)}"
          ".g-prt th:nth-child(3),.g-prt td:nth-child(3){background:color-mix(in srgb,var(--g-hl) 6%,transparent)}",
      fields=head_fields('对比', '每一档都有什么') + [L('cols', '列名（一行一个）', '入门\n专业\n团队'),
                                              L('rows', '行（一行一个：功能|入门|专业|团队）', '页面数量|3|不限|不限\n自己的域名|—|✓|✓\n一起编辑|—|—|✓\n历史版本|7 天|30 天|一年\n回复速度|两天|当天|一小时')]),
    S('price-single', '单一方案', 'price', looks=FOUR,
      html="<section class='g g-prs%K'><div class='g-w'><div class='g-card g-prs-c'><div><div class='g-eb'>{{eyebrow}}</div><h2 class='g-h'>{{title}}</h2><p class='g-lead'>{{text}}</p>"
           "<ul class='g-prs-l'>{{#points}}<li>{{1}}</li>{{/points}}</ul></div><div class='g-prs-box'><span>{{label}}</span><b class='g-num'>{{price}}</b><small>{{unit}}</small>"
           "<a class='g-b g-b1' href='{{url}}'>{{button}}</a><em>{{note}}</em></div></div></div></section>",
      css=".g-prs-c{display:grid;grid-template-columns:1.4fr 1fr;gap:48px;padding:48px;align-items:center}"
          ".g-prs-l{list-style:none;padding:0;margin:26px 0 0;display:grid;grid-template-columns:1fr 1fr;gap:10px 20px;font-size:15px}"
          ".g-prs-l li:before{content:'✓';color:var(--g-hl);font-weight:700;margin-right:9px}"
          ".g-prs-box{text-align:center;background:var(--g-soft);border-radius:var(--g-r2);padding:36px 28px;display:flex;flex-direction:column;align-items:center}"
          ".g-prs-box span{font-size:14px;color:var(--g-mute)}.g-prs-box b{font-size:56px;line-height:1.1;margin-top:8px}.g-prs-box small{font-size:13px;color:var(--g-faint)}"
          ".g-prs-box .g-b{width:100%;margin-top:24px}.g-prs-box em{font-style:normal;font-size:12.5px;color:var(--g-faint);margin-top:12px}"
          "@media(max-width:820px){.g-prs-c{grid-template-columns:1fr;padding:30px}.g-prs-l{grid-template-columns:1fr}}",
      fields=[T('eyebrow', '小标题', '会员'), T('title', '标题', '一次付清，一直能用'), A('text', '说明', '不按月收钱，买一次，以后的更新都有。'),
              L('points', '包含（一行一个）', '全部组件\n以后的更新\n自己的域名\n优先回复'), T('label', '价格上方', '只要一次'), T('price', '价格', '¥ 199'),
              T('unit', '价格下方', '没有月费'), T('button', '按钮', '买下来'), T('url', '按钮链接', '#'), T('note', '小字', '七天内不满意，原路退回')]),
    S('faq-accordion', '展开问答', 'faq', looks=FOUR,
      html="<section class='g g-faq-acc%K'><div class='g-wn'>" + head() + "<div class='g-fa'>{{#items}}<details><summary>{{1}}</summary><p>{{2}}</p></details>{{/items}}</div></div></section>",
      css=".g-fa details{border-bottom:1px solid var(--g-line)}.g-fa details:first-child{border-top:1px solid var(--g-line)}"
          ".g-fa summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:20px;padding:22px 0;font-size:17px;font-weight:600}"
          ".g-fa summary::-webkit-details-marker{display:none}.g-fa summary:after{content:'';width:10px;height:10px;flex:none;border:solid var(--g-faint);border-width:0 1.8px 1.8px 0;"
          "transform:rotate(45deg) translateY(-3px);transition:transform .25s}.g-fa details[open] summary:after{transform:rotate(-135deg) translateY(-2px)}"
          ".g-fa p{padding:0 40px 24px 0;margin:0;color:var(--g-mute);line-height:1.75}",
      fields=head_fields('问答', '大家常问的', '没找到答案？写信给我们。') + [L('items', '问答（一行一个：问题|回答）', FAQ)]),
    S('faq-grid', '两栏问答', 'faq', looks=FOUR,
      html="<section class='g g-faq-grid%K'><div class='g-w'>" + head(center=False) + "<div class='g-g2 g-fg'>{{#items}}<div><h3 class='g-h3'>{{1}}</h3><p class='g-p'>{{2}}</p></div>{{/items}}</div></div></section>",
      css=".g-fg{gap:40px 56px}.g-fg .g-h3{font-size:17px}.g-fg .g-p{margin-top:10px;font-size:15.5px}",
      fields=head_fields('问答', '你可能想知道') + [L('items', '问答（一行一个：问题|回答）', FAQ)]),
    S('faq-side', '左标题右问答', 'faq', looks=FOUR,
      html="<section class='g g-faq-side%K'><div class='g-w g-fs'><div>" + head(center=False) + "<a class='g-b g-b2' href='{{url}}'>{{button}}</a></div>"
           "<div class='g-fa2'>{{#items}}<details><summary>{{1}}</summary><p>{{2}}</p></details>{{/items}}</div></div></section>",
      css=".g-fs{display:grid;grid-template-columns:1fr 1.4fr;gap:72px;align-items:start}.g-faq-side .g-head-l{margin-bottom:24px}"
          ".g-fa2 details{border-bottom:1px solid var(--g-line)}.g-fa2 details:first-child{border-top:1px solid var(--g-line)}"
          ".g-fa2 summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;gap:20px;padding:20px 0;font-size:16.5px;font-weight:600}"
          ".g-fa2 summary::-webkit-details-marker{display:none}.g-fa2 summary:after{content:'+';font-size:22px;line-height:1;color:var(--g-faint);transition:transform .25s}"
          ".g-fa2 details[open] summary:after{transform:rotate(45deg)}.g-fa2 p{padding:0 0 22px;margin:0;color:var(--g-mute);line-height:1.75}"
          "@media(max-width:820px){.g-fs{grid-template-columns:1fr;gap:32px}}",
      fields=head_fields('还有问题？', '常见问题', '这里找不到的，可以直接问我们。') + [T('button', '按钮', '写信给我们'), T('url', '按钮链接', 'mailto:hi@example.com'), L('items', '问答（一行一个：问题|回答）', FAQ)]),
    S('faq-boxes', '卡片问答', 'faq', looks=FOUR,
      html="<section class='g g-faq-box%K'><div class='g-wn'>" + head() + "<div class='g-fb'>{{#items}}<details class='g-card'><summary>{{1}}</summary><p>{{2}}</p></details>{{/items}}</div></div></section>",
      css=".g-fb{display:flex;flex-direction:column;gap:10px}.g-fb details{padding:0}.g-fb summary{list-style:none;cursor:pointer;padding:20px 24px;font-weight:600;display:flex;justify-content:space-between;gap:16px}"
          ".g-fb summary::-webkit-details-marker{display:none}.g-fb summary:after{content:'';width:22px;height:22px;flex:none;border-radius:50%;background:var(--g-soft) center/10px no-repeat;"
          "background-image:linear-gradient(var(--g-ink),var(--g-ink)),linear-gradient(var(--g-ink),var(--g-ink));background-size:10px 1.6px,1.6px 10px;transition:transform .25s}"
          ".g-fb details[open] summary:after{transform:rotate(45deg)}.g-fb p{margin:0;padding:0 24px 22px;color:var(--g-mute);line-height:1.75}",
      fields=head_fields('帮助', '先看看这里') + [L('items', '问答（一行一个：问题|回答）', FAQ)]),
]
