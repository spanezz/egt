from typing import IO
import subprocess
import tempfile
import os.path
import os
import fcntl
import select
import datetime


def today() -> datetime.date:
    """
    Mockable version of datetime.date.today()
    """
    return datetime.date.today()


class atomic_writer(object):
    """
    Atomically write to a file
    """
    def __init__(self, fname: str, mode: str, osmode: int = 0o644, sync: bool = True, **kw):
        self.fname = fname
        self.osmode = osmode
        self.sync = sync
        dirname = os.path.dirname(self.fname)
        self.fd, self.abspath = tempfile.mkstemp(dir=dirname, text="b" not in mode)
        self.outfd = open(self.fd, mode, closefd=True, **kw)

    def __enter__(self) -> IO:
        return self.outfd

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.outfd.flush()
            if self.sync:
                os.fdatasync(self.fd)
            os.fchmod(self.fd, self.osmode)
            os.rename(self.abspath, self.fname)
        else:
            os.unlink(self.abspath)
        self.outfd.close()
        return False


def intervals_intersect(p1s, p1e, p2s, p2e):
    """
    Return True if the two intervals intersect
    """
    if p1e is not None and p2s is not None and p1e < p2s:
        return False
    if p1s is not None and p2e is not None and p1s > p2e:
        return False
    return True


def format_duration(mins: int, tabular: bool = False):
    h = mins / 60
    m = mins % 60
    if tabular:
        return "%3dh %02dm" % (h, m)
    else:
        if m:
            return "%dh %dm" % (h, m)
        else:
            return "%dh" % h


def format_td(td, tabular=False):
    if tabular:
        if td.days > 0:
            return "%3d days" % td.days
        else:
            return format_duration(td.seconds / 60, tabular=True)
    else:
        if td.days > 0:
            return "%d days" % td.days
        else:
            return format_duration(td.seconds / 60)


def stream_output(proc: "subprocess.Popen"):
    """
    Take a subprocess.Popen object and generate its output, line by line,
    annotated with "stdout" or "stderr". At process termination it generates
    one last element: ("result", return_code) with the return code of the
    process.
    """
    fds = [proc.stdout, proc.stderr]
    bufs = [b"", b""]
    types = ["stdout", "stderr"]
    # Set both pipes as non-blocking
    for fd in fds:
        fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
    # Multiplex stdout and stderr with different prefixes
    while len(fds) > 0:
        s = select.select(fds, (), ())
        for fd in s[0]:
            idx = fds.index(fd)
            buf = fd.read()
            if len(buf) == 0:
                fds.pop(idx)
                if len(bufs[idx]) != 0:
                    yield types[idx], bufs.pop(idx).decode("utf-8")
                types.pop(idx)
            else:
                bufs[idx] += buf
                lines = bufs[idx].split(b"\n")
                bufs[idx] = lines.pop()
                for l in lines:
                    yield types[idx], l.decode("utf-8")
    res = proc.wait()
    yield "result", res
