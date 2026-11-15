# CodePDF

PDF 的常见操作：照片转 PDF、合并、拆分、压缩、改页面大小、旋转、保留或删除页。原文件不会被改动或删除，结果是新文件，默认放在原文件旁边的 `CodePDF` 文件夹（或 `--out`）。

```
codepdf run <tool> --args-file args.json [--out 文件夹]
```

`schema` 列出每个 tool 要填什么。tool：`images`、`merge`、`split`、`compress`、`size`、`rotate`、`pick`。页码写成 `1-3,5,8-`（从 1 开始，空 = 全部）。

1. 先问清用户要对哪个文件做什么；路径是这台电脑上的路径。
2. 运行，读 `lines` 和 `files`，告诉用户结果在哪里。
3. 出错时 `error` 是一句人话，照实告诉用户。
