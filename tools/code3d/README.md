# Code3D

用代码做 3D。写一段 Python，你电脑上的 Blender 在后台把它变成模型和真实的画面。

## 怎么用

- 窗口：双击 `D:\CodeDoctor\Code3D.lnk`。左边写代码，按 F5 预览，F6 出成片。
- 让 AI 做：在 Lumen 的输入框里打 `@Code3D`，或点窗口右上角的「AI 建模」。
- 命令行：`D:\CodeDoctor\bin\code3d.cmd`，所有命令都用一行 JSON 回答。给 AI 的说明在 `AI_GUIDE.md`。

## 写场景

```python
import c3d

c3d.sky(sun_height=24)
c3d.ground(mat='concrete')
c3d.sphere(.5, at=(0, 0, .5), mat='gold')
c3d.camera(at=(3, -4, 1.5), look=(0, 0, .4), lens=50)
```

长度单位是米，Z 轴朝上，颜色写 `'#rrggbb'`，角度写度数。`scene.py` 里也能直接用 `bpy`，也就是 Blender 的全部功能。
`code3d schema` 列出 `c3d` 的所有函数。

## 几个实际情况

- **预览不是实时的**。窗口里的画面都是 Blender 真渲染出来的，「转一圈」是一圈小图，拖动时在这些图之间切换。要实时转动，点「在 Blender 打开」。
- **在 Blender 打开的是副本**（`out/scene.blend`）。在那里改的东西不会写回代码。
- **能在游戏后面跑**。Cycles 只用处理器，优先级调低，并留一个核，不占显卡。EEVEE 用显卡，玩游戏时别用。
- **scene.py 被限制在项目文件夹里**：不能启动程序、不能联网、不能读写项目外的文件（`kit/guard.py`）。这能挡住误操作和粗心的脚本，但不是绝对的沙箱：Blender 自己的 C 代码（比如 `bpy.ops`）不经过这道检查。
- **Blender 的位置**自动从开始菜单的快捷方式找。如果找不到，或者你想换版本，设置环境变量 `CODE3D_BLENDER`。

## 测试

```bash
python -m unittest discover -s tests
```

## 窗口里的积木

右边的「积木」点一下，就把一段能跑的代码写到光标处：天空、摄影棚、地面、方块、球、圆柱、旋转体、管子、文字、灯泡、相机。先搭起来，再改数字。
