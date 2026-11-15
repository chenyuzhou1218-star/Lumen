# CodeGame

**打开：** 双击 `D:\CodeDoctor\CodeGame.lnk`，或者本文件夹里的 `CodeGame.lnk`。

说一句话，做出能玩的 3D 小游戏。成品是一个网页文件，双击就能玩，也能发给别人。

- **自己的引擎**：不用下载任何东西，直接跑在浏览器的 WebGL 2 上，有光照、影子、雾、天空和地形，为弱显卡做过取舍。
- **接得上别的工具**：读 Code3D 导出的 GLB 模型，播放 CodeSound 做的声音，素材都打包进一个文件。
- **AI 能自己玩**：`play` 在本机的 Edge 或 Chrome 里开游戏、按键、截图，报告玩家走了多远、分数变了没有、有没有掉出地图、有没有报错。

## 用法

```bash
python codegame.py init mygame
python codegame.py build mygame
python codegame.py play mygame
```

成品是 `out/index.html`。`examples/crystal_valley` 是一个完整的小游戏：在天黑前找齐水晶，躲开石卫士。

在 Lumen 里输入 `@CodeGame` 也可以。AI 的写法见 [AI_GUIDE.md](AI_GUIDE.md)。
