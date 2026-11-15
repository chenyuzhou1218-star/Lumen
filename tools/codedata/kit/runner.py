"""Runs analysis.py, kept to its own folder and off the network (guard.py)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import sys
import traceback

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))

import guard  # noqa: E402


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    folder = Path(job['folder'])
    script = folder / job['script']
    answer_at = Path(job['answer'])
    import cd

    guard.install(folder, [str(KIT), str(Path(os.__file__).parent), str(Path(sys.executable).parent), sys.base_prefix], str(script))

    def where() -> dict:
        tb = sys.exc_info()[2]
        line = None
        while tb is not None:
            if Path(tb.tb_frame.f_code.co_filename) == script:
                line = tb.tb_lineno
            tb = tb.tb_next
        return {'line': line} if line else {}

    try:
        os.chdir(folder)
        sys.path.insert(0, str(folder))
        runpy.run_path(str(script), run_name='__main__')
        answer = {'ok': True, **cd.finish(folder)}
    except cd.DataError as e:
        answer = {'ok': False, 'error': str(e), **where()}
    except Exception as e:  # noqa: BLE001 (the report of it is the point)
        answer = {'ok': False, 'error': f'{type(e).__name__}: {e}', **where(), 'trace': traceback.format_exc()[-1200:]}
    answer_at.write_text(json.dumps(answer, ensure_ascii=False, default=str), encoding='utf-8')
    return 0 if answer['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
