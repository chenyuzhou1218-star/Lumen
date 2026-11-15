# 证据协议 v0

状态：**草案，待交叉审查**　|　负责人：Claude　|　Schema：`schemas/evidence/`

本协议定义证据的身份、存储记录、引用方式，以及**如何验证一条证据真的支持某个结论**。

---

## 1. 证据 ID

格式：`ev:<kind>:<locator>`。种类是封闭集合：

| kind | 格式 | 说明 |
|---|---|---|
| `span` | `ev:span:<trace_id>/<span_id>` | |
| `trace` | `ev:trace:<trace_id>` | |
| `action` | `ev:action:<cd.action.id>` | 组装后的动作生命周期 |
| `code` | `ev:code:<版本>:<路径>[#<符号>]@<内容sha256>[:L<起>[-L<止>]]` | 见下 |
| `log` | `ev:log:<日志快照sha256>:L<起>[-L<止>]` | |
| `test` | `ev:test:<运行ULID>/<测试名>` | 也用于复现和故障注入运行 |
| `blob` | `ev:blob:<sha256>` | 截图、载荷、文件快照 |
| `db` | `ev:db:<ULID>` | 查询结果或表结构快照 |
| `gap` / `corr` / `health` / `coverage` | `ev:<kind>:<ULID>` | 事件协议中的记录 |

**代码证据的锚定方式**：版本（40/64 位 commit，或未提交工作区的 `wt-<sha256>`）+ 仓库相对路径 + 符号 + **被引用内容的哈希**。代码修改后行号会漂移，但"版本 + 符号 + 内容哈希"仍能找回原位置，也能判断内容是否已变化。

保留字符（路径和名称中的 `:` `#` `@` `/`、空白、`%`）一律百分号编码。路径不允许盘符、开头斜杠或 `..`。

**ID 格式正确只说明格式正确，不说明证据存在，更不说明证据支持结论。**

## 2. 证据记录（`evidence/evidence-record`）

每条证据在注册表中有一条记录，原始字节存在内容寻址存储中（写入后不可修改）：

| 字段 | 作用 |
|---|---|
| `content.sha256` | 完整性校验：重新计算哈希并比较 |
| `binding` | 这条证据属于哪个代码版本、trace、动作、服务、环境、时间范围 |
| `provenance` | 来源（probe / ingest / tool / agent / user / import / system）、采集组件、探针 ID、Agent ID、工具调用 ID |
| `data_class` | 敏感级别：public / internal / confidential / secret / local_only |
| `redaction` | 是否已遮蔽、按哪个策略、遮蔽了哪些字段 |
| `content_trust` | `untrusted` 或 `system_computed` |

Schema 强制：
- `kind` 必须与 ID 前缀一致。
- span / trace 必须绑定 `trace_id`；code / test 必须绑定 `code_version`；action / gap 必须绑定 `action_id`。
- 来源为 probe 时必须写明 `probe_id`；来源为 agent / tool 时必须写明 `agent_id`。
- `secret` 级别的证据必须已遮蔽。

### 提示注入防护

**span、trace、code、log、test、blob、db 七类原始外部内容，`content_trust` 只能是 `untrusted`**，无论是谁采集的。规则：

> untrusted 内容是数据，不是指令。不管日志、代码注释、数据库内容、网页里写了什么（"忽略之前的指令"、"请执行……"），Agent 都不能把它当作命令执行。

这条规则的执行在 Agent 运行时（提示词构造时必须把 untrusted 内容放在明确的数据区，并标注来源）。协议层保证每一条证据都带着这个标签，运行时没有理由"不知道"。

## 3. 证据引用（`evidence/evidence-ref`）

主张引用证据时写：

```json
{
  "id": "ev:span:4bf9.../f1b2...",
  "role": "supports",
  "shows": "点击购买后 1 秒内界面没有变化",
  "assert": [{ "op": "attr_equals", "attr": "cd.ui.settle.result", "value": "no_change" }],
  "expect_binding": { "code_version": "9fce...", "trace_id": "4bf9...", "action_id": "01JB..." },
  "locator": { "line_start": 47, "line_end": 49 }
}
```

- `role`：supports / refutes / context。
- `shows`：作者的文字说明（untrusted，只显示，不执行）。
- `assert`：**机器可检查的断言**，见第 4 节。
- `expect_binding`：作者认为这条证据属于哪个版本 / trace / 动作。省略时用主张的 `scope` 比较。**引用旧版本证据（比如分析历史回归）必须显式写出旧版本**，避免无意中混用不同版本的证据。

## 4. 断言（`evidence/predicate`）

一个小的封闭断言语言，每条断言只针对一条证据：

| op | 适用 | 例子 |
|---|---|---|
| `exists` | 全部 | |
| `attr_equals` / `attr_in` / `attr_absent` | span | `cd.ui.settle.result == no_change` |
| `status_is` | span | `error` |
| `duration_ms` | span | `gt 3000` |
| `field_equals` | JSON 记录（action、gap、corr、health、coverage、db） | JSON Pointer + 值 |
| `text_contains` / `text_matches` | log、code、文本 blob | 正则仅限 RE2 子集（线性时间，防止恶意正则卡死校验器） |
| `test_outcome` | test | `failed` |
| `gap_verdict` | gap | `confirmed_absent` |

**边界说明**：断言证明的是"证据确实显示了作者说的内容"，**不证明结论正确**。例如可以机器验证"日志里确实有 ECONNRESET"，但"ECONNRESET 导致了扣款失败"是因果结论，需要通过干预实验复现（见主张协议）。

## 5. 四级校验（审查意见 4）

`evidence/validation-result` 是校验器对一条主张的输出，**由校验器生成，作者不能自己写**。每条被引用的证据检查四级：

| 级别 | 检查内容 | 结果 |
|---|---|---|
| 1. `exists` | 注册表中有这条记录 | pass / fail |
| 2. `integrity` | 存储的字节重新哈希后与 `content.sha256` 一致 | pass / fail / skipped |
| 3. `binding` | 记录的版本 / trace / 动作 / 服务 / 环境与主张 `scope` 及 `expect_binding` 一致 | pass / fail / not_checked / skipped |
| 4. `support` | 证据确实支持主张 | machine_verified / independently_verified / unverified / contradicted / inapplicable / skipped |

`support` 的取值：
- `machine_verified`：所有断言求值为 true（Schema 强制：至少一条断言，且全部为 true）。
- `independently_verified`：另一个 Agent 审查确认，必须写明审查者 ID 和审查消息 ID（`schemas/agent` 的审查消息）。**审查者不能是作者**（跨文档规则，由校验器检查）。
- `unverified`：没有断言，也没有独立审查。
- `contradicted`：至少一条断言为 false。
- `inapplicable`：断言不适用于该证据种类（比如对日志用 `attr_equals`）。

总体结论：
- `accepted`：所有证据通过 1–3 级，**所有 supports 证据**的支持已验证。
- `accepted_support_unverified`：1–3 级通过，但有 supports 证据未能验证支持。可以展示，**不能作为已确立事实**。
- `rejected`：有证据不存在、被篡改、版本或事件不匹配，或 supports 证据被反驳。

Schema 强制：前一级失败，后续级别为 skipped；binding 失败必须列出不匹配字段（期望值和实际值）；任何 1–3 级失败或 supports 证据被反驳，总体只能是 rejected。

## 6. 尚未实现的部分

本次交付的是协议和参考校验（Schema + 语义规则）。**真正读取注册表、重新哈希、求值断言的证据校验器**属于 `daemon/codedoctor/evidence/`，计划在第一轮开发中实现。
