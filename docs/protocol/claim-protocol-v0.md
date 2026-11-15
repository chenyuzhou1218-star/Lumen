# 结构化主张协议 v0

状态：**草案，待交叉审查**　|　负责人：Claude　|　Schema：`schemas/claim/`

主张（claim）是 Agent、用户或确定性组件**陈述任何事实、假设或风险的唯一方式**。耦合分析、因果判断、未来故障推演都直接读写主张，不需要重新定义数据结构。

---

## 1. 结构

```json
{
  "cd_schema": "cd.claim/0",
  "id": "clm_01JB...",
  "claim_type": "finding",
  "author": { "kind": "agent", "id": "worker-backend", "role": "worker",
              "model": { "provider": "ollama", "model": "qwen3-coder:30b", "endpoint_profile": "local-ollama" },
              "task_id": "task_01JB8Z" },
  "statement": {
    "text": "点击购买能到达 ShopService.buy，但 orders 表的 INSERT 从未发生，界面也没有变化。",
    "subject": "ent:stage:shop.buy/db-write",
    "relation": "absent_in",
    "object": { "value": "01JB8Z4K3M5N6P7Q8R9S0T1V2W" }
  },
  "evidence_level": "observed",
  "scope": { "code_version": "9fce...", "action_ids": ["01JB..."], "services": ["shop-web", "shop-api"] },
  "evidence": [ /* evidence-ref，见证据协议 */ ],
  "status": "proposed"
}
```

完整例子见 `schemas/claim/fixtures/valid/`。

## 2. 四种主张类型

| 类型 | 用途 | 额外要求 |
|---|---|---|
| `finding` | 关于当前系统的事实 | — |
| `hypothesis` | 待检验的候选解释 | 必须有 `falsification` |
| `risk_prediction` | 尚未发生、但在给定条件下可能发生的故障（**核心 3：未来 Bug 推演**） | 必须有 `falsification` 和至少一个 `conditions`；证据等级不能是 observed |
| `fix_verification` | 修复已应用并重新测试 | 证据等级必须是 reproduced |

`conditions` 可以引用故障模型库的 ID（如 `fm:duplicate_request`、`fm:response_lost_after_commit`），推演引擎和测试生成器据此选择注入方式。

## 3. 实体 ID：让不同 Agent 的发现能自动拼接

`subject` / `object` 使用规范实体 ID `ent:<type>:<key>`：

| 类型 | 格式 | 例子 |
|---|---|---|
| service | `ent:service:<服务>` | `ent:service:shop-api` |
| route | `ent:route:<服务>:<方法>:<模板路径>` | `ent:route:shop-api:POST:/api/shop/buy` |
| symbol | `ent:symbol:<服务>:<路径>#<限定名>` | `ent:symbol:shop-api:server/shop.py#ShopService.buy` |
| file | `ent:file:<服务>:<路径>` | |
| table / column | `ent:table:<库>:<表>` / `ent:column:<库>:<表>.<字段>` | `ent:column:main:players.gold` |
| state | `ent:state:<服务>:<存储>/<键>` | 前端 store、游戏状态字段、缓存键 |
| ws_msg / job | `ent:ws_msg:<服务>:<类型>` / `ent:job:<服务>:<名称>` | |
| ui | `ent:ui:<服务>:<组件或选择器>` | |
| external | `ent:external:<主机>[:端口]` | 第三方 API |
| invariant | `ent:invariant:<名称>` | `ent:invariant:gold-conservation`（业务守恒规则） |
| stage | `ent:stage:<模板>/<阶段>` | `ent:stage:shop.buy/db-write` |

路由统一用 `{id}` 风格的模板路径，Express 的 `:id` 由 ingest 规范化。

**设计意图**：前端 Worker 说"按钮触发 `ent:route:shop-api:POST:/api/shop/buy`"，数据库 Worker 说"`ent:symbol:...#ShopService.buy` writes `ent:column:main:players.gold`"，两条主张通过相同的实体字符串**被程序直接合并**成耦合图，不需要模型读文字。

## 4. 关系词表

封闭集合（扩展用 `x-` 前缀，内置分析忽略扩展关系）：

- 结构：`calls`、`handles`、`reads`、`writes`、`emits`、`consumes`、`triggers`、`renders`、`depends_on`、`shares_state_with`、`precedes`
- 观测：`present_in`、`absent_in`、`fails_with`、`violates`
- 因果：`causes`、`may_cause`、`affects`
- 修复：`fixed_by`

## 5. 证据等级规则（Schema 强制）

| 等级 | 规则 |
|---|---|
| `observed` | 至少一条 supports 证据是运行时证据（span / trace / action / log / db / gap / corr / blob）。**只引用代码不算 observed**：读代码不等于观察运行。 |
| `reproduced` | 至少一条 supports 证据是测试 / 复现运行（`ev:test:`） |
| `inferred` | 必须依赖其他主张（`depends_on`）或至少一条 supports 证据 |
| `speculated` | 可以没有证据，但**永远不能被标记为 supported** |

因果规则：
- **`causes` 永远不能是 observed**。因果关系不能被直接观察到，只能推断，或通过干预实验复现。
- `causes` + `reproduced` 时，`falsification.method` 必须是 test / fault_injection / replay，并且 `intervention = true`。"再观察一次"不算证明因果。

## 6. 刻意不包含的字段

- **没有数值 `confidence` 字段**。模型自报的置信度不是证据，加了只会让人误以为 0.97 有意义。可信度由证据等级 + 校验结果表达。Schema 用 `additionalProperties: false` 拒绝这个字段。
- **作者不能写校验结果**。`supported` / `refuted` 状态在校验和审查之后才设置。

## 7. 与 Agent 协议（ChatGPT 负责）的接口点

| 字段 | 依赖 `schemas/agent` 或 `schemas/config` 的定义 |
|---|---|
| `author.role` | 角色名称集合（head_logic、head_dispatch、worker、guardian、investigator……） |
| `author.task_id` | 任务 ID 格式 |
| `author.model.endpoint_profile` | 用户配置中的端点配置 ID（**不包含 API Key 和 Base URL**） |
| validation-result `verified_by.review_id` | 审查消息 ID 格式 |
| `data_class` | 模型路由策略按此判断能否发给某个模型 |

`author.model` 只记录"是哪个模型产出的"，用于追溯和对照实验。**协议从不选择模型**，这由用户在配置中逐个 Agent 指定。

## 8. 语义规则

见 `tools/protocol/semantic.py`：主张不能依赖自己、不能取代自己、subject 和 object 不能是同一个实体。
