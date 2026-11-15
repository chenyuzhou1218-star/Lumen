# Making a web page with CodePage

A page is `page.json`. The person drags in a window; you write the same file. Do not write HTML by hand unless a component cannot do it: then use the `html` component.

## The way of working

1. Decide who the page is for and the one thing it must get them to do.
2. Write `page.json`: `title`, `description`, `theme` (one of the themes, or your own colours), `blocks`.
3. `check` it, then `build` with pictures. Look at BOTH pictures, computer and phone.
4. Fix the biggest thing, build again, at least two rounds.

## A block

```json
{"id": "a1b2c3", "type": "hero-center", "values": {"title": "...", "text": "..."}, "style": {"padTop": 40}}
```

Fields you leave out keep their sample text, so fill every text: a page must never go out saying 卡片标题. `id` is any unique word.

Columns hold blocks in `children`, one list per column:

```json
{"id": "r1", "type": "row3", "children": [[{"id": "c1", "type": "card", "values": {}}], [], []]}
```

`style`: padTop, padBottom, marginTop, marginBottom, minHeight, radius (numbers, pixels), width (percent), align (left, center, right), bg, color, shadow (true), valign (center, bottom: where the content sits when minHeight makes the block taller), anim (up, fade, zoom, left, right: how it appears when scrolled to).

Fields of type lines hold one row per line, parts split by `|`: `"首页|#\n关于|about.html"`. An image is a path or address; `@photo`, `@portrait`, `@city`, `@sea`, `@forest`, `@desk`, `@product`, `@abstract`, `@warm`, `@app`, `@face1` ... `@face4` are drawn placeholders, to be replaced when a real picture exists. A field whose label says 图标名 takes one of the icon names listed there.

There are over 600 components. Most come in five looks with the same fields: `feat-icons3` (plain), `feat-icons3-soft`, `-ink` (inverted), `-brand` (the theme colour), `-glow`. Alternate plain and soft sections, and keep ink or brand for one or two sections that must stand out. `schema` lists them all with their fields.

## Slides

`deck` is a presentation inside the page: each item of `children` is one slide, as many as needed, and each slide holds blocks. The `sl-*` components (cover, agenda, bullets, two-col, pic-right, pic-full, big-num, quote, chart, timeline, compare, cards, table, team, steps, code, end, each with `-soft`, `-ink`, `-brand`, `-glow`) are made for a 16:9 slide; one per slide is usual.

```json
{"id": "d1", "type": "deck", "values": {"auto": "0"}, "children": [[{"id": "s1", "type": "sl-cover-ink", "values": {"title": "..."}}], [{"id": "s2", "type": "sl-bullets", "values": {}}]]}
```

The page shows one slide at a time (arrows, keys, swipe, full screen); printing gives one slide per page.

## What makes a page good

- One idea on the first screen, one main button.
- Real words about the real thing. Never invent reviews, numbers, prices or customers: leave those components out, or ask.
- Few colours: the theme's. A section of `soft` colour between plain ones gives rhythm.
- Space. Sections breathe; add `padTop` rather than more things.
- A search box needs a real target: a search engine address, your own site, or `search-site`, which filters this page. A form's address must be real too.
- Check the phone picture. Long words, wide tables and fixed widths are what break.

## When the page needs a backend

The person may press 写后端: the brief lands in `BACKEND.md` next to `page.json` and comes to you with the request. Write the server in `backend/` with Python's own library unless the person agrees to more, keep the data in local files (SQLite is fine), and change where the forms and buttons go by editing `page.json` (then build), never `index.html` by hand. Start it, send the form once for real, and say what you saw.

Write everything the person will read (titles, slide and page text, narration, labels) in the language they wrote to you in; use 中文 only when they did. The examples and theme names in this guide being 中文 is not a reason to answer in 中文.
