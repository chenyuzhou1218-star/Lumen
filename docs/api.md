# 不开窗口用 Code Doctor：终端命令和 HTTP API

桌面窗口、终端命令和 HTTP API 用的是同一个项目：同一份配置、同一套调查记录和长期记忆。
在窗口里建的项目，终端和 API 都能直接用。

同一个项目同一时间只能有一个服务在跑。窗口开着时，终端的 `fix` 和 `serve` 会提示先关窗口；`tasks` 和 `show` 这类只读命令不受影响。

## 终端

把 `D:\CodeDoctor\bin`（或仓库里的 `code-doctor\bin`）加进 PATH 之后，在任意终端（cmd、PowerShell、Windows Terminal）里都能用：

```bash
cd C:\Users\cheng\Desktop\a
codedoctor fix "购物车总价少算了，积分抵扣后还会变成负数"
```

- **项目怎么找**：在项目的代码文件夹（或它的子文件夹）里运行，就用窗口里登记的这个项目。也可以用 `--project 名字` 或 `--config 配置文件` 指定。
- **交给谁**：默认交给你在设置里选的协作方式（6 人、双人互检等）的入口，也可以用 `--agent` 指定。
- **运行时**：终端里实时显示每个 agent 在做什么、系统测试的结果、侦察兵发现了什么、交给了谁修。
- **结束后**：打印最终回答、团队每个人的结果、改了哪些文件、测试通过没有、侦察发现。
- **退出码**：完成且测试没被改坏是 0，否则是 1，方便写进脚本或 CI。
- **中断**：按 Ctrl+C 中断，没做完的任务会标成"中断"，之后可以在窗口里继续执行。

| 命令 | 作用 |
|---|---|
| `codedoctor fix "问题描述"` | 让整支队伍查找并修复问题；`--json` 把结果输出成 JSON；`--thinking off/low/medium/high/max` 思考强度；`--model 服务/模型` 这次所有 Agent 用的模型；`--with codecut` 用 CodeCut 剪视频（和窗口里的 @CodeCut 一样，会打开 CodeCut 窗口实时显示，`--no-window` 不打开；只在项目文件夹里能用） |
| `codedoctor tasks` | 最近的调查 |
| `codedoctor show [编号\|last]` | 看一次调查的结果；`--json` 给脚本用 |
| `codedoctor undo [编号\|last]` | 撤回一次调查改动过的文件（调查结束后被你改过的文件不会动）；`--yes` 跳过确认 |
| `codedoctor projects` | 窗口里建过的项目 |
| `codedoctor serve` | 开 HTTP API（见下文） |
| `codedoctor check` | 检查配置，并试连每个模型服务 |

## HTTP API

```bash
codedoctor serve --port 8765
```

- 默认只监听本机（127.0.0.1）。
- 加 `--token 你的令牌`（或设置环境变量 `CODEDOCTOR_API_TOKEN`）后，每个请求都要带 `Authorization: Bearer 你的令牌`。
- 监听本机以外的地址（例如 `--host 0.0.0.0`）时必须设令牌，否则拒绝启动。这个接口能改你的代码。

| 接口 | 作用 |
|---|---|
| `POST /tasks` `{"instructions": "..."}` | 提交一个调查。`agent` 和 `title` 可以不写；`reasoning`（思考强度：off/low/medium/high/max）和 `model`（`{"endpoint": "...", "model": "..."}`，这次所有 Agent 用它）也可以不写；返回 `task_id` |
| `GET /tasks/{id}/progress?after_seq=0` | 新的进度（人能看懂的句子）。把返回的 `last_seq` 传回来就只拿新的；`settled` 为 true 表示全部结束 |
| `GET /tasks/{id}/result` | 结果：状态、最终回答、团队、改动的文件、系统测试、侦察发现 |
| `POST /tasks/{id}/cancel` | 取消（子任务一起停） |
| `POST /tasks/{id}/undo` | 撤回改动的文件 |
| `GET /tasks` | 最近的任务 |
| `GET /health`、`GET /agents` | 服务状态、每个 agent 用的模型和状态 |

更底层的接口（`/journal`、`/messages`、`/claims/...`、`/anomalies` 等）和 OpenAPI 文档在服务启动后的 `http://127.0.0.1:8765/docs`。

### Python

