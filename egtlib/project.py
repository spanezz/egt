import os.path
import subprocess
import datetime
import re
import sys
from collections import OrderedDict
from .egtparser import ProjectParser
from .utils import format_duration, intervals_intersect
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


def default_tags(config, fname):
    """
    Guess tags from the project file pathname
    """
    tags = set()

    if "autotag" in config:
        autotags = config["autotag"]
        if autotags is not None:
            for tag, regexp in autotags.items():
                if re.search(regexp, fname):
                    tags.add(tag)

    return tags


def parse_duration(s):
    """
    Parse a duration like 3d 8h 30m, returning its value in minutes
    """
    mins = 0
    for tok in s.split():
        if tok.endswith("d"):
            mins += int(tok[:-1]) * (24 * 60)
        elif tok.endswith("h"):
            mins += int(tok[:-1]) * 60
        elif tok.endswith("m"):
            mins += int(tok[:-1])
        else:
            raise ValueError("cannot parse '%s' in '%s'" % (tok, s))
    return mins


class Project(object):
    def __init__(self, fname=None, path=None, name=None, tags=set()):
        if path is None and fname is not None:
            path = os.path.dirname(fname)
        self.fname = fname
        self.path = path
        self.name = name
        self.tags = tags
        self.editor = None

    @classmethod
    def from_file(self, config, fname):
        # Default values, can be overridden by file metadata
        p = Project(
            fname=fname,
            path=os.path.dirname(fname),
            name=default_name(fname),
            tags=default_tags(config, fname)
        )
        # Load the actual data
        p.load()
        return p

    def load(self):
        self.meta = OrderedDict()
        self.log = []
        self.body = None

        self.parser = ProjectParser(self.fname)
        self.parser.parse()

        self.meta = self.parser.meta
        self.log = self.parser.log
        self.body = self.parser.body

        # Amend path using meta's path if found
        self.path = self.meta.get("path", self.path)
        self.name = self.meta.get("name", self.name)
        self.editor = self.meta.get("editor", self.editor)
        if 'tags' in self.meta:
            self.tags = set(re.split("[ ,\t]+", self.meta["tags"]))

        # If we're doing daily billing, annotate log entries with the number of
        # days (or fraction of days) accounted for them
        if self.meta.get("billing", "hourly") == "daily":
            self.annotate_log_with_daily_billing()

        # Allow to group archived projects with the same name
        # Set it now before we potentially mangle the name
        self.group = self.name

        # Quick access to 'archive' meta attribute
        if self.meta.get("archived", "false").lower() in ("true", "yes"):
            self.archived = True
            since, until = self.formal_period
            if until:
                self.name += until.strftime("-%Y-%m-%d")
            elif since:
                self.name += since.strftime("-%Y-%m-%d")

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
    def daymins(self):
        """
        Return the number of minutes per work day
        """
        return parse_duration(self.meta.get("day", "8h"))

    @property
    def elapsed(self):
        mins = 0
        for l in self.log:
            mins += l.duration
        return mins

    def annotate_log_with_daily_billing(self):
        # Find out which is the last log entry for each day
        lastentries = {}
        for l in self.log:
            lastentries[l.begin.date()] = l

        # Compute effective work time for each day
        days = self.compute_daily_billing()

        # Annotate the last log entries with the work time, all others with 0
        for l in self.log:
            if lastentries[l.begin.date()] == l:
                l.day_billing = days[l.begin.date()]
            else:
                l.day_billing = 0.0

    def compute_daily_billing(self):
        """
        For each day in the log, compute the number of work days or half work
        days logged for it.
        """
        daymins = float(self.daymins)

        # Iterate logs, aggregating the number of minutes per day
        days = {}
        for l in self.log:
            d = l.begin.date()
            if d in days:
                days[d] += l.duration
            else:
                days[d] = l.duration

        # Iterate days
        karma = 0
        res = {}
        for d, mins in sorted(days.items()):
            # Allow one hour slack
            if mins >= (daymins/2 - 60) and mins < daymins/2:
                mins = daymins/2
            elif mins >= daymins-60 and mins < daymins:
                mins = daymins

            # Apply minutes carried forward from old roundings
            amount = mins + karma

            if amount < daymins/4:
                # Skip day
                account = 0.0
            elif abs(daymins/2 - amount) < abs(daymins - amount):
                # Closer to half day
                account = 0.5
            elif amount > daymins * 1.5:
                # More than a day and a half: count a day and a half
                account = 1.5
            else:
                # Closer to full day
                account = 1.0

            res[d] = account
            #print d, "%4.1f + %4.1f = %4.1f" % (mins/60, karma/60, amount/60),\
            #         "-> %4.1f + %4.1f" % (account, (amount-account*daymins)/60), dcount
            karma = amount - account * daymins

        return res

    @property
    def elapsed_days(self):
        days = self.compute_daily_billing()
        return sum(days.values())

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

    @property
    def contexts(self):
        """
        Return a set with all contexts in this project
        """
        res = set()
        for el in self.body:
            if el.TAG != "next-actions": continue
            res |= el.contexts
        return res

    @property
    def formal_period(self):
        """
        Compute the begin and end dates for this project.

        If Start-date and End-date are provided in the metadata, return those.
        Else infer them from the first or last log entries.
        """
        since = self.meta.get("start-date", None)
        until = self.meta.get("end-date", None)
        if since is None and self.log:
            since = self.log[0].begin.date()
        elif since is not None:
            since = datetime.datetime.strptime(since, "%Y-%m-%d").date()
        if until is None and self.log:
            until = self.log[-1].until
            if until is None:
                # Deal with entries that are still open
                until = datetime.date.today()
            else:
                until = until.date()
        elif until is not None:
            until = datetime.datetime.strptime(until, "%Y-%m-%d").date()
        return since, until

    def next_events(self, since=None, until=None):
        """
        Return the next events within the given date range
        """
        for na in self.next_actions:
            if na.event is None: continue
            d_since = na.event.get("start", None)
            if d_since is not None: d_since = d_since.date()
            d_until = na.event.get("end", None)
            if d_until is not None:
                d_until = d_until.date()
            else:
                d_until = d_since
            if not intervals_intersect(d_since, d_until, since, until): continue
            yield na

    def spawn_terminal(self, with_editor=False):
        from .system import run_work_session
        run_work_session(self, with_editor)

    def run_editor(self):
        from .system import run_editor
        run_editor(self)

    def run_grep(self, args):
        from .utils import stream_output
        for gd in self.gitdirs():
            cwd = os.path.abspath(os.path.join(gd, ".."))
            cmd = ["git", "grep"] + args
            log.info("%s: git grep %s", cwd, " ".join(cmd))
            p = subprocess.Popen(cmd, cwd=cwd, close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for ltype, line in stream_output(p):
                if ltype == "stdout":
                    print("{}:{}".format(self.name, line), file=sys.stdout)
                elif ltype == "stderr":
                    print("{}:{}".format(self.name, line), file=sys.stderr)

    def gitdirs(self, depth=2, root=None):
        """
        Find all .git directories below the project path
        """
        # Default to self.path
        if root is None:
            root = self.path

        # Check the current dir
        cand = os.path.join(root, ".git")
        if os.path.isdir(cand):
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

        # Add all paths listed in the 'backup' metadata, one per line
        for p in [x.strip() for x in self.meta.get("backup", "").split("\n")]:
            if not p: continue
            path = os.path.join(self.path, p)
            if not os.path.exists(path): continue
            tarout.add(path)

    @classmethod
    def has_project(cls, fname):
        return os.path.exists(fname)
