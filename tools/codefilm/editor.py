"""CodeFilm's window: one sentence in, a film out. It is app_window.py with a box for the sentence."""
from __future__ import annotations

from pathlib import Path
import sys

import right_python

right_python.use('PySide6', 'PIL')

from app_window import Action, Config, Project, launch  # noqa: E402

HERE = Path(__file__).resolve().parent


def describe(answer: dict) -> list:
    if answer.get('output', '').endswith('.mp4'):
        return [f"片子做好了：{answer['output']}，{answer.get('seconds')} 秒，{answer.get('shots')} 个镜头，{answer.get('size')}，旁白 {answer.get('narration_lines', 0)} 句"]
    if answer.get('style'):
        return [f"分镜排好了：{answer['style']}风格，{answer['shots']} 个镜头，约 {answer['seconds']} 秒。左边可以改，改完点“做成片子”"]
    return []


IDEA = '一句话写分镜'
# the page asks these before "一句话写分镜" runs (they were two dialogs of their own before)
ASKS = [{'key': 'idea', 'label': '想做一个什么样的片子？', 'placeholder': '例如：做一个一分钟的古风宣传片《山河》', 'required': True},
        {'key': 'lines', 'label': '旁白（可以不写；一行一句，一个镜头念一句）', 'multiline': True}]
CONFIG = Config('CodeFilm', HERE / 'codefilm.py', '一句话出成片：写一句想要的片子，它排好分镜，用 Code3D 渲染画面、CodeSound 作曲、Windows 语音配旁白，再剪成带字幕的视频。草稿几分钟，高清要久一些。',
                ('film.json',), [Action(IDEA, ['plan', '{folder}'], asks=ASKS), Action('做成片子（草稿）', ['build', '{folder}', '--quality', 'draft'], True, 'out/film.mp4'),
                                 Action('做成高清', ['build', '{folder}', '--quality', 'final'], False, 'out/film.mp4')],
                opens=[('打开片子', 'out/film.mp4'), ('打开字幕', 'out/film.srt')], describe=describe)


class FilmProject(Project):
    def run(self, action: Action, values: dict | None = None) -> None:
        if action.label != IDEA:
            super().run(action, values)
            return
        idea = str((values or {}).get('idea') or '').strip()
        lines = str((values or {}).get('lines') or '').strip()
        if not idea:
            return
        if self.folder is None:
            base = Path.home() / 'CodeFilm'
            n = 1
            while (base / f'片子{n}').exists():
                n += 1
            self.folder = base / f'片子{n}'
            self.folder.mkdir(parents=True)
        super().run(Action(IDEA, ['plan', '{folder}', '--idea', idea, '--lines', lines]))

    def done(self, *a) -> None:
        super().done(*a)
        if self.folder is not None and (self.folder / 'film.json').is_file():
            self.load_code()
            self.push()


def window_for_check(argv: list, mode: str | None):
    import app_window
    import webshell

    folder, watch, _ = app_window.args_of(argv)
    return webshell.window(FilmProject(CONFIG, folder, watch), CONFIG.name, HERE / 'ui_dist', mode=mode, minimum=(380, 300))


PROJECT = FilmProject  # what webkit/shot.py makes


if __name__ == '__main__':
    sys.exit(launch(CONFIG, FilmProject))
