"""Screenshots of a tool's page with real sample data, in Edge through playwright (nothing shows on the desktop).

    python webkit/shot.py <tool> <out_dir> [project args...] [--size 1280x820] [--name base] [--js file]
The data is what the tool's own Python answers for that project (its api_boot), so the picture is what the window
shows; the page is the built ui_dist. One picture in 浅色 and one in 深色."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
TOOLS = Path(__file__).resolve().parents[1]


def run_now(project, index: int) -> None:
    """An action run to its end before the picture (what pressing its button does), so the page shows what came out."""
    import subprocess

    action = project.cfg.actions[index]
    out = subprocess.run([sys.executable, str(project.cfg.tool), *[str(a).replace('{folder}', project.target()) for a in action.args]],
                         capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, creationflags=0x08000000 if os.name == 'nt' else 0)
    project.buffer, project.running, project.after = out.stdout, action.label, ''
    project.done()


def sample(tool: str, argv: list, runs: list | None = None) -> dict:
    sys.path.insert(0, str(TOOLS / tool))
    sys.path.append(str(Path(__file__).resolve().parent))
    os.chdir(TOOLS / tool)
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 (the project's timers want one)
    editor = importlib.import_module('editor')
    from check import keep_prefs

    keep_prefs(editor)
    if hasattr(editor, 'sample_for_shot') and not runs:
        return editor.sample_for_shot(argv)
    import app_window

    folder, watch, _ = app_window.args_of(argv)
    project = getattr(editor, 'PROJECT', app_window.Project)(editor.CONFIG, folder, watch)
    project.show_pictures()
    for i in runs or []:
        run_now(project, i)
    return {'boot': project.api_boot(), 'answers': {'ai_state': project.ai.state()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('tool')
    ap.add_argument('out')
    ap.add_argument('--size', default='1280x820')
    ap.add_argument('--name', default='')
    ap.add_argument('--run', type=int, action='append', help='run this action (its index) first, as its button would')
    ap.add_argument('--js', help='JavaScript run before the picture (open a menu, a panel...)')
    ap.add_argument('args', nargs='*')
    a = ap.parse_args()
    data = sample(a.tool, a.args, a.run)
    from playwright.sync_api import sync_playwright

    w, h = (int(v) for v in a.size.split('x'))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    page_url = (TOOLS / a.tool / 'ui_dist' / 'index.html').as_uri()
    base = a.name or a.tool
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=['--allow-file-access-from-files'])
        for mode in ('light', 'dark'):
            page = browser.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
            page.add_init_script(f'window.__SAMPLE__ = {json.dumps(data, ensure_ascii=False)};')
            page.goto(f'{page_url}?mode={mode}&still=1')
            page.wait_for_selector('.app > *', timeout=15000)
            if os.environ.get('SHOT_LANG'):  # what the window does once the page is loaded: the words in Lumen's language (CODEDOCTOR_HOME/ui.json)
                sys.path.insert(0, str(TOOLS / a.tool))
                import i18n
                script = i18n.web_script(TOOLS / a.tool, TOOLS / a.tool / 'ui' / 'kit')
                if script:
                    page.evaluate(script)
            page.wait_for_timeout(500)
            if a.js:
                page.evaluate(Path(a.js).read_text(encoding='utf-8'))
                page.wait_for_timeout(400)
            name = out / f'{base}-{"浅色" if mode == "light" else "深色"}.png'
            page.screenshot(path=str(name))
            print(name)
            page.close()
        browser.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
