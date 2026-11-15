# CodeFilm

**打开：** 双击 `D:\CodeDoctor\CodeFilm.lnk`，或在 Lumen 的“插件”页里点它。

一句话出成片。写一句“做一个一分钟的古风宣传片《山河》”，它会：

1. **排分镜**：按风格挑场景、定镜头和运镜，片名从你的话里取。
2. **渲染画面**：每个镜头用 Code3D 和 Blender 渲染。
3. **作曲**：CodeSound 按风格写一首和片子一样长的配乐。
4. **配音**：你写了旁白，就用 Windows 自带的语音念出来（离线、免费）。没写就不配，它不会自己编台词。
5. **剪辑**：镜头缓缓推拉平移，交叉淡化转场，烧进字幕，旁白说话时音乐自动让开，最后导出 MP4 和 SRT 字幕。

渲染好的镜头、配音和音乐都会存下来，改了哪个就只重做哪个。

在 Lumen 里输入 `@CodeFilm 做一个……`，AI 会把分镜、旁白和需要的新场景都写好，自己看每个镜头再改。

```bash
python codefilm.py plan myfilm --idea "做一个30秒的古风宣传片《山河》" --lines "山河依旧\n烽火又起"
python codefilm.py build myfilm --quality draft
python codefilm.py build myfilm --quality final
```
