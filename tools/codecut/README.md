# CodeCut 剪辑软件

把代码运行生成的画面、视频、图片和音频合成 MP4。提供 Windows 桌面界面，也保留终端命令和 JSON，方便 AI 操作。

## 打开桌面界面

双击 **CodeCut.lnk**（本机无黑色终端窗口的启动入口），或双击 **启动剪辑软件.cmd**。也可以在本目录运行：

```powershell
.\启动剪辑软件.cmd
# 直接载入附带示例：
.\启动剪辑软件.cmd --project .\demo\project.json
```

第一次剪辑：

1. 点素材区上方「导入」，选视频、音乐或图片；也可以把文件拖进窗口。
2. 双击素材加入时间线；也可以拖到主画面或画中画轨道。
3. 点击时间线标尺定位播放头，选中片段后点「分割」。拖两端裁剪，拖中间调整顺序。
4. 点「＋ 文字」添加标题，在右侧改文字、大小和位置，点「应用更改」。
5. 右侧还能调整速度、原声音量、淡入淡出、旋转、镜像、四边裁剪和颜色。
6. 点「更新预览」查看完整合成效果。改动后需要重新生成预览；点击播放也会自动生成。
7. 右上角「导出视频」保存视频；「保存项目」保存以后还能修改的剪辑文件。

新版界面使用左侧分类素材库、中间播放器、右侧分组属性和下方时间线。素材卡片显示实际缩略图与音频波形；搜索框和分类按钮用于筛选当前项目素材。右侧选项按基础、画面、色彩和声音分组。「更新预览」查看合成效果，右上角「导出视频」保存 MP4；保存项目使用顶栏保存图标或 Ctrl+S。时间线右上角的适应图标可让全部片段适应窗口宽度。

界面使用玻璃材质：共享的模糊光影背景、半透明面板、细高光边缘、轻微折射和带悬停过渡的玻璃按钮。输入框、数值微调箭头、滑块、勾选框和时间线使用统一细节。材质只用于编辑界面，不会叠加到导出的视频中。

声音和文字可以单独拖到指定时间。主画面连续排列，删除或裁剪后自动接合。画中画属于所在主片段；分割主片段时，画中画也会连续拆分。淡入淡出为画面与声音逐渐出现或消失，不是两个片段互相叠化。

快捷键：`Ctrl+B` 分割、`Ctrl+Z` 撤销、`Ctrl+Shift+Z` 重做、`Ctrl+D` 复制片段、`Ctrl+S` 保存、`Ctrl+E` 导出。未在文字框内输入时，空格播放/暂停，左右箭头逐帧定位，Delete 删除选中片段。删除片段不删除源文件。

本地 HTML、Git 仓库和运行中的预览地址，通过左侧「代码 / Git」导入。预览会先在后台生成真实的低分辨率合成视频；导出使用项目原始尺寸。菜单「文件 → 项目画幅与帧率」可选横屏、竖屏或正方形。编辑期间会自动保存恢复副本。

这是基础剪辑版。暂不含自动语音识别字幕、智能抠像、素材商城、关键帧动画、专业多机位编辑或任意桌面程序自动运行。

## 立即运行（PowerShell）

进入本文件所在目录：

```powershell
cd "C:\Users\cheng\Documents\Codex\2026-10-31\new-chat\outputs\codecut"
.\codecut.cmd doctor
.\codecut.cmd list .\demo\project.json
.\codecut.cmd render .\demo\project.json -o .\demo\my-video.mp4
```

`demo/result.mp4` 是已经实际导出的示例：代码动画 → 视频加代码画中画，同时混入 MP3。音频为测试音。

## 自己建项目

