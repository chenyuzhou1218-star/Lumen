# Making slides and documents with CodeDeck

Slides are `deck.json`. A document is `doc.md`, in Markdown. `build` makes the PowerPoint or Word file, a PDF, a web page and a picture of each page.

## The way of working

1. Who reads it, and what should they do or know at the end? Write that down first.
2. Plan the story as a list of slide titles. Read the titles alone: they should tell the whole thing.
3. Write it, `build`, and LOOK at every page picture.
4. Fix what the warnings say, then what you see. At least two rounds. A page that is reported as not fitting is not finished.

## Slides

```json
{"title": "...", "theme": "清爽", "slides": [
  {"kind": "title", "title": "...", "subtitle": "..."},
  {"kind": "section", "title": "第一部分", "subtitle": ""},
  {"kind": "points", "title": "...", "points": ["...", {"text": "...", "note": "a smaller line under it"}]},
  {"kind": "two", "title": "...", "left": {"title": "...", "points": []}, "right": {"title": "...", "points": []}},
  {"kind": "image", "title": "...", "image": "pictures/a.png", "side": "right", "points": []},
  {"kind": "quote", "text": "...", "who": "..."},
  {"kind": "numbers", "title": "...", "numbers": [{"value": "87%", "label": "..."}]},
  {"kind": "chart", "title": "...", "chart": {"type": "bar", "labels": [], "values": []}, "points": []},
  {"kind": "table", "title": "...", "rows": [["头", "头"], ["甲", "乙"]]},
  {"kind": "steps", "title": "...", "steps": [{"title": "...", "text": "..."}]},
  {"kind": "big", "text": "one sentence, alone on the page", "note": ""},
  {"kind": "agenda", "title": "...", "items": ["...", "..."]},
  {"kind": "timeline", "title": "...", "items": [{"when": "2024", "what": "..."}]},
  {"kind": "pictures", "title": "...", "images": ["a.png", "b.png", "c.png"]},
  {"kind": "end", "title": "谢谢", "subtitle": "..."}
]}
```

Any slide may have `"notes"`: what to say aloud. They go to `out/讲稿.md`. `outline <folder> <outline.md>` turns a plain outline into a deck.

Themes: 清爽 商务 暖色 深色 水墨 科技 极简 森林. Chart types: bar, hbar, line, donut. `values` is a list, or `{"name": [...]}` for bar and line.

`image` paths are relative to the project. Use `numbers` at most four, `steps` at most five.

- **The title is the conclusion.** Not 销售情况 but 华东的销售额占了四成.
- **One idea per slide.** Up to six short points. If it needs more, it is two slides.
- Never invent figures, quotes or names. Use what the user gave you, or leave it out.
- Vary the kinds: a chart or a number says more than a fifth list of points.

## Documents

Markdown: `#` the title, `##` and `###` sections, lists, tables, `> quotes`, ``` code, `![说明](picture.png)`, `**bold**`, `*italic*`, `` `code` ``. `<!-- 换页 -->` starts a new page.

Headings become Word's own heading styles, so that a table of contents can be made in Word.

Write everything the person will read (titles, slide and page text, narration, labels) in the language they wrote to you in; use 中文 only when they did. The examples and theme names in this guide being 中文 is not a reason to answer in 中文.
