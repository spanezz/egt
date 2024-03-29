from __future__ import annotations

import datetime
import fcntl
import os
import os.path
import select
import subprocess
import tempfile
from collections import defaultdict
from typing import IO, TYPE_CHECKING, Callable, Optional, Sequence

if TYPE_CHECKING:
    import egtlib


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


class SummaryCol:
    def __init__(
            self,
            label: str,
            align: str,
            func: Optional[Callable[[egtlib.Project], str]] = None):
        self.label = label
        self.align = align
        self._func = func

    def init_data(self):
        pass

    def func(self, p: egtlib.Project) -> str:
        if self._func:
            return self._func(p)
        else:
            return ""


class TaskStatCol(SummaryCol):
    def __init__(self, label: str, align: str, projs: Sequence[egtlib.Project]):
        super().__init__(label, align)
        self.task_stats: dict[str, int] = defaultdict(int)
        self._proj: Optional[egtlib.Project]
        try:
            self._proj = projs[0]
        except IndexError:
            self._proj = None

    def init_data(self):
        if self._proj is None:
            return
        tasks = self._proj.body.tasks.tw.filter_tasks({"status": "pending"})
        # could not figure out how to do this in one go
        tasks += self._proj.body.tasks.tw.filter_tasks({"status": "waiting"})
        for task in tasks:
            try:
                self.task_stats[task["project"]] += 1
            except KeyError:
                pass

    def func(self, p):
        return str(self.task_stats[p.name])


class HoursCol(SummaryCol):
    def func(self, p):
        return format_duration(p.elapsed, tabular=True) if p.last_updated else "--"


class LastEntryCol(SummaryCol):
    def __init__(self, *args):
        super().__init__(*args)
        self.now = datetime.datetime.now()

    def func(self, p):
        if p.last_updated:
            return format_td(self.now - p.last_updated, tabular=True) + " ago"
        else:
            return "--"


def format_duration(mins: int, tabular: bool = False) -> str:
    """
    Format a time duration in minutes
    """
    h = mins // 60
    m = mins % 60
    if tabular:
        return f"{h:3d}h {m:02d}m"
    else:
        if m:
            return f"{h}h {m}m"
        else:
            return f"{h}h"


def format_td(td: datetime.timedelta, tabular=False) -> str:
    """
    Format a timedelta object
    """
    if tabular:
        if td.days == 0:
            return format_duration(td.seconds // 60, tabular=True)
        elif td.days == 1:
            return f"{td.days:3d} day"
        else:
            return f"{td.days:3d} days"
    else:
        if td.days == 0:
            return format_duration(td.seconds // 60)
        elif td.days == 1:
            return f"{td.days} day"
        else:
            return f"{td.days} days"


def stream_output(proc: "subprocess.Popen"):
    """
    Take a subprocess.Popen object and generate its output, line by line,
    annotated with "stdout" or "stderr". At process termination it generates
    one last element: ("result", return_code) with the return code of the
    process.
    """
    assert proc.stdout is not None
    assert proc.stderr is not None
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
                for line in lines:
                    yield types[idx], line.decode("utf-8")
    res = proc.wait()
    yield "result", res
