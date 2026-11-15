# CodeSound

**打开：** 双击 `D:\CodeDoctor\CodeSound.lnk`，或者本文件夹里的 `CodeSound.lnk`。

用代码写音乐和音效。全部声音都在本机现算：不用采样，不用下载，不用模型。

- **一键作曲**：选 14 种风格之一（古风、战斗、史诗、悬疑、电子、爵士、芯片……），换一个种子就是一首新曲子。
- **54 种乐器**：钢琴、弦乐、铜管、合唱、吉他、合成器，还有古筝、琵琶、扬琴、二胡、竹笛、唢呐、笙、编钟这类民族乐器。
- **26 种鼓**：架子鼓、808、太鼓、战鼓、定音鼓、锣、康加、邦戈等。
- **30 多种音效**：金币、刀剑、弓箭、爆炸、脚步、马蹄、胜利、失败、魔法，还有雷雨、风、火、海浪、鸟鸣、夜晚、洞穴，环境音可以无缝循环。
- **音色效果**：失真、合唱、颤音、复古降采样、滤波扫频、淡入淡出、转调、变速、循环音乐。
- **能导入导出**：导入 MIDI 用任何乐器演奏，导出 WAV、分轨、MP3、OGG、M4A。
- **AI 看得见声音**：AI 听不见，所以 CodeSound 会测响度、频段、削波和声场，读谱查走调、撞音和重复，再画一张图给它看。

## 用法

```bash
python codesound.py init mysong
python codesound.py render mysong --quality check
python codesound.py render mysong --quality final --stems
python codesound.py midi mysong
```

窗口里左边写代码，右边看钢琴卷帘，能试听，也能让 Lumen 的团队来写。在 Lumen 里输入 `@CodeSound` 也可以。

成品在 `out/`：`final.wav` 整首，`stems/` 分轨，`sfx/` 音效，`song.mid` 音符，`latest.png` 给人和 AI 看的图。

`examples/` 里有一首古风战曲、一首安静的小品和一套游戏音效。

AI 的写法见 [AI_GUIDE.md](AI_GUIDE.md)。
