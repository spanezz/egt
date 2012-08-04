# coding: utf-8

import tempfile
import os.path
import os


class atomic_writer(object):
    """
    Atomically write to a file
    """
    def __init__(self, fname, mode=0664, sync=True):
        self.fname = fname
        self.mode = mode
        self.sync = sync
        dirname = os.path.dirname(self.fname)
        self.outfd = tempfile.NamedTemporaryFile(dir=dirname)

    def __enter__(self):
        return self.outfd

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.outfd.flush()
            if self.sync:
                os.fdatasync(self.outfd.fileno())
            os.fchmod(self.outfd.fileno(), self.mode)
            os.rename(self.outfd.name, self.fname)
            self.outfd.delete = False
        self.outfd.close()
        return False


def intervals_intersect(p1s, p1e, p2s, p2e):
    """
    Return True if the two intervals intersect
    """
    if p1e is not None and p2s is not None and p1e < p2s: return False
    if p1s is not None and p2e is not None and p1s > p2e: return False
    return True


def format_duration(mins, tabular=False):
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
