# Lumen Feature Book

Lumen is a team of AIs that lives on your Windows PC. You talk only to Lumen, in plain language. It hands the work to the most suitable member of the team, picks the right tools on its own, and gives you the result when it's done. It can write code, track down problems, edit videos, make 3D models, build web pages and PDFs, look things up on the web, and operate your computer.

## 1. Getting started

- **What you need**: Windows, Python 3.12, and one AI: Claude Code or Codex (sign in once in the terminal after installing), or an API key (any service compatible with the OpenAI or Anthropic interface works).
- **Installing**: In the Lumen folder, run `setup.ps1` (the Chinese-language instructions are in `安装环境.ps1`). It creates a `.venv` in this folder and installs the packages Lumen needs, without touching the Python on your system. After that, double-click `Lumen.cmd` to open Lumen.
- **First launch**: After the welcome page, choose your interface language and a working folder, and you're ready to go. You can change the model later, below the input box.
- **Next time**: Lumen returns to the folder you were in last. The left sidebar lets you switch folders, start a new chat, and search your chats.

## 2. Sending messages

- Type what you want in the input box and press Enter to send. You can drag files in or paste them.
- **Voice input**: Click the microphone and speak. Casual speech is fine; Lumen understands what you mean and doesn't grade your grammar.
- **Model**: Below the input box, choose which AI to use (a model from Claude Code, Codex, or a service you've connected). Next to it is the thinking level. You choose the model yourself; Lumen never switches it on its own.
- **When it's unsure, it asks first**: If Lumen isn't confident it understands what you want, a question panel pops up. Each question comes with ready-made options, so you just click one. If you'd rather not answer, skip it and let Lumen use its own judgment.
- **Under each reply**: Copy it, remember it, regenerate it, or edit your message and ask again. When a reply is done, its steps fold away and only the result stays; click to see each step.

## 3. Approval modes

Choose the approval mode for this conversation below the input box. It decides whether the AI checks with you before it acts:

| Approval mode | When it asks you |
|---|---|
| Fully open | Never asks; just does it |
| Review for me | Only before deleting files, and before operating the mouse or keyboard |
| Ask me for everything | Before every action that changes anything |

When it needs to ask, a small card appears above the input box in the bottom right. It has one line describing the action, next to **Allow** and **Don't allow**. Clicking Don't allow skips only that one action; everything else continues as normal. Beyond this, Lumen has no other permission limits: every folder and drive on your computer is available to it.

## 4. The Lumen team

| Member | Responsible for |
|---|---|
| Lumen | Coordinator: talks with you, hands out the work, and gives you the final answer |
| Spark | Writes code, and also uses the various making tools |
| Prism | Reviews |
| Torch | Hands-on testing: actually runs the program from start to finish |
| Ray | Looks things up on the web |
| Lantern | Manages files |
| Beacon | Supervises: double-checks other members' results |
| Iris | Operates the computer |

Each member has its own working memory and can also call on disposable helpers. Members can work at the same time without getting in each other's way.

**Lumen treats you as an equal.** It talks like a capable colleague. If you're wrong, it says so directly and explains why. When it's right, repeated pressure won't make it back down unless you give it a reason. Decisions that are yours to make are yours: once you decide, Lumen carries them out properly.

## 5. Tools used automatically (no @ needed)

Just say what you want, for example "turn this image into a PDF," "trim this video to its first 10 seconds," or "make a red 3D cube." Lumen knows which tools are installed on this computer, picks the right ones, and hands the job to the member who has that tool.

You can also type @ in the input box to name a tool. Then only the tool you named is used.

| Tool | Used for |
|---|---|
| CodeCut | Video editing: cutting, joining, subtitles, background music, export |
| Code3D | 3D models and scenes, made with Blender on your computer; exports GLB files and images |
| CodeSound | Music and sound effects |
| CodePage | Web pages |
| CodeGame | Small games you can play |
| CodeDeck | Slides and documents (PowerPoint, Word, PDF) |
| CodeData | Analyzes Excel and CSV files; every number in a report can be traced back to its source |
| CodeCAD | Parts for 3D printing, with dimensions in millimeters |
| CodeLab | Views model training logs and progress |
| CodeTools | Dozens of small tools: logo posters, flowcharts, QR codes, subtitles, voiceovers, batch photo editing, file organizing, and more |
| CodeFilm | Turns one sentence into a short film |
| CodePDF | Images to PDF, merging, splitting, compressing, rotating, and picking pages |

## 6. Right-hand panel

- **Tool window**: When the team uses a tool, it opens automatically on the right so you can watch it work. This window belongs to the AI: it clicks and types inside it without taking over your mouse and keyboard, and you'll see a small blue mouse moving around. Click × on the window to close it.
- **Browser** (Ctrl+Shift+B): Search and open web pages here. Links in chat open here too. When the team looks things up online, you'll see it here as well.
- **Terminal** (Ctrl+J): A real PowerShell, opened in the current folder. Commands the team runs appear here in color.

## 7. Long-term memory

- **The AI remembers you**: Before each new conversation starts, the AI reviews your past conversations and condenses the key points into a memory. It covers two things: about you (who you are, how you talk, what you like, the rules you've set; shared across all projects) and about this project (what's been done, what's been decided, how far along it is). New conversations start with this memory, so you don't have to explain yourself again every time.
- **Length follows your history**: If you've chatted only a little, the memory is a few lines. The more you chat, the longer it gets, normally up to about 50,000 characters and at most around 80,000. Beyond that, it condenses again, trimming detail but not losing track of what happened.
- **It tells you when it's still working**: If the memory from your previous conversation isn't finished being organized, the new conversation shows "Reviewing past chats…" for up to 90 seconds.
- **You can view, edit, or clear it**: Go to "Settings → Long-term memory → What AI remembers about you." Anything you change is followed from then on. After you clear it, past conversations won't be used to rebuild it.
- Members also note facts worth remembering while they work, and recall them automatically next time. Once you choose an embedding model, Lumen can also recall older conclusions that were worded differently, based on meaning.

## 8. Doing several things at once

- Several conversations can run at the same time without waiting on each other. One can be waiting for your answer while another keeps working.
- You can open multiple windows on the same folder (Ctrl+Shift+N).
- What one conversation learns, the others know the next time (see section 7).

## 9. Computer use

- Available from the start: screenshots, mouse, keyboard, opening and closing programs, the terminal, and all windows (except Lumen's own windows). Give it a program name or a full path, and it can open any program.
- Whether it asks you first depends on the approval mode (section 3).
- **How it operates**: It starts out working in the background and doesn't take over your mouse and keyboard. For things like games that need a real mouse, switch to foreground mode in "Settings → Computer use."
- **Emergency stop**: Press `Ctrl+Alt+End`, or move the mouse to the top-left corner of the screen.
- To keep the AI away from your computer: in "Settings → Computer use," turn on "Turn off computer use."

## 10. When administrator rights are needed

System folders such as `C:\Windows` and `Program Files` require administrator rights. If Windows says "Access denied," the AI reruns that command as administrator. Windows then shows its own confirmation prompt, and you decide whether to allow it.

## 11. Automatic tests

In "Settings → Automatic tests," enter your project's test command (or click "Auto-detect"). When the team changes code, the system runs the tests automatically before starting work, after each change, and before handing off the result. This doesn't go through the model and uses no tokens. If someone breaks a test that used to pass, it's flagged on the spot. We recommend committing with git once before you start, so you can always see what changed and roll it back if needed.

## 12. Interface language

English, Français, Español, Deutsch, Italiano, Português, 简体中文: seven languages in total. Switch in "Settings → Appearance," and it takes effect immediately. The right-hand tool window switches too. The AI answers in the language you write your messages in.

## 13. Settings at a glance

- **Services and keys**: Connect as many AI services as you like. Keys are stored only in Windows Credential Manager, never in config files.
- **AI models**: Which model from which service each member uses, how deeply it thinks, and which backup model to switch to if an error occurs.
- **Long-term memory**: The recall switch, "What AI remembers about you," and meaning-based recall.
- **Automatic tests** and **Computer use**: See above.
- **Appearance**: Language, wallpaper, font size, accent color, and more. Changes apply right away.
- **Usage**: How much you've used today, over the last seven days, and in total.
- **Feature book**: This page.

## 14. Handy extras

- **Ctrl+K**: One box to find everything: chats, pages, and actions. Type two or more characters and you can even find things said in past chats. **Ctrl+/** shows all keyboard shortcuts.
- **Ctrl+N** starts a new chat, **Ctrl+B** collapses or expands the left sidebar, **Ctrl+F** finds text within a chat, and **Ctrl+,** opens Settings.
- **Right-click a chat**: Rename it, export it as Markdown, or collapse it from the list (this doesn't delete it).
- **Saved phrases**: Write a message you use often and press Ctrl+S to save it as a saved phrase. Type / in an empty input box to bring it up. An unsent message is kept even if you close the window.
- **Done alerts**: When the window isn't in front, the taskbar flashes when a reply finishes, and a reminder appears in the bottom right.
- **Browser**: Click the star to bookmark this page, press Ctrl+Shift+T to reopen a closed tab, and use the bubble to send this page to Lumen.
- **Terminal**: Right-click the output to send the selected or most recent output to Lumen.

## 15. Security and privacy

- You choose all the models. Lumen never switches them on its own.
- Your conversations, memory, and logs are stored on your own computer, in the `~/.codedoctor` folder.
- Keys live only in Windows Credential Manager. Keys are never saved in memory.
- The AI won't handle payments or logins for you.

## 16. Tips

- The more specific you are, the closer the first result will be to what you want. If you're not specific, Lumen will ask you first.
- To go faster and spend less, choose a smaller model or a lower thinking level. Switch to a larger one for harder work.
- If Lumen crashes, send `~/.codedoctor/crash.log` to the developer.
