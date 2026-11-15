# 事件协议 v0（跨服务事件追踪）

状态：**草案，待交叉审查**　|　负责人：Claude　|　Schema：`schemas/event/`

本协议定义 Code Doctor 如何表示"一次用户操作在整个系统里发生了什么"，以及如何判断某一环"真的没发生"还是"只是没采集到"。

---

## 1. 总体模型

```
SDK / 探针 ──OTLP──▶ ingest（规范化）──▶ span 记录（event/span）
     │                                        │
     ├─ 覆盖声明（event/coverage）            ▼
     └─ 健康报告（event/telemetry-health）   动作组装 ──▶ 动作生命周期（event/action）
                                              │            ▲
                                              │            └─ WS 关联（event/ws-correlation）
                                              ▼
                       链路模板（event/chain-template）──▶ 断点判定（event/gap-assessment）
```

- **SDK 只发标准 OTLP**，加上 `cd.*` 属性。不自创传输协议。
- **ingest 负责规范化**：旧属性名映射、ID 小写化、时间统一为十进制字符串、敏感字段兜底遮蔽。下游只读规范化后的记录。
- **分析的基本单位是"动作"（action），不是 trace。** 一次操作可能跨越多条 trace。

## 2. 一次操作 ≠ 一条 trace（审查意见 1）

`cd.action.id`（ULID）在 `ui.action` 根 span 上生成，通过以下方式传到下游：

| 场景 | 关联方式 | `joined_by` | 强度 |
|---|---|---|---|
| 普通 HTTP | 同一 trace 的父子关系 | `root` | exact |
| 下游另起 trace，但带了 W3C baggage | baggage 中的 `cd.action.id` | `baggage_action_id` | exact |
| 异步任务、重连、重试 | span link（`continues_action` / `retry_of` / `reconnect_of`） | `span_link` / `job_link` | exact |
| WS 消息里带了 trace 上下文 | 封包字段 | `ws_envelope` | exact |
| WS 消息用应用自己的消息 ID / 序号 | 适配器 | `ws_adapter` | 由关联记录决定 |
| WS 消息无法修改（二进制等） | 原始帧字节的 sha256 | `ws_digest` | 由关联记录决定，通常 probabilistic |

规则（Schema 强制）：
- 通过传播上下文建立的关联（root、baggage、span link、envelope、job link）**必须是 exact**。
- 非 root 关联**必须引用证据**（`via`）；`ws_adapter` / `ws_digest` 关联**必须引用 ws-correlation 记录**。
- 每个动作**恰好一个** root trace。

动作状态：`open`（仍在收集）/ `settled`（有 `ui.settle` 收尾）/ `timed_out` / `abandoned`（客户端提前离开）。

## 3. WebSocket 兼容已有应用（审查意见 5）

`cd.ws.correlation.method` 四种方式，**只有 `envelope` 需要修改消息格式，且必须由项目主动开启**：

| 方式 | 是否修改协议 | 适用 | 记录要求 |
|---|---|---|---|
| `envelope` | 是（opt-in） | 允许额外字段的 JSON 协议 | 接收端有真实 parent |
| `adapter` | 否 | 协议里本来就有消息 ID / 序号（多数游戏协议都有） | `cd.ws.msg.key` 必填 |
| `digest` | 否 | 二进制帧、不能改格式的系统 | `cd.ws.msg.digest` + `cd.ws.msg.size` 必填 |
| `none` | 否 | 无法关联 | 下游断点只能判为 unknown |

`event/ws-correlation` 记录一次匹配：
- 窗口内**多于一个候选**时，强度**只能是 probabilistic**。
- exact → 证据等级 `observed`；probabilistic → **只能是 `inferred`**。
- 这样，相同内容的帧（比如心跳）造成的歧义不会被当成观测事实。

## 4. "没发生"与"没采集到"（审查意见 2，核心规则）

断点判定（`event/gap-assessment`）对**一个动作的一个预期阶段**给出五种结论之一：

| verdict | 含义 | conclusive |
|---|---|---|
| `present` | 找到了匹配的 span | ✅ |
| `confirmed_absent` | 没找到，**且所有采集丢失途径都已排除并有证据** | ✅ |
| `not_instrumented` | 这一层 / 这个路由没有探针覆盖 | ❌ |
| `telemetry_degraded` | 探针、采集器或 ingest 有问题，可以解释缺失 | ❌ |
| `unknown` | 没找到，但至少有一项检查无法判定 | ❌ |

**只有 conclusive 的结论可以作为程序行为的事实使用。** 其余三种在界面上显示为"缺少观测证据"或"观测系统异常"。

`confirmed_absent` 必须同时满足 11 项检查（Schema 强制，任何一项 `unknown` 都不行）：

| 检查 | 要求 | 必须附证据 |
|---|---|---|
| `template_confirmed` | 链路模板经用户确认（AI 推测的模板可能是错的） | — |
| `coverage_declared` | 覆盖声明覆盖该层、该服务、该路由/表，且覆盖整个窗口 | ✅ coverage |
| `probe_alive` | 窗口内心跳连续，序号无跳跃 | ✅ health |
| `sampled` | 该 trace 在这一层被采样（always_on / 父采样 / 有采样决策记录） | ✅ |
| `exporter_healthy` | 窗口内无导出失败，窗口后有一次成功导出 | ✅ health |
| `no_drops` | `spans_dropped = 0` 且队列未满 | ✅ health |
| `collector_healthy` | 采集器无丢弃/拒绝（无采集器时可为 not_applicable） | ✅ health |
| `ingest_complete` | ingest 水位线已越过窗口终点 | ✅ health |
| `context_propagated` | 上游阶段存在，且 `cd.propagation.injected=true`，下游无解析失败 | ✅ span |
| `window_elapsed` | 截止时间 + 最大刷新延迟已过，不会再有迟到的 span | — |
| `clock_skew_bounded` | 主机间时钟偏差相对窗口足够小 | — |

