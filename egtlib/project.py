from __future__ import absolute_import
import os.path
import subprocess
import datetime
import sys
import re
from .egtparser import ProjectParser
from .utils import format_duration, format_td
import logging

log = logging.getLogger(__name__)

def default_name(fname):
    """
    Guess a project name from the project file pathname
    """
    dirname, basename = os.path.split(fname)
    if basename in ("ore", ".egt", "egt"):
        # Use dir name
        return os.path.basename(dirname)
    else:
        # Use file name
        return basename[:-4]


def default_tags(fname):
    """
    Guess tags from the project file pathname
    """
    tags = set()
    debhome = os.environ.get("DEBHOME", None)
    if debhome is not None and fname.startswith(debhome):
        tags.add("debian")
    # FIXME: this is currently only valid for Enrico
    if "/lavori/truelite/" in fname: tags.add("truelite")
    return tags


class Project(object):
    def __init__(self, fname):
        self.fname = fname
        # Default values, can be overridden by file metadata
        self.path = os.path.dirname(fname)
        self.name = default_name(fname)
        self.tags = default_tags(fname)
        self.editor = os.environ.get("EDITOR", "vim")
        # Load the actual data
        self.load()

    def load(self):
        self.meta = {}
        self.log = []
        self.body = None

        self.parser = ProjectParser()
        self.parser.parse(fname=self.fname)

        self.meta = self.parser.meta
        self.log = self.parser.log
        self.body = self.parser.body

        # Amend path using meta's path if found
        self.path = self.meta.get("path", self.path)
        self.name = self.meta.get("name", self.name)
        self.editor = self.meta.get("editor", self.editor)
        if 'tags' in self.meta:
            self.tags = set(re.split("[ ,\t]+", self.meta["tags"]))

    @property
    def last_updated(self):
        """
        Datetime when this project was last updated
        """
        if not self.log: return None
        last = self.log[-1]
        if last.until: return last.until
        return datetime.datetime.now()

    @property
    def elapsed(self):
        mins = 0
        for l in self.log:
            mins += l.duration
        return mins

    @property
    def formatted_elapsed(self):
        return format_duration(self.elapsed)

    @property
    def formatted_tags(self):
        return ", ".join(sorted(self.tags))

    @property
    def next_actions(self):
        for el in self.body:
            if el.TAG != "next-actions": continue
            yield el

    def spawn_terminal(self, with_editor=False):
        import pipes
        with open("/dev/null", "rw+") as devnull:
            cmdline = [
                "x-terminal-emulator",
            ]
            if with_editor:
                cmdline.append("-e")
                cmdline.append("sh")
                cmdline.append("-c")
                cmdline.append(self.editor + " " + pipes.quote(self.fname))
            subprocess.Popen(cmdline, stdin=devnull, stdout=devnull, stderr=devnull, cwd=self.path, close_fds=True)
            # Let go in the background

    def run_editor(self):
        p = subprocess.Popen([self.editor, self.fname], cwd=self.path, close_fds=True)
        p.wait()

    def run_grep(self, args):
        for gd in self.gitdirs():
            cwd = os.path.abspath(os.path.join(gd, ".."))
            cmd = ["git", "grep"] + args
            log.info("%s: git grep %s", cwd, " ".join(cmd))
            p = subprocess.Popen(cmd, cwd=cwd, close_fds=True)
            p.wait()


    def summary(self, out=sys.stdout):
        mins = self.elapsed
        lu = self.last_updated
        stats = []
        if self.tags:
            stats.append("tags: %s" % ",".join(sorted(self.tags)))
        if lu is None:
            stats.append("never updated")
        else:
            stats.extend([
                "%d log entries" % len(self.log),
                "%s" % format_duration(mins),
                "last %s (%s ago)" % (
                    self.last_updated.strftime("%Y-%m-%d %H:%M"),
                    format_td(datetime.datetime.now() - self.last_updated)),
            ])
        print "%s\t%s" % (self.name, ", ".join(stats))

    def gitdirs(self, depth=2, root=None):
        """
        Find all .git directories below the project path
        """
        # Default to self.path
        if root is None:
            root = self.path

        # Check the current dir
        cand = os.path.join(root, ".git")
        if os.path.exists(cand):
            yield cand

        # Recurse into subdirs if we still have some way to go
        if depth > 1:
            for fn in os.listdir(root):
                if fn.startswith("."): continue
                d = os.path.join(root, fn)
                if os.path.isdir(d):
                    for gd in self.gitdirs(depth - 1, d):
                        yield gd

    def backup(self, tarout):
        # Backup the main todo/log file
        tarout.add(self.fname)
        if 'abstract' not in self.meta:
            for gd in self.gitdirs():
                tarout.add(os.path.join(gd, "config"))
                hookdir = os.path.join(gd, "hooks")
                for fn in os.listdir(hookdir):
                    if fn.startswith("."): continue
                    if fn.endswith(".sample"): continue
                    tarout.add(os.path.join(hookdir, fn))
        # TODO: a shellscript with command to clone the .git again
        # TODO: a diff with uncommitted changes
        # TODO: the content of directories optionally listed in metadata
        #       (documentation, archives)
        # (if you don't push, you don't back up, and it's fair enough)

    @classmethod
    def has_project(cls, fname):
        return os.path.exists(fname)
