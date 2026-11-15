# 交叉审查请求：长期记忆第一批（ADR 0006）

- 提交者：Claude
- 审查者：ChatGPT（以及用户）
- 日期：2026-10-24

## 审查范围

| 文件 | 内容 |
|---|---|
| `docs/adr/0006-memory-claim-status-and-coupling-recall.md` | 设计决定 |
| `daemon/codedoctor/memory/notes.py` | 回忆打分、主张状态读取（含取代链）、实体索引写入 |
| `daemon/codedoctor/memory/related.py` | 新：从查询文字找图谱种子实体、沿耦合扩展 |
| `daemon/codedoctor/agents/runtime.py` | 任务开始的回忆改走耦合扩展；任务结束为每个主张写 `claim` 笔记 |
| `daemon/codedoctor/agents/tools.py` | `recall` 工具新增 `follow_coupling`；输出格式加入状态标记和耦合路径 |
| `daemon/codedoctor/store/db.py` | schema v4：`note_entities` 表与升级回填 |
| `schemas/memory/note.schema.json` | 新笔记类型 `claim` + 有效样本 |
| `daemon/codedoctor/agents/orchestration.py`、`agents/daemon.py` | 子任务创建竞态修复 |
| `tests/daemon/test_memory_recall.py` 等 | 测试 |

运行测试：

```bash
.venv/Scripts/python -m pytest
```

## 我希望被重点挑战的地方

1. **打分权重是拍出来的**（主张 +0.2 / −0.3、实体 0.6 / 0.4 / 0.25、摘要 −0.1）。目前只用合成场景验证了排序方向。有没有更好的依据，或者应该做成用户可配置？
2. **被推翻的笔记是降权而不是隐藏**。理由是"已排除的方向"也有价值；风险是小模型可能忽略 `REFUTED` 标记、照样采信。是否应该对 refuted 笔记改写显示方式（例如只显示"已排除：……"）？
3. **种子识别的歧义阈值**（一个词匹配超过 4 个实体就丢弃）和 3 个字符的最短长度：英文常用词（`get`、`save`）可能误匹配同名函数，也可能漏掉真正想问的 `buy`。
4. **扩展深度 2 跳**：浅了会漏掉跨模块耦合，深了会把无关笔记拉进来。对真实大项目是否合适？
5. **只用已建好的图谱**：首次任务前如果从没建过图谱，就没有耦合回忆。是否应该在服务启动时后台构建？
6. **`claim` 笔记只由系统写**：Agent 的 `remember` 不能写这种类型。是否还需要在 `NoteStore.write` 层面强制（目前只靠工具参数枚举限制）？

### 评测数据（补充，2026-10-24）

[评测基准](../../bench/README.md)已经对第 1、2、3 点给出数据（脚本模型，[完整结果](../../bench/results/2026-10-24-scripted-baseline.md)）：

- 第 1 点：本批之前 → 当前，recall@8 从 0.909 到 1.000，MRR 从 0.649 到 0.761。但权重仍是在同一批题上看的，没有留出检验题。
- 第 2 点：被推翻的笔记排在正确笔记前的次数从 1 变成 3。降权不够：被推翻扣 0.3，名字命中加 0.6。
- 第 3 点：种子识别漏掉了接口路径（`/api/session/reconnect`）和状态名（gold），p8 一个种子都没找到。
- 新发现：Agent 用 `remember` 记下的错误结论不会被标"已推翻"，因为 `remember` 不能挂主张。三种配置下都是 3 次未警示。

## 需要 ChatGPT 确认的接口点

- `note_entities` 依赖实体 ID 的**规范写法**（`schemas/claim/entity-ref`）。图谱抽取和主张都已使用同一套 ID；如果你那边的耦合图谱或 UI 生成实体 ID，请保持一致，否则耦合回忆会静默失效。
- `recall` 的 HTTP / 命令行输出新增 `flags`、`via` 字段，桌面程序如需显示请读取这两个字段。

## 已知未做

- 召回内容的长度控制（长摘要仍完整进入提示）——计划与 M5 任务内工作记忆一起做。
- 真实模型下的效果尚未验证：所有测试用脚本模型。
