# CodeData

**打开：** 双击 `D:\CodeDoctor\CodeData.lnk`，或者本文件夹里的 `CodeData.lnk`。

把 Excel 或 CSV 丢进来，得到一份每个数字都查得到来源的分析报告。不用装 pandas，只用 Python 自带的库。

- **先体检**：`look` 不写代码就能看出重复行、缺失、数字列里混的文字、同一个名字的不同写法、离群值。
- **数字可追溯**：报告里的数字都由代码算出，每句结论连着它的依据，存在 `out/facts.json`。
- **能复核**：`recheck` 重新跑一遍，逐个数字对比。
- **图表自己画**：柱状图、条形图、折线图、环形图、散点图、直方图，配色对色盲友好。
- **原始文件不动**：读 `.xlsx`、`.csv`、`.tsv`、`.json`，只在内存里算。

## 用法

```bash
python codedata.py init sales
python codedata.py look sales
python codedata.py run sales --pictures
python codedata.py recheck sales
```

把数据文件放进项目文件夹，分析写在 `analysis.py`，成品是 `out/report.html`。

在 Lumen 里输入 `@CodeData` 也可以。写法见 [AI_GUIDE.md](AI_GUIDE.md)。
