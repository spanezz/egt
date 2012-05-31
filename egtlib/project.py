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


class LogParser(object):
    re_yearline = re.compile("(?:^|\n)\s*(?P<year>[12][0-9]{3})\s*(?:$|\n)")
    re_loghead = re.compile(r"^(?P<day>[0-9 ][0-9]) (?P<month>\w+)(?:\s+(?P<year>\d+))?:\s+(?P<start>\d+:\d+)-\s*(?P<end>\d+:\d+)")

    def __init__(self):
        self.year = datetime.date.today().year
        self.begin = None
        self.until = None
        self.logbody = []

    def flush(self):
        res = dict(
            begin=self.begin,
            until=self.until,
            logbody="\n".join(self.logbody),
        )
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
                self.until = datetime.datetime.combine(date, parsetime(mo.group("end")))
                continue

            self.logbody.append(line)
        if self.begin is not None: yield self.flush()


class Project(object):
    def __init__(self, path, basename="ore"):
        self.path = path
        self.name = os.path.basename(path)
        self.fname = os.path.join(self.path, basename)

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
            self.meta = dict(email.message_from_string(head))

            # Extract the log from the rest
            t = re_secsep.split(body, 1)
            if len(t) == 1:
                head, body = "", t[0]
            else:
                head, body = t

        # Parse head as log entries
        self.log = list(LogParser().parse(head.split("\n")))

        # Parse/store body
        self.body = body

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
                "--working-directory=" + self.path
            ]
            if with_editor:
                cmdline.append("-e")
                cmdline.append("vim ore")
            p = subprocess.Popen(cmdline, stdin=devnull, stdout=devnull, stderr=devnull, cwd=self.path, close_fds=True)

    def summary(self, out=sys.stdout):
        print >>out, "%s: %s" % (self.name, self.path)
        print >>out, "  %d log entries" % (len(self.log))