```powershell
.\codecut.cmd init .\my-project.json --width 1280 --height 720 --fps 30
.\codecut.cmd add .\my-project.json code "D:\your-repo" --entry index.html --duration 5 --id intro
.\codecut.cmd add .\my-project.json video "D:\media\clip.mp4" --trim 2 --duration 6 --id clip
.\codecut.cmd add .\my-project.json code "D:\your-repo\index.html" --over clip --width 320 --height 180 --x 920 --y 500 --duration 6 --id overlay
.\codecut.cmd add .\my-project.json audio "D:\media\music.mp3" --start 0 --duration 11 --volume 0.3 --id music
.\codecut.cmd preview .\my-project.json --open
.\codecut.cmd render .\my-project.json -o .\final.mp4
```

命令中的素材路径需要换成自己的真实路径。场景依次播放；音频按 `--start` 放到全片时间线上；画中画从所属场景的开头出现。

## Git 仓库和正在运行的项目

```powershell
.\codecut.cmd repo https://github.com/USER/REPO.git .\repos\example
.\codecut.cmd add .\my-project.json code .\repos\example --entry index.html --duration 5
# Vite / React 等项目先自己启动，再传入实际预览地址：
.\codecut.cmd add .\my-project.json code http://localhost:5173 --duration 5
```

`repo` 只克隆，不自动安装依赖或运行仓库脚本。静态项目直接选择 HTML 入口；需要编译的项目可以选择构建后的 HTML，或传入已经运行的 HTTP 地址。多个仓库的画面可以先后拼接，也可以叠在同一个场景中。不会自动合并不同仓库的源代码或业务依赖。

## 修改剪辑

```powershell
.\codecut.cmd list .\my-project.json
.\codecut.cmd move .\my-project.json clip 1
.\codecut.cmd set .\my-project.json clip duration 4
.\codecut.cmd set .\my-project.json music volume 0.2
.\codecut.cmd remove .\my-project.json overlay
.\codecut.cmd check .\my-project.json
.\codecut.cmd schema
```

也可以直接编辑 `project.json`。其中相对素材路径以 JSON 所在文件夹为基准；命令行参数中的路径以当前终端目录为基准。视频和音频不填 `--duration` 时会读取剩余时长；代码和图片默认 5 秒。视频导出帧率固定，时长会取整到最近的一帧。

终端的 `preview` 会导出完整预览 MP4，`--open` 调用系统播放器；`--scene clip` 只导出该场景及画中画，不含全局背景音和文字。已有文件需要 `--force` 才能覆盖；源素材和项目文件不能作为输出路径。

## 给 AI 使用

让 AI 先读 [AI_GUIDE.md](AI_GUIDE.md)，再执行 `schema`。正常结果输出到标准输出，单行 JSON；进度输出到标准错误，也是一行一个 JSON。成功退出码为 0，失败非 0。

代码画面推荐提供这个函数：

```javascript
window.renderFrame = async function(seconds, {width, height}) {
  // 根据 seconds 设置完整画面。可绘制 Canvas、SVG、DOM 或 WebGL。
};
```

参考 `examples/animation.html`。未提供函数时，工具会推进浏览器定时器和 requestAnimationFrame，并按时间定位 CSS 动画。普通页面的外部服务、随机数和复杂异步任务不保证逐帧可重复。网页内音频不会录入，画中画原声音轨也静音；需要声音请单独 `add audio`。画中画目前使用不透明矩形，按添加顺序叠放，超出自身时长后消失。

## 环境

本机已准备好 Python、Playwright Chromium 和项目内 FFmpeg。启动器会优先使用 `CODECUT_PYTHON`，然后使用本机 Python 3.12，最后尝试 `python`。

换电脑时：安装 Python 3.10+，执行：

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

FFmpeg 可放在 `tools/ffmpeg.exe`，或通过 `CODECUT_FFMPEG` 指定路径，也可使用 PATH 中的版本。其版本和授权说明见 `tools/NOTICE.md`。

实现参考：[Playwright 页面与截图 API](https://playwright.dev/python/docs/api/class-page)、[FFmpeg 滤镜文档](https://ffmpeg.org/ffmpeg-filters.html)。
