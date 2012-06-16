from __future__ import absolute_import
import os.path
import subprocess
import datetime
import sys
import re

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


def parsetime(s):
    h, m = s.split(":")
    return datetime.time(int(h), int(m), 0)


def format_duration(mins):
    h = mins / 60
    m = mins % 60
    if m:
        return "%dh %dm" % (h, m)
    else:
        return "%dh" % h


def format_td(td):
    if td.days > 0:
        return "%d days" % td.days
    else:
        return format_duration(td.seconds / 60)


class Log(object):
    def __init__(self, begin, until, body):
        self.begin = begin
        self.until = until
        self.body = body

    @property
    def duration(self):
        """
        Return the duration in minutes
        """
        if not self.until:
            until = datetime.datetime.now()
        else:
            until = self.until

        td = (until - self.begin)
        return (td.days * 86400 + td.seconds) / 60

    @property
    def formatted_duration(self):
        return format_duration(self.duration)

    def output(self, project=None):
        head = [self.begin.strftime("%d %B: %H:%M-")]
        if self.until:
            head.append(self.until.strftime("%H:%M "))
            head.append(format_duration(self.duration))
        if project is not None:
            head.append(" [%s]" % project)
        print "".join(head)
        print self.body


class LogParser(object):
    re_yearline = re.compile("(?:^|\n)\s*(?P<year>[12][0-9]{3})\s*(?:$|\n)")
    re_loghead = re.compile(r"^(?P<day>[0-9 ][0-9]) (?P<month>\w+)(?:\s+(?P<year>\d+))?:\s+(?P<start>\d+:\d+)-\s*(?P<end>\d+:\d+)?")

    def __init__(self):
        self.year = datetime.date.today().year
        self.begin = None
        self.until = None
        self.logbody = []

    def flush(self):
        res = Log(self.begin, self.until, "\n".join(self.logbody))
        self.begin = None
        self.end = None
        self.logbody = []
        return res

    def parse(self, lines):
        for line in lines:
            mo = self.re_yearline.match(line)
            if mo:
                if self.begin is not None: yield self.flush()
                self.year = int(mo.group("year"))
                continue

            mo = self.re_loghead.match(line)
            if mo:
                if self.begin is not None: yield self.flush()
                if mo.group("year"): self.year = int(mo.group("year"))
                date = datetime.date(self.year, MONTHS[mo.group("month")], int(mo.group("day")))
                self.begin = datetime.datetime.combine(date, parsetime(mo.group("start")))
                if mo.group("end"):
                    self.until = datetime.datetime.combine(date, parsetime(mo.group("end")))
                    if self.until < self.begin:
                        # Deal with intervals across midnight
                        self.until += datetime.timedelta(days=1)
                else:
                    self.until = None
                continue

            self.logbody.append(line)
        if self.begin is not None: yield self.flush()


class Project(object):
    def __init__(self, path, basename="ore"):
        self.path = path
        self.name = os.path.basename(path)
        self.fname = os.path.join(self.path, basename)
        self.tags = set()
        self.editor = os.environ.get("EDITOR", "vim")
        # TODO: make configurable, use as default of no Tags: header is found
        # in metadata
        if "dev/deb" in self.path: self.tags.add("debian")
        if "lavori/truelite" in self.path: self.tags.add("truelite")

    def load(self):
        self.meta = {}
        self.log = []
        self.body = None

        re_secsep = re.compile("\n\n+")

        with open(self.fname) as fd:
            body = fd.read()

        # Split on the first empty line
        t = re_secsep.split(body, 1)
        if len(t) == 1:
            head, body = t[0], ""
        else:
            head, body = t
        if not LogParser.re_yearline.match(head) and not LogParser.re_loghead.match(head):
            # There seems to be metadata: parse it as RFC822 fields
            import email
            self.meta = dict(((k.lower(), v) for k, v in email.message_from_string(head).items()))

            # Extract the log from the rest
            t = re_secsep.split(body, 1)
            if len(t) == 1:
                head, body = "", t[0]
            else:
                head, body = t

        # Amend path using meta's path if found
        self.path = self.meta.get("path", self.path)

        # Parse head as log entries
        self.log = list(LogParser().parse(head.split("\n")))

        # Parse/store body
        self.body = body

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

    def from_cp(self, cp):
        """
        Load information about this Project from a ConfigParser
        """
        secname = "dir %s" % self.path
        if not cp.has_section(secname):
            return

        if cp.has_option(secname, "name"):
            self.name = cp.get(secname, "name")

    def to_cp(self, cp):
        """
        Store information about this Project in a ConfigParser
        """
        secname = "dir %s" % self.path
        cp.add_section(secname)
        cp.set(secname, "name", self.name)

    def spawn_terminal(self, with_editor=False):
        with open("/dev/null", "rw+") as devnull:
            cmdline = [
                "x-terminal-emulator",
            ]
            if with_editor:
                cmdline.append("-e")
                cmdline.append("sh")
                cmdline.append("-c")
                cmdline.append(self.editor + " ore")
            subprocess.Popen(cmdline, stdin=devnull, stdout=devnull, stderr=devnull, cwd=self.path, close_fds=True)
            # Let go in the background

    def run_editor(self):
        p = subprocess.Popen([self.editor, "ore"], cwd=self.path, close_fds=True)
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
    def has_project(cls, path, basename="ore"):
        fname = os.path.join(path, basename)
        return os.path.exists(fname)
