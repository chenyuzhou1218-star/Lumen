# ADR 0001：协议 v0 的基础决定

- 状态：提议（待 ChatGPT 审查、用户批准后改为"已接受"）
- 日期：2026-10-24
- 作者：Claude

## 背景

事件、证据、主张三份协议是三大核心共同的底层。后端、SDK、Agent、前端开始并行开发之前，需要先冻结它们。

## 决定

1. **JSON Schema draft 2020-12** 作为唯一契约来源。`$id` 统一为 `https://code-doctor.local/schemas/v0/<路径>`（只是标识符，不会联网）。Python / TS 类型由 Schema 生成，不手写。
2. **每个顶层记录带 `cd_schema` 版本标签**（如 `cd.event.span/0`），嵌入片段（evidence-ref、predicate）不带。
3. **OpenTelemetry 是传输层，Code Doctor 定义规范化存储形式。** SDK 只发 OTLP + `cd.*` 属性。
4. **分析单位是"动作"，不是 trace。** 用 `cd.action.id` + span link + WS 关联把多条 trace 组成一个动作。
5. **缺失判定默认是"不知道"。** 只有 11 项遥测检查全部通过并附证据，才能得出 `confirmed_absent`。
6. **证据校验分四级**（存在、完整、绑定、支持），并且支持级别要求机器断言或独立审查。
7. **主张是陈述事实的唯一方式**，使用规范实体 ID 和封闭关系词表，让耦合图可以机械合并。
8. **安全规则在协议层强制**：敏感属性键只能存遮蔽值；原始外部内容一律标记 untrusted；记录带数据级别。
9. **语义规则单独实现**（`tools/protocol/semantic.py`），作为 daemon 实现的参考，测试中与 Schema 一起执行。

## 对用户审查意见的处理

| 审查意见 | 处理 | 位置 |
|---|---|---|
| 1. 一次操作不总是一条 trace | 增加 `cd.action.id`、span link 关系、动作生命周期记录（多 trace，带关联方式与强度） | `event/action`、`event/span#/$defs/link` |
| 2. 有探针但没 span 不能直接判为中断 | 断点判定五种结论；`confirmed_absent` 需要采样、导出、丢弃、队列、采集器、ingest、上下文传播等 11 项检查全部通过并附证据；新增覆盖声明、健康报告 | `event/gap-assessment`、`event/coverage`、`event/telemetry-health` |
| 3. 使用现行 OTel 源码属性名 | 规范化记录只允许 `code.file.path` / `code.function.name` / `code.line.number`，旧名出现即失败，由 ingest 映射 | `event/span` |
| 4. 证据 ID 存在 ≠ 证据支持结论 | 四级校验 + 机器断言语言 + 期望绑定 + 独立审查记录 | `evidence/*` |
| 5. WS 扩展必须兼容已有应用 | envelope 改为 opt-in；新增不改协议的 adapter 和 digest 方式；模糊匹配只能是 inferred | `event/ws-correlation`、`event/span` |
| 三、安全边界 | 敏感键强制遮蔽、默认不采集正文、untrusted 标记、数据级别 | `common/defs`、`evidence/evidence-record` |

## 后果

- 好处：下游（耦合图、推演、报告）可以直接依赖这些结构；"把采集缺失误判为 Bug"在 Schema 层就被阻止。
- 代价：探针必须报告覆盖声明和健康计数，SDK 工作量比"只发 span"大。这是有意的。
- 风险：规则较严，早期很多断点会显示为 `unknown`。这是正确行为，界面需要把"缺少观测证据"和"缺少哪项检查"说清楚，引导用户补齐探针。
