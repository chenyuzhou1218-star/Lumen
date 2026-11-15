# 交叉审查请求：协议 v0（事件 / 证据 / 主张）

- 提交者：Claude
- 审查者：ChatGPT（以及用户）
- 日期：2026-10-24

## 审查范围

| 文件 | 内容 |
|---|---|
| `schemas/common/defs.schema.json` | 共享类型：ID、时间、路径、数据级别、证据等级、属性映射（含敏感键规则）、模型身份 |
| `schemas/event/*.schema.json` | span、动作、覆盖声明、遥测健康、WS 关联、链路模板、断点判定 |
| `schemas/evidence/*.schema.json` | 证据 ID、证据记录、证据引用、断言、校验结果 |
| `schemas/claim/*.schema.json` | 实体 ID、主张 |
| `schemas/*/fixtures/{valid,invalid}/` | 114 个样本，每个无效样本都写明它**应该因为什么失败** |
| `tools/protocol/semantic.py` | Schema 无法表达的语义规则（参考实现） |
| `tests/protocol/test_schemas.py` | 自动测试 |
| `docs/protocol/*.md` | 协议说明 |
| `docs/adr/0001-protocol-v0-foundations.md` | 设计决定与对审查意见的处理 |

运行测试：

```bash
python -m pytest
```

## 需要 ChatGPT 确认的接口点

这些字段由我的协议引用，但定义属于 `schemas/agent` / `schemas/config`：

1. **Agent 角色名称集合**：`claim.author.role` 目前只要求 `^[a-z][a-z0-9_]{0,63}$`。建议你定义枚举（head_logic、head_dispatch、worker、guardian、investigator……），我改为引用。
2. **任务 ID、审查消息 ID 格式**：`claim.author.task_id`、`validation-result.refs[].verified_by.review_id` 目前是自由字符串（≤128）。请给出格式，我改为引用你的定义。
3. **端点配置 ID**：`modelIdentity.endpoint_profile` 指向用户配置里的端点配置，**只存 ID，不存 API Key / Base URL**。请确认你的 config 用同样的 ID。
4. **数据级别路由**：`dataClass`（public / internal / confidential / secret / local_only）。请在 config 中定义"哪个级别允许发给哪个端点"，并确认 `local_only` 永远不发往非本地端点。
5. **untrusted 内容进入提示词的方式**：协议给每条证据打了 `content_trust` 标签。Agent 运行时如何把 untrusted 内容和指令隔离，属于你的部分，请在 Agent ADR 中写明。

## 我希望被重点挑战的地方

1. **`confirmed_absent` 的 11 项检查是否过严或缺项？** 例如：是否需要单独的"进程未崩溃 / 未重启"检查（目前隐含在 `probe_alive` 的心跳连续性里）。
2. **`causes` 不能是 observed** 这条规则是否会妨碍某些合理场景？
3. **断言语言是否够用？** 目前没有跨两条证据的断言（例如"span A 早于 span B"），这类关系我认为应该是主张而不是断言，但欢迎反驳。
4. **敏感键正则**是否有误伤或漏网（测试里列了正反例）。
5. **实体 ID 格式**是否足够让你的耦合引擎直接用作图节点 ID。

## 已知限制

- 跨文档规则（审查者不能是作者、动作关联强度必须等于关联记录强度、span 的 `probe_id` 必须有覆盖声明）不在 Schema 层，需要证据校验器和 ingest 实现。
- 断言求值器、证据注册表、ingest 都还没写，这次只交付协议。
- 测试环境：Python 3.14 + jsonschema 4.26；尚未在 TS 侧生成类型并验证。
