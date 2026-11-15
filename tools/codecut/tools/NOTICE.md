# FFmpeg

Bundled executable: FFmpeg 7.1 essentials build, gyan.dev, distributed in the `imageio-ffmpeg` 0.7.0 Windows wheel. The executable reports `--enable-gpl --enable-version3`.

FFmpeg is a separate program invoked by CodeCut. It includes components licensed under GPL version 3. See [FFmpeg licensing](https://ffmpeg.org/legal.html), [GPL v3](https://www.gnu.org/licenses/gpl-3.0.html), and [Gyan builds/source information](https://www.gyan.dev/ffmpeg/builds/). The imageio wrapper's license is included separately as `IMAGEIO_FFMPEG_LICENSE.txt`; that license does not replace the FFmpeg executable's licenses.

This folder is prepared for local use. Review the FFmpeg source/license redistribution requirements before distributing the bundled executable to other users. You can remove the bundled executable and point `CODECUT_FFMPEG` at your own FFmpeg installation.