其他约束：
- `telemetry_degraded` 必须指出至少一项失败的遥测检查。
- `not_instrumented` 的 `coverage_declared` 必须是 `fail`。
- 非 `present` 的结论不能列出匹配 span。

为了支撑这些检查，探针必须提供：
- **覆盖声明**（`event/coverage`）：覆盖哪些层、哪些路由/消息/表（`all` 或 `listed`），采样策略（ratio 必须写明比例；是否记录每个 trace 的采样决策），导出队列参数，心跳间隔，传播器，遮蔽策略。
- **健康报告**（`event/telemetry-health`）：窗口内的 started / exported / dropped / not_sampled / 导出失败 / 解析失败计数，队列峰值，心跳序号，时钟偏差；ingest 额外报告水位线。

## 5. 链路模板

`event/chain-template` 描述一个业务流程"应该"经过哪些阶段（层、匹配条件、是否必需、前置阶段、截止时间）。

- `source` 可以是 `user` / `inferred_from_code` / `learned_from_traces` / `agent_proposed`。
- `source = user` 时必须 `confirmed_by_user = true`。
- **未确认的模板可以使用，但基于它的缺失判断永远不会是 conclusive**（通过 `template_confirmed` 检查实现）。

## 6. Span 规范化形式

`event/span` 的必填字段：`trace_id`、`span_id`、`name`、`cd_kind`、`otel_kind`、起止时间、`status`、`service`、`probe_id`、`attributes`。

`cd_kind` 决定必填属性：

| cd_kind | 必填属性 |
|---|---|
| `ui.action` | `cd.action.id`, `cd.action.type` |
| `ui.settle` | `cd.action.id`, `cd.ui.settle.result`, `cd.ui.settle.observer` |
| `http.client` | `http.request.method`, `cd.propagation.injected` |
| `http.server` | `http.request.method`, `http.route` |
| `handler` | `code.function.name`, `code.file.path` |
| `db` | `db.system.name` |
| `ws.send` / `ws.recv` | `cd.ws.connection.id`, `cd.ws.correlation.method`（及对应方式的字段） |
| `job.enqueue` / `job.run` | `cd.job.id` |

**源码属性使用现行 OTel 语义约定（审查意见 3）：** `code.file.path`、`code.function.name`、`code.line.number`、`code.column.number`。旧名 `code.filepath` / `code.function` / `code.lineno` / `code.namespace` 以及 `db.system` **只允许出现在 SDK 输出中**，ingest 负责映射并设置 `cd.compat.legacy_code_attrs=true`；规范化记录里出现旧名直接校验失败。

数据库 span 用 `cd.db.reads` / `cd.db.writes`（`表.字段`）和 `cd.db.tx.id` 描述读写，这是耦合图"数据边"的来源。

## 7. 安全（从第一天建立）

- **属性名必须小写**，这样敏感键检测才可靠。
- 名称中含 `password`、`passwd`、`secret`、`token`、`api_key`/`apikey`、`authorization`、`cookie`、`set-cookie`、`session_id`、`private_key`、`credential` 的属性，**值只能是遮蔽占位符**：
  - `cd:redacted`：完全丢弃；
  - `cd:redacted:hmac:<hex>`：按项目密钥计算的 HMAC，可以比较"两次请求是否用了同一个 token"，但不暴露原值。
- 不误伤：`gen_ai.usage.input_tokens`、`max_tokens`、`session.id`（OTel 的会话标识）可以保留原值（有测试覆盖）。
- 默认**不采集请求/响应/消息正文**（`redaction.captures_bodies = false`）。
- span 带 `data_class`，供模型路由策略（`schemas/config`，由 ChatGPT 负责）判断能否发给云端模型。

## 8. 时间与 ID

- 时间：Unix 纳秒，**十进制字符串**（JSON 数字超过 2^53 会丢精度）。
- trace/span ID：小写十六进制，不能全为 0。
- 动作、记录 ID：Crockford base32 ULID。探针 ID：`prb_<ULID>`。

## 9. Schema 无法表达、由语义规则检查的内容

见 `tools/protocol/semantic.py`：span 结束不早于开始、不能以自己为父、span 事件在 span 时间范围内、窗口顺序、动作 ID 与记录 ID 一致、root trace 与根 span 一致、同一 trace 不重复列出、模板阶段只能依赖更早的阶段、WS 关联的发送端和接收端不能是同一个 span。

## 10. 已知未覆盖（v0 之后）

- 跨文档一致性（动作中 `ws_digest` 关联的强度必须等于关联记录的强度、span 的 `probe_id` 必须有对应覆盖声明）由 ingest / 证据校验器实现，不在 Schema 层。
- 游戏客户端的渲染循环观测（`render_loop_hook`）只定义了枚举值，具体判定方法待 SDK 设计。
- RPC（gRPC 等）只有 `layer: rpc`，尚无专门的 `cd_kind`。
