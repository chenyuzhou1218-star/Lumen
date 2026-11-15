# CodeCAD

**打开：** 双击 `D:\CodeDoctor\CodeCAD.lnk`，或者本文件夹里的 `CodeCAD.lnk`。

用代码做能真的打印出来的零件。尺寸以毫米为单位，用你电脑上的 Blender 做布尔切割。

- **尺寸是量出来的**：写下零件必须有的尺寸，建好后实际测量，对不上就报告。
- **打印前检查**：是不是封闭的实体、有没有碎块、悬空面积、是不是放在平台上、会不会超过打印机尺寸。
- **算重量**：按 PLA、PETG、ABS、TPU、铝、钢算。
- **出 STL**：直接送切片软件。

## 用法

```bash
python codecad.py init bracket
python codecad.py build bracket
```

零件写在 `part.py`，成品在 `out/`。写法见 [AI_GUIDE.md](AI_GUIDE.md)。在 Lumen 里输入 `@CodeCAD` 也可以。
