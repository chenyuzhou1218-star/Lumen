# Lumen

**A team of AIs on your Windows computer.** You talk to Lumen in plain words - typed or spoken. It hands the work to the
right member, picks the right tool by itself, and you watch it work on the right side of the window.

**装在你 Windows 电脑上的一队 AI。** 你只跟 Lumen 说话，打字或者语音都行。它会把活交给最合适的成员，自己挑合适的工具；你在窗口右边看着它干。

[English](#english) · [中文](#中文)

---

## English

### What it does

- **One conversation, a whole team.** Lumen leads; Spark writes code, Prism checks, Torch runs it for real, Ray searches the
  web, Lantern looks after files, Beacon reviews, Iris uses the computer. Members work at the same time without overlapping.
- **Tools it picks by itself - no @ needed.** Video (CodeCut), 3D in your own Blender (Code3D), web pages (CodePage), slides
  and documents (CodeDeck), PDFs (CodePDF), music and sound, data analysis, printable parts, games, short films, and dozens
  of small utilities (CodeTools). Say what you want; the tool opens on the right and a blue cursor works in it - your own
  mouse and keyboard stay yours.
- **It remembers you.** Before a new conversation starts, an AI reviews the earlier ones and keeps what matters - who you
  are, how you talk, your rules, where the work stands - a few lines to some 50K characters, at most ~80K, compressed again
  rather than cut. You can read, edit and clear it in Settings → Long-term memory.
- **An equal, not a servant.** It tells you plainly when you are wrong, and keeps a right answer under pressure; once a
  decision is yours to make, it carries it out.
- **Your approval, your choice.** Fully open (never asks) · Review for me (asks only before deleting files and before using
  the mouse and keyboard) · Ask me for everything. No other limits: every folder and drive is open, and Windows asks you itself
  when administrator rights are needed.
- **Many things at once.** Several conversations run side by side; a question waiting in one never holds up another.
- **Seven languages**: English, Français, Español, Deutsch, Italiano, Português, 简体中文 - the tools' windows too.
- **Your models.** Claude Code, Codex, or any OpenAI- or Anthropic-compatible service (DeepSeek, Gemini, Qwen, Kimi, GLM,
  Ollama, LM Studio ...). Lumen never switches models on its own. Keys stay in the Windows Credential Manager.

### Install (Windows 10 / 11)

| You need | For | Required? |
|---|---|---|
| Python 3.12 (python.org) | Lumen and every tool | Yes |
| One AI: Claude Code (`npm i -g @anthropic-ai/claude-code`, then `claude` once to sign in), Codex (`npm i -g @openai/codex`, then `codex` once), or an API key entered in Lumen | The answers | One of them |
| Node.js 18+ | Installing Claude Code or Codex; rebuilding the interface | Only for those |
| Microsoft Edge (comes with Windows) | Pictures and PDFs of CodePage and CodeDeck | Already there |
| Blender 4+ (blender.org) | Code3D and CodeCAD | Only for those two |
| ffmpeg | CodeCut | Included |

With Python 3.12 installed, run in this folder:

```bash
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

It makes a `.venv` here (your system Python is not touched), installs the libraries, and says at the end which of the
programs above are missing. Then double-click `Lumen.cmd`. The feature book is inside Lumen: Settings → Feature book.

In PyCharm: open the folder, choose Python 3.12 and let it make a virtual environment from `requirements-dev.txt`, then run
the module `codedoctor.desktop.app`. Run `setup.ps1` once in its terminal for the CodeCut and CodePDF libraries.

### Without the window

With `bin` on PATH, in a project folder: `codedoctor fix "the cart total is too low"` shows each member's steps and the
tests, then the changes; `codedoctor show`, `codedoctor undo`, and `codedoctor serve` for an HTTP API ([docs/api.md](docs/api.md)).

### Tests

```bash
.venv\Scripts\python -m pytest tests/daemon -q
.venv\Scripts\python tools\flow_check.py
```

`flow_check.py` runs the main flow with a real model in a throwaway data folder (`LUMEN_FLOW_ENGINE`, `LUMEN_FLOW_MODEL`):
chat, the question panel, parallel chats, memory, approvals, tools picked by themselves, CodeCut, Code3D, CodePDF, the seven
languages.

### License

[MIT](LICENSE): free to use, change, share and sell, keeping the copyright notice. ffmpeg (in `tools/codecut/tools`) and the
Python and JavaScript libraries Lumen installs come under their own licenses.

---

## 中文

### 它能做什么

- **一个对话，一整队人**：Lumen 带队；Spark 写代码，Prism 检查，Torch 把程序真跑一遍，Ray 上网查资料，Lantern 管文件，Beacon 监督复查，Iris 操控电脑。成员能同时干活，互不重叠。
- **自己挑工具，不用 @**：剪视频（CodeCut）、用你自己的 Blender 做 3D（Code3D）、网页（CodePage）、幻灯片和文档（CodeDeck）、PDF（CodePDF）、音乐音效、数据分析、能打印的零件、小游戏、短片，还有几十个小工具（CodeTools）。说出你要什么，工具会在右边打开，一个蓝色的小鼠标在里面干活，不占用你的鼠标键盘。
- **它记得你**：每次新对话开始前，AI 会回顾以前的对话，把要点留下来：你是谁、怎么说话、立过的规矩、活做到哪一步。少则几行，平常 5 万字以内，最多约 8 万字；超了就再压缩，不会直接截掉。在“设置 → 长期记忆”里能看、能改、能清空。
- **平等，不当跟班**：你说错了它会直说，它对的时候你逼它也不改口；该你拍板的事，你定了它就照着做好。
- **批准方式你来定**：完全放开（从不问）· 帮我审查（只在删文件和用鼠标键盘之前问）· 全部问我。除此之外没有别的限制：每个文件夹、每个盘都能用；需要管理员权限时，Windows 会自己弹窗问你。
- **同时做好几件事**：好几个对话并排跑，一个在等你回答，另一个照样干活。
- **7 种界面语言**：English、Français、Español、Deutsch、Italiano、Português、简体中文，右边的工具窗口也跟着换。
- **模型你来选**：Claude Code、Codex，或任何兼容 OpenAI / Anthropic 接口的服务（DeepSeek、Gemini、通义千问、Kimi、智谱、Ollama、LM Studio 等）。Lumen 从不自己换模型；密钥只存在 Windows 凭据管理器里。

### 安装（Windows 10 / 11）

| 需要 | 用途 | 必需吗 |
|---|---|---|
| Python 3.12（python.org） | Lumen 和所有工具 | 必需 |
| 一种 AI：Claude Code（`npm i -g @anthropic-ai/claude-code`，再运行一次 `claude` 登录）、Codex（`npm i -g @openai/codex`，再运行一次 `codex`），或在 Lumen 里填一个 API 密钥 | 回答问题 | 至少一种 |
| Node.js 18 以上 | 装 Claude Code 或 Codex；重新打包界面 | 只在这些时候 |
| Microsoft Edge（Windows 自带） | CodePage、CodeDeck 的截图和 PDF | 系统自带 |
| Blender 4 以上（blender.org） | Code3D 和 CodeCAD | 只有这两个工具 |
| ffmpeg | CodeCut 剪视频 | 已附带 |

装好 Python 3.12 后，在本文件夹运行：

```bash
powershell -ExecutionPolicy Bypass -File .\安装环境.ps1
```

它会在这个文件夹里建一个 `.venv`（不动你系统里的 Python），装好需要的库，最后告诉你上面哪些程序还没装。之后双击 `Lumen.cmd` 打开。功能手册在 Lumen 里面：设置 → 功能手册。

用 PyCharm：打开这个文件夹，解释器选 Python 3.12，让它按 `requirements-dev.txt` 建虚拟环境，然后运行模块 `codedoctor.desktop.app`。CodeCut 和 CodePDF 的库，在它的终端里运行一次 `setup.ps1` 就装好了。

### 不开窗口也能用

把 `bin` 文件夹加进 PATH，在项目文件夹里运行 `codedoctor fix "购物车总价少算了"`，会显示每个成员的步骤和测试，最后列出改动；`codedoctor show` 看结果，`codedoctor undo` 撤回，`codedoctor serve` 开 HTTP 接口（见 [docs/api.md](docs/api.md)）。

### 测试

`tests/daemon` 是单元测试；`tools/flow_check.py` 在临时数据目录里用真模型跑一遍主流程：聊天、提问面板、并行对话、记忆、批准方式、自动选工具、CodeCut、Code3D、CodePDF、7 种语言。

### 许可证

[MIT](LICENSE)：可以免费使用、修改、分享和商用，只要保留版权声明。ffmpeg（在 `tools/codecut/tools` 里）以及 Lumen 安装的 Python、JavaScript 库，各自遵循它们自己的许可证。
