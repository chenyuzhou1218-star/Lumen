# CodeDeck

**打开：** 双击 `D:\CodeDoctor\CodeDeck.lnk`，或者本文件夹里的 `CodeDeck.lnk`。

用文字写幻灯片和文档，直接得到 PowerPoint、Word、PDF 和网页。不用装 Office，也不用下载库。

- **幻灯片**：11 种页面（标题、要点、左右对比、图文、引用、数字、图表、表格、步骤等），5 种主题。
- **真的能改**：PPT 里是真文本框和真表格，Word 里是真标题和真列表，图表是图片。
- **文档**：写 Markdown，出 Word 和 PDF。
- **AI 自己检查**：每页出图，还会量文字有没有溢出，提醒哪页字太多。

## 用法

```bash
python codedeck.py init mytalk
python codedeck.py init myreport --doc
python codedeck.py build mytalk
```

幻灯片写在 `deck.json`，文档写在 `doc.md`，成品都在 `out/`。

在 Lumen 里输入 `@CodeDeck` 也可以。写法见 [AI_GUIDE.md](AI_GUIDE.md)。
