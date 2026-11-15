# Making a short film with CodeFilm

A film is `film.json`. CodeFilm renders each shot with Code3D, writes the music with CodeSound, reads the narration with a Windows voice, and cuts it all into `out/film.mp4` with subtitles.

## The way of working

1. Write down what the film is for, who watches it, and how long it is. One idea.
2. `plan` with the user's sentence gives a first storyboard by rule. Then write it properly yourself:
   - A shot is a picture the camera moves over: `scene`, `seconds`, `move` (推近 拉远 左移 右移 静止), `say` (the narration), `text` (the subtitle, by default what is said).
   - Use the ready scenes when they fit. For anything else, write a Code3D scene file in the project (for example `scenes/my_shot.py`, written with Code3D's c3d kit and following Code3D's guide) and give its path as `scene`. Render it with Code3D first and look at it before it goes into the film.
   - Narration: short sentences, one per shot, said in about the shot's length. Never invent facts, names or figures about the user's product or story: ask, or keep to what they said.
3. `build --quality draft` and look at `out/shots.png`, every shot. Fix the weakest, build again.
4. `build --quality final` once at the end: it renders at 1920×1080 and takes much longer.

## film.json

```json
{"title": "片名", "subtitle": "", "style": "古风",
 "music": {"style": "古风", "seed": 3},
 "voice": {"on": true, "name": "", "rate": 0},
 "shots": [{"scene": "山水晨雾", "seconds": 6, "move": "推近", "say": "山河依旧"}],
 "end": "谢谢观看"}
```

`music` may be `{"file": "song.wav"}` for the user's own, or `null` for none. Music styles are CodeSound's. A shot grows to fit its narration. The music steps back while the voice speaks.

Say in your report what you saw in the shots and what you changed. Whether the film moves anyone is the user's to judge.

Write everything the person will read (titles, slide and page text, narration, labels) in the language they wrote to you in; use 中文 only when they did. The examples and theme names in this guide being 中文 is not a reason to answer in 中文.
