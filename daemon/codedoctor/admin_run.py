"""Run one command as administrator, for any agent (Codex, Claude Code, Lumen's own): Windows shows its own UAC question and
the user decides there. Prints what the command printed; the exit code is the command's (1223: the user said no).

    python -m codedoctor.admin_run "Remove-Item C:\\Windows\\Temp\\* -Recurse -Force"
"""

from __future__ import annotations

import os
import sys


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m codedoctor.admin_run \"<PowerShell command>\"")
        return 2
    if os.name != "nt":
        os.execvp("sudo", ["sudo", "sh", "-c", " ".join(argv)])
    from codedoctor.agents.tools import run_as_admin

    code, out = run_as_admin(" ".join(argv), os.getcwd())
    sys.stdout.write(out)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
