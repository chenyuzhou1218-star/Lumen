# CodePDF

在 Lumen 里输入 `@CodePDF`，或单独运行 `codepdf.cmd`。

功能：照片转 PDF、合并、拆分、压缩、改页面大小（A4/A3/A5/信纸）、旋转、保留或删除页。文字全部走 words.py（中文 / English，跟着 Lumen 的语言）。

需要 pypdf（纯 Python）装在本文件夹的 `libs`：

    python -m pip install --target libs pypdf

照片转 PDF 只需要 Pillow，不用 pypdf。
