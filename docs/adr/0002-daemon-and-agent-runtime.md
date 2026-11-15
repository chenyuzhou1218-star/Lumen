# ADR 0002：后台服务与基础 Agent 运行时

- 状态：提议（待 ChatGPT 审查、用户批准）
- 日期：2026-10-24
- 作者：Claude（按用户指示先实现基础 Agent 功能；原计划这部分由 ChatGPT 负责，现改为由 ChatGPT 审查）

## 背景

用户要求先把"一个 Agent 的基础功能"做扎实：Agent 通信、后台系统架构、长期记忆，然后再做耦合分析。

## 决定

### 1. 后台独立运行

`codedoctor serve` 是一个独立进程（FastAPI + uvicorn，默认只监听 127.0.0.1）。桌面界面、命令行、脚本都只是它的客户端，关闭界面不影响后台。

```
daemon/codedoctor/
  config.py          项目配置（逐 Agent 模型由用户指定）
  services.py        打开一个项目所需的全部组件
  store/             SQLite（WAL）+ 内容寻址 blob 存储
  evidence/          证据注册表（代码片段、命令输出）
  memory/            长期记忆：journal（完整日志）+ notes（可检索笔记）
  models/            模型适配：OpenAI 兼容 / Anthropic / 脚本模型
  agents/bus.py      消息总线
  agents/runtime.py  Agent 运行时
  agents/tools.py    工具
  agents/daemon.py   调度所有 Agent 的循环
  claims.py          主张存储（拒绝伪造证据）
  api.py / cli.py    HTTP API 与命令行
```

### 2. Agent 通信：只有一条通道

所有 Agent、用户、系统之间的交流都是 `schemas/agent/message` 消息，经过校验后永久存储在 `messages` 表，按顺序投递。没有任何"私下"通道，所以任何对话都能完整回放。

- 消息类型：task、report、question、answer、review_request、review、escalation、control。
- 只有用户或系统能发 control（暂停、恢复、取消任务、停止）。
- 审查（review）只有三种结论：反例、已复验、证据不足；前两种必须附证据。

### 3. 没有消息就不调用模型

每个 Agent 一个循环：收件箱为空时等待事件（附带超时轮询，以发现其他进程写入的消息），**不调用模型**。有测试验证空闲期间模型调用次数为 0。

### 4. 单个任务的执行循环

```
回忆长期记忆 → 调用用户指定的模型 → 执行工具 → 结果回填 → 重复
```

停止条件（全部会写入 journal）：

| 条件 | 结果 |
|---|---|
| 模型给出不调用工具的最终回答 | `done` |
| 步数或 token 达到预算 | `budget_exhausted` |
| 连续 N 步没有新信息（成功且未重复的工具调用） | `stalled`（思考有效性检查） |
| 用户取消（立即生效于运行中的任务） | `cancelled` |
| 模型不可用且没有用户配置的备用模型，或数据级别不允许发送 | `blocked` + 发 escalation 给用户 |
| 内部异常 | `failed`（请求者一定会收到报告） |

### 5. 模型选择完全由用户决定

- 每个 Agent 的主模型和备用列表都写在配置里。
- 主模型失败：可重试错误（超时、429、5xx）在**同一模型**上重试一次；仍失败则**只按用户配置的备用列表**切换，并记录 `model_switch`（注明"按用户配置"）。
- 没有配置备用模型：Agent 停下并通知用户，**绝不自行换模型**。
- API Key 不写入配置文件，配置只写环境变量名；变量未设置时不发送任何请求。

### 6. 数据级别

每个端点有 `max_data_class`（远程默认 internal，本地默认 local_only）。项目代码的级别由 `project.code_data_class` 决定。任务上下文的级别取读到的所有内容中最严格的；**发送前检查**，不允许就不发送，任务以 `blocked` 结束。

### 7. 工具（基础模式）

| 工具 | 说明 |
|---|---|
| `list_dir` / `search_text` | 浏览和搜索，不能离开项目根目录 |
| `read_file` | 读取片段并注册为代码证据，返回 `ev:code:...` |
| `run_command` | 默认禁止；allowlist 模式下只允许前缀匹配，拒绝 `; & \| < > $( )` 等串联和重定向；输出存为证据 |
| `read_evidence` | 按证据 ID 读取原文（先做完整性检查） |
| `remember` / `recall` | 写入 / 检索长期记忆 |
| `submit_claim` | 提交结构化主张；系统填写 ID、作者、模型；**引用不存在或被篡改的证据直接拒绝** |
| `send_message` | 向用户或其他 Agent 提问 |

写文件（自动修复）暂未开放，等 Git 分支隔离与回滚做好后加入。

### 8. 不可信内容隔离

工具返回的外部内容（文件、命令输出、记忆）用 `<<<DATA ...>>> … <<<END DATA>>>` 包裹，系统提示明确规定其中内容只是数据。内容里出现的同名标记会被破坏（插入零宽字符），无法提前"关闭"包裹。有测试验证。

### 9. 上下文预算

用户设置的 `context_budget_tokens` 不会因为速度被自动缩小。超出时，最早的工具输出被折叠为一行说明，**保留其中的证据 ID**；完整原文仍在 journal 和证据库中，Agent 可以用 `read_evidence` 重新读取。

## 暂未实现（明确列出，避免误解）

- 多 Agent 协作逻辑（双首脑、Worker/Guardian 配对、任务分派）：消息协议和运行时已支持多个 Agent 并行运行和互相发消息，但首脑的分派与审查逻辑尚未编写。
- 暂停只在任务之间生效；取消和停止会立即作用于运行中的任务。
- 模型能力自动检测：`codedoctor check` 目前只检查端点可达和模型是否在列表中。
- 不支持工具调用的模型（纯文本协议）尚未适配。
- 写文件、Git 分支隔离、自动修复。
