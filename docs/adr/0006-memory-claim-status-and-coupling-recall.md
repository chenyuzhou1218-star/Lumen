# ADR 0006：长期记忆加强（第一批）——主张状态联动、按主张拆分记忆、沿耦合图回忆

- 状态：提议（待审查）
- 日期：2026-10-24
- 作者：Claude
- 用户要求：重点加强长期记忆和推理逻辑；按 M1 → M3 → M2 的顺序先做记忆第一批。
- 承接：[ADR 0003 长期记忆](0003-long-term-memory.md)（journal + notes 两层结构不变）

## 要解决的问题

| # | 问题 | 后果 |
|---|---|---|
| M1 | 笔记写入时就固定了内容，不知道它引用的主张后来被**推翻**、**撤回**或**过时** | 一个已被证伪的结论会在下一次任务开头被原样召回，看起来和事实一样 |
| M3 | 任务结束只写一条摘要笔记（最终回答的前 6000 字） | 检索时长摘要靠篇幅命中大量查询词，把具体发现挤掉；一条摘要里真假混杂 |
| M2 | 回忆只按任务文字匹配 | 问"结账为什么偶尔失败"时，想不起"扣金币函数没有加锁"——因为问题里没出现钱包，但结账调用了钱包 |

## 决定

### M1：回忆时读取主张的**当前**状态

笔记仍然不可修改（只追加，更正用 `superseded_by`）。真假不写死在笔记里，而是**每次回忆时**去读它引用的主张现在的状态：

| 主张当前状态 | 提示里的标记 | 排序加减分 |
|---|---|---|
| supported | `VERIFIED` | +0.2 |
| proposed | `UNVERIFIED` | 0 |
| needs_revalidation | `STALE (code changed since; re-check before relying on it)` | −0.15 |
| refuted | `REFUTED (disproven; do not rely on it)` | −0.3 |
| withdrawn | `WITHDRAWN by its author` | −0.3 |
| 找不到 | `CLAIM NOT FOUND` | 0 |

- 引用多个主张时取平均分；标记按状态分组列出（每组最多显示 8 个 ID）。
- **被取代（superseded）的主张沿取代链追到最新那条**，用它的状态，并写明"clm_旧 (superseded by clm_新)"。
- 被推翻的笔记**降权但不隐藏**：知道"这个方向已经排除过"本身就是有用的记忆。
- 原有的"引用的代码片段已改动 → POSSIBLY OUTDATED"标记保留，两者并存。

### M3：任务结束时，每个主张单独写一条笔记

- 新增笔记类型 `claim`（`schemas/memory/note.schema.json`）。**只由系统写**：`remember` 工具的 kind 枚举不含 `claim`，Agent 不能自己伪造。
- 内容由系统从主张结构生成，不依赖模型写得好坏：
  - `主张类型 (证据等级): 陈述`
  - `subject -relation-> object`
  - 风险预测的触发条件（含故障模型 ID）
  - 证伪方法
- 实体 = 主张的 subject 和 object；证据 = 主张引用的证据；`claims` = 该主张；`code_version` = 主张的版本。
- 来源（`sources`）精确到**接受这条主张的那次 `tool_result` journal 条目**，找不到时退回到本任务的摘要笔记。
- 只为"本 Agent 在本任务中提交的"主张写笔记；写入失败不会阻止报告发出。
- 笔记本身**不声明真假**——它的可信度完全由 M1 在回忆时读到的主张状态决定。
- 摘要笔记保留（完整性），但排序减 0.1，让具体笔记排在同样命中的长摘要前面。

### M2：沿耦合图谱扩展回忆

新模块 `daemon/codedoctor/memory/related.py`：

1. **找种子**：从查询文字中取标识符、路径、`ent:` ID，映射到图谱实体。
   - 路径（`server/wallet.py`）→ 文件实体，以及该文件定义的符号（最多 30 个）。
   - `file.py#name` → 该文件里的那个符号。
   - 名字（`checkout`、`ShopService.buy`）→ 名字相等或以 `.名字` 结尾的非文件实体。
   - **一个词匹配超过 4 个实体视为歧义，不用**，免得常见词把半个项目拉进来。
2. **扩展**：从每个种子沿图谱上下游各走 **2 跳**（复用 `Graph.reach`，规则与影响分析一致：不跟随 ambiguous 的名字匹配边），最多 200 个实体。
3. **检索**：新表 `note_entities(entity, note_rowid)`（数据库 schema v4，旧库升级时自动回填），按实体精确查找笔记。
4. **打分**：实体分按距离 0 / 1 / 2 跳 = 0.6 / 0.4 / 0.25，与文字命中分相加。
5. **可解释**：经耦合关系召回的笔记附上路径，例如
   `(recalled through coupling: affected by 'checkout': checkout -calls-> spend_gold)`。

边界：
- **只用已经建好的图谱，回忆本身不会触发图谱构建**；图谱不可用时退回纯文字检索。
- 图谱里由主张推出的边（inferred / verified）也会被跟随，并在路径里标出来源。
- `recall` 工具新增 `follow_coupling` 参数（默认 true）；任务开始时的自动回忆、HTTP API、命令行都走同一个函数。API / 命令行的结果新增 `flags` 与 `via` 字段。

### 打分公式（汇总）

```
score = 查询词命中比例
      + 实体分（0.6 / 0.4 / 0.25，按耦合距离）
      + 主张分（按引用主张的当前状态取平均）
      + 0.25（置顶）
      − 0.1（摘要笔记）
```

## 顺带修复：创建子任务的竞态

`delegate` 在线程里运行，先发任务消息、再写任务行。Worker 在事件循环上可能在这两步之间就收到消息并写入同一行（`_begin_task`），随后创建方的 INSERT 报 `UNIQUE constraint failed: tasks.id`，调度首脑的任务以 "Internal error" 失败。这个竞态原来就存在，这次加入的回忆步骤改变了时序，使它在完整测试中偶发出现。修复：`create_subtask` 和 `submit_task` 的 INSERT 改为 `ON CONFLICT(id) DO NOTHING`（Worker 已写入的行就是当前状态）。新增确定性测试复现该时序。

## 不在本批

- M5 任务内工作记忆、M4 记忆整理（去重 / 冲突标记）、M6 向量检索（需要用户指定嵌入模型）。
- 推理批次 R1–R4。
- 召回结果的长度控制：长摘要仍会完整进入提示，等 M5 一起处理。

## 测试

- `tests/daemon/test_memory_recall.py`（12 项）：状态标记随主张升级 / 推翻变化、被推翻笔记排在后面但仍可见、取代链追踪、找不到的主张、摘要降权、沿下游 / 上游召回及路径文字、距离排序、文件路径作种子、无图谱时不构建、歧义词不作种子、深度限制、v3 → v4 回填。
- `tests/daemon/test_agent.py`：端到端验证主张笔记的实体、证据、证伪文字、来源指向 `submit_claim` 的 tool_result，以及后来的读者看到 `UNVERIFIED`。
- `tests/daemon/test_cluster.py`：子任务竞态。
- 全部 424 项通过，连续 3 次完整运行无失败。