```python
import time
import requests

API = "http://127.0.0.1:8765"
H = {"Authorization": "Bearer 你的令牌"}  # 没设令牌就去掉

task = requests.post(f"{API}/tasks", json={"instructions": "购物车总价少算了"}, headers=H).json()
seq = 0
while True:
    p = requests.get(f"{API}/tasks/{task['task_id']}/progress", params={"after_seq": seq}, headers=H).json()
    for e in p["events"]:
        print(e["text"])
    seq = p["last_seq"]
    if p["settled"]:
        break
    time.sleep(2)

r = requests.get(f"{API}/tasks/{task['task_id']}/result", headers=H).json()
print(r["status"], r["tests"]["verdict"])
for c in r["changes"]:
    print(c["path"], f"+{c['added']} -{c['removed']}")
```

### PowerShell

```powershell
$t = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/tasks -ContentType "application/json; charset=utf-8" `
     -Body ([Text.Encoding]::UTF8.GetBytes('{"instructions": "购物车总价少算了"}'))
Invoke-RestMethod "http://127.0.0.1:8765/tasks/$($t.task_id)/result"
```

### curl

```bash
curl -X POST http://127.0.0.1:8765/tasks -H "Content-Type: application/json" -d "{\"instructions\": \"cart total is wrong\"}"
```

## 用 @ 调用工具：@CodeCut 剪视频

在输入框里打 `@`，会弹出可以调用的工具。选 **CodeCut** 后，输入框下面出现 `@ CodeCut` 标签（点它取消），这次调查才有剪辑工具
（`video_project` 看项目、`video_edit` 新建/加素材/分割/字幕/变速/调色、`video_render` 导出）。没有 @ 的调查里没有这些工具，
修代码时不多花 token。直接打出 `@CodeCut` 也一样。

- 发出后会打开一个 CodeCut 窗口，跟着项目文件夹：智能体每改一次项目文件，时间线就刷新一次；你自己有没保存的修改时不会被覆盖。
- 选的协作方式入口是总指挥时，任务交给有监督者的执行者（总指挥不能直接剪辑）。
- 在 CodeCut 里点右上角 **AI 剪辑** 也行：小窗口里说要怎么剪，它会先保存项目，再在项目文件夹里运行 `codedoctor fix --with codecut`。
  视频所在的文件夹要属于一个 Code Doctor 项目（在窗口里新建项目、选好模型）。
- 终端：`codedoctor fix --with codecut "把开头剪到 5 秒，加标题"`；HTTP：`POST /tasks` 带 `"tools": ["codecut"]`。
- 同样的写法还能叫来 `codesound`（音乐音效）、`codepage`（网页）、`codegame`（小游戏）、`codedeck`（幻灯片和文档）、`codedata`（数据分析）、`codecad`（打印零件）、`codelab`（看训练日志）：工具放在 Lumen 旁边的 `tools/<名字>`，见 `daemon/codedoctor/makers.py`。

## 思考强度和各家模型

同一个"思考强度"会换成每家自己的参数发出去：

| 服务 | 发出去的参数 |
|---|---|
| DeepSeek | `thinking` 开关和 `reasoning_effort` |
| Claude | `thinking.budget_tokens`（低 2048 / 中 8192 / 高 24576 / 最高 32768） |
| Gemini（OpenAI 兼容接口） | `reasoning_effort` |
| 通义千问 / 硅基流动 / 混元 / vLLM | `enable_thinking` 和 `thinking_budget` |
| 智谱 GLM / 豆包 | `thinking.type` |
| OpenRouter | `reasoning.effort` |
| OpenAI / Grok / Groq / Ollama / 其他 OpenAI 兼容服务 | `reasoning_effort` |

- 不设置时什么都不发，用各家的默认值。
- 某个模型不认识这个参数时，系统会自动去掉参数重发一次，并记住这个模型不支持，所以思考强度永远不会让请求失败。
- 开着思考又在调用工具时，DeepSeek 的 `reasoning_content` 和 Claude 带签名的思考内容会原样传回给模型（两家都要求这样做，否则直接报错）。
- 缓存：DeepSeek、OpenAI、Gemini 会自动缓存重复的开头。Claude 要在请求里标出缓存位置，Code Doctor 会标在工具列表、系统提示和最新一条消息上，所以每次请求只有新增的部分按全价算。每次回复里命中了多少缓存都记录在案（`cached_tokens`）。
