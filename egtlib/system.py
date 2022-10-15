from __future__ import annotations

import os
import subprocess
import sys


def run_editor(proj):
    editor = proj.meta.get("editor", None)
    if editor is None:
        editor = os.environ.get("EDITOR", "vim")
    p = subprocess.Popen([editor, proj.abspath], cwd=proj.path, close_fds=True)
    p.wait()


def run_work_session(proj, with_editor=True):
    pid = os.fork()
    if pid > 0:
        return

    argv0 = os.path.abspath(sys.argv[0])

    # Move to the project directory
    os.chdir(proj.path)

    # Detach from terminal
    os.setsid()

    cmdline = [
        "x-terminal-emulator",
    ]
    if with_editor:
        cmdline.append("-e")
        cmdline.append(argv0)
        cmdline.append("edit")
        cmdline.append(proj.name)

    # Close file descriptors
    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()
    proc = subprocess.Popen(cmdline, cwd=proj.path, close_fds=True)
    proc.wait()
    sys.exit(0)
