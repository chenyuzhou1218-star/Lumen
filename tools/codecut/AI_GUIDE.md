# CodeCut: instructions for an AI operator

Use the terminal for AI automation. A native Windows UI is also available in `editor.py`. Both share the same JSON and renderer. Do not read or stitch source-code lines as video content. Render the running visual result.

1. Run `codecut.cmd doctor`. Require `ok: true` before rendering.
2. Run `codecut.cmd schema` to learn the JSON contract.
3. Create a project with `init`, then use `add`, or edit the project JSON directly.
4. Use `list` to inspect the order and IDs. `move` uses a 1-based position within that clip's track.
5. Run `check` to validate configuration and source paths. It does not run pages or decode all media.
6. Run `render PROJECT -o OUTPUT.mp4`. Read progress from stderr. Read the final JSON from stdout and check the exit code.
7. Report the actual output path. Do not claim rendering succeeded unless the command returned `ok: true`.

All commands are non-interactive. No API key or AI service is needed. Help and argument errors are human-readable; normal results and runtime errors are JSON. Existing outputs are protected unless `--force` is supplied. Do not use `--force` unless replacement is intended.

## Minimal commands

```text
codecut.cmd init project.json --width 1280 --height 720 --fps 30
codecut.cmd add project.json code ./repo --entry index.html --duration 5 --id intro
codecut.cmd add project.json video ./clip.mp4 --trim 1 --duration 3 --id video
codecut.cmd add project.json code ./repo/index.html --over video --duration 3 --x 20 --y 20 --width 320 --height 180 --id inset
codecut.cmd add project.json audio ./voice.mp3 --duration 8 --start 0 --volume 0.8 --id voice
codecut.cmd split project.json video 4.5
codecut.cmd text project.json "Opening title" --start 0 --duration 3 --size 56 --id title
codecut.cmd update project.json video "{\"speed\": 2, \"fade_in\": 0.5, \"saturation\": 1.2}"
codecut.cmd duplicate project.json intro
codecut.cmd info ./clip.mp4
codecut.cmd render project.json -o result.mp4
```

`split` cuts at a time on the whole timeline (like Ctrl+B in the window); `text` adds a burned-in title; `update` changes any clip fields with the editor's own rules (a speed change rescales the duration; fades are clamped). Code Doctor agents use these through its `video_project`, `video_edit` and `video_render` tools.

## JSON example

```json
{
  "version": 1,
  "width": 1280,
  "height": 720,
  "fps": 30,
  "scenes": [
    {"id": "intro", "kind": "code", "source": "repo/index.html", "duration": 5},
    {"id": "video", "kind": "video", "source": "clip.mp4", "trim": 1, "duration": 3, "volume": 0.5}
  ],
  "audio": [
    {"id": "voice", "kind": "audio", "source": "voice.mp3", "duration": 8, "start": 0, "volume": 0.8}
  ]
}
```

Scene order is playback order. Audio and text `start` are global timeline time; overlay `start` is relative to its parent scene. `trim` is source time. `duration` is output time; source consumption is `duration * speed`. Durations are rounded to the nearest output frame. Overlays appear in array order and their audio is muted. They disappear when their duration ends. Browser audio is not captured. Add it explicitly on the audio track.

Supported optional clip fields: `speed` (0.25..4), `fade_in`, `fade_out` (output seconds). Visuals also accept `rotate` (0/90/180/270), `mirror`, `crop` ([left,top,right,bottom] fractions), `brightness` (-1..1), `contrast` (0..3), `saturation` (0..3). `texts` is an optional global array: `{id,kind:"text",text,start,duration,font_size,color:"#ffffff",x,y,box:true}`. x/y are the center of the text in canvas pixels. Texts are burned into the MP4. Scene-only preview excludes global text and audio. The desktop UI stores optional asset-library and thumbnail metadata; the renderer ignores it.

JSON source paths are relative to the JSON file. CLI paths are relative to the current working directory. Code directories use `--entry index.html` by default. Local HTML is served over loopback HTTP so imports and assets can load; `--root` sets the serving root. Build-dependent code must already be built or have a running HTTP URL. Do not claim that arbitrary Python/C++ repositories can run as browser scenes. Repository scripts are not executed automatically.

Prefer code with `window.renderFrame = async (seconds, {width,height}) => {...}`. It must return promptly, set the complete frame from the supplied absolute time, and not wait for requestAnimationFrame. For generic pages the browser clock advances; network, randomness and all asynchronous effects are not guaranteed to be deterministic. HTML dependencies must be available; an exported file does not prove remote assets were correct.

`preview` renders a real MP4. `preview --scene ID` excludes global audio. `preview --open` invokes the system player on Windows. It is not an interactive timeline UI.

Success example: `{"ok":true,"output":"C:\\...\\result.mp4","duration":8.0,"scenes":2,"width":1280,"height":720,"fps":30}`.

Error example: `{"ok":false,"error":"Source not found: ..."}` with nonzero exit status. Fix the specific error and retry. Do not substitute empty videos or fake progress.

## Working beside the window

`editor.py --follow FOLDER` shows the CodeCut project being edited in that folder and reloads it whenever its file
changes (unsaved edits made in the window are never overwritten). Code Doctor opens it this way for `@CodeCut`; the
window's **AI 剪辑** button runs `codedoctor fix --with codecut --no-window` in the project's folder and follows the
file the same way.

