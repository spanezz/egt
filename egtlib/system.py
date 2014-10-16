# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import os
import sys
import subprocess
try:
    import dbus
except ImportError:
    dbus = None


def run_editor(proj):
    if dbus:
        session_bus = dbus.SessionBus()
        try:
            buffy_obj = session_bus.get_object("org.enricozini.buffy", "/buffy")
            buffy = dbus.Interface(buffy_obj, dbus_interface="org.enricozini.buffy")
        except:
            buffy = None
    else:
        buffy = None

    if buffy:
        buffy.set_active_inbox(".egt.{}".format(proj.name).encode("utf-8"), True)

    p = subprocess.Popen([proj.editor, proj.fname], cwd=proj.path, close_fds=True)
    p.wait()

    if buffy:
        buffy.set_active_inbox(".egt.{}".format(proj.name), False)


def run_work_session(proj, with_editor=True):
    pid = os.fork()
    if pid > 0: return

    argv0 = os.path.abspath(sys.argv[0])

    # Move to the project directory
    os.chdir(proj.path)

    # Detach from terminal
    os.setsid()

    # Close file descriptors
    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()

    cmdline = [
        "x-terminal-emulator",
    ]
    if with_editor:
        cmdline.append("-e")
        cmdline.append(argv0)
        cmdline.append("edit")
        cmdline.append(proj.name)
    proc = subprocess.Popen(cmdline, cwd=proj.path, close_fds=True)
    proc.wait()
