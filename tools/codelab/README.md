# CodeLab

**打开：** 双击 `D:\CodeDoctor\CodeLab.lnk`，或者本文件夹里的 `CodeLab.lnk`。

看着模型训练：读日志，算进度，发现问题就说出来。

- **只读不碰**：读日志完全不影响正在跑的训练。
- **认识各种日志**：`loss: 0.31`、`epoch 3/10`、JSON 行、tqdm 进度条、CSV。
- **能发现问题**：NaN、不再下降、变差、过拟合、显存不够、日志很久没更新。
- **看曲线**：把各项指标画成图，也能比较几次训练的最好成绩。
- **不动别人的任务**：`stop` 只能停 CodeLab 自己启动的任务，手动开的训练永远不会被它停掉。

## 用法

```bash
python codelab.py watch D:/ai1/train.log --name 主模型
python codelab.py picture 主模型
python codelab.py start D:/ai1/exp --name 试验一 -- python train.py
```

只用 Python 自带的库，画图用 Pillow。

在 Lumen 里输入 `@CodeLab` 也可以。写法见 [AI_GUIDE.md](AI_GUIDE.md)。
