# coding: utf-8
import os
import sys
import subprocess
try:
    import dbus
except ImportError:
    dbus = None


def connect_to_buffy():
    if not dbus: return None

    session_bus = dbus.SessionBus()
    try:
        buffy_obj = session_bus.get_object("org.enricozini.buffy", "/buffy")
        return dbus.Interface(buffy_obj, dbus_interface="org.enricozini.buffy")
    except Exception:
        return None


def run_editor(proj):
    buffy = connect_to_buffy()
    if buffy:
        buffy.set_active_inbox(".egt.{}".format(proj.name).encode("utf-8"), True)

    editor = proj.meta.get("editor", None)
    if editor is None:
        editor = os.environ.get("EDITOR", "vim")
    p = subprocess.Popen([editor, proj.abspath], cwd=proj.path, close_fds=True)
    p.wait()

    # Reconnect, in case buffy was restarted while we were working
    # (it's quite useful, for example, when doing 'egt work buffy')
    buffy = connect_to_buffy()
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
