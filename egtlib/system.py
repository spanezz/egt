"""
Facilities to run external commands.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .project import Project


def run_editor(proj: Project) -> None:
    """
    Edit the .egt file for the give Project
    """
    editor = proj.meta.get("editor", None)
    if editor is None:
        editor = os.environ.get("EDITOR", "vim")
    p = subprocess.Popen([editor, proj.abspath], cwd=proj.path, close_fds=True)
    p.wait()


def run_work_session(proj: Project, with_editor: bool = True) -> None:
    """
    Open a terminal on the working directory of the given project, optionally
    opening the project file in an editor inside the terminal
    """
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
