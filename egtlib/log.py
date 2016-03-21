# coding: utf8
from __future__ import absolute_import
from .utils import format_duration
from .lang import get_parserinfo
import dateutil.parser
import datetime
import sys
import re
import logging

log = logging.getLogger(__name__)


def parsetime(s):
    h, m = s.split(":")
    return datetime.time(int(h), int(m), 0)


class EntryBase:
    re_timebase = re.compile("^(?:(?P<year>\d{4})|-+\s*(?P<date>.+?))\s*$")
    re_entry = re.compile(r"^(?P<date>(?:\S| \d)[^:]*):\s*(?:(?P<start>\d+:\d+)-\s*(?P<end>\d+:\d+)?|$)")
    re_new_time = re.compile(r"^(?P<start>\d{1,2}:\d{2})-?\s*\+?\s*$")
    re_new_day = re.compile(r"^\+\+?\s*$")

    def __init__(self, body=None):
        # List of lines with the body of the log entry
        if body is None:
            self.body = []
        else:
            self.body = body

    def sync(self, project):
        """
        When syncing logs, return the transformed version of this entry.

        If no transformation is required, just return self.
        """
        return self

    def _sync_body(self, project):
        """
        Sync log body with git or any other activity data sources
        """
        if not self.body: return
        if self.body[-1].strip() != "+": return
        self.body.pop()
        from .git import collect_achievements
        collect_achievements(project, self)

    @classmethod
    def _read_body(cls, lines):
        # Read entry body
        body = []
        while True:
            line = lines.peek()
            if not line: break
            if not line[0].isspace(): break
            if Entry.is_start_line(line): break
            body.append(lines.next())
        return body


class Timebase(EntryBase):
    def __init__(self, line, dt):
        super().__init__()
        self.line = line
        self.dt = dt

    def print(self, file):
        print(self.line, file=file)

    @classmethod
    def parse(cls, logparser, lines, year, date):
        val = date or year
        log.debug("%s:%d: timebase: %s", lines.fname, lines.lineno, val)
        # Just parse the next line, storing it nowhere, but updating
        # the 'default' datetime context
        dt = logparser.parse_date(val)
        line = lines.next()
        if dt is None: return None
        return cls(line, dt)

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_timebase.match(line)


class Entry(EntryBase):
    re_tail = re.compile(r"(?P<head>:\s*\d+:\d+-\s*\d+:\d+).*")

    def __init__(self, begin, until, head, body, fullday):
        super().__init__(body)
        # Datetime of beginning of log entry timespan
        self.begin = begin
        # Datetime of end of log entry timespan, None if open
        self.until = until
        # Text line of the head part of the log entry
        self.head = head
        # If true, the entry spans the whole day
        self.fullday = fullday

    @property
    def is_open(self):
        """
        Check if this log entry is still been edited
        """
        if self.fullday:
            return self.begin.date() == datetime.date.today()
        else:
            return self.until is None

    def sync(self, project):
        self._sync_body(project)
        return self

    @property
    def duration(self):
        """
        Return the duration in minutes
        """
        if self.fullday: return 24 * 60

        if not self.until:
            until = datetime.datetime.now()
        else:
            until = self.until

        td = (until - self.begin)
        return (td.days * 86400 + td.seconds) / 60

    @property
    def formatted_duration(self):
        return format_duration(self.duration)

    def print(self, file, project=None):
        if self.fullday:
            print(self.head, file=file)
        else:
            # If there is a tail after the duration, remove it
            head = [re.sub(self.re_tail, r"\g<head>", self.head, count=1)]
            if self.until:
                head.append(format_duration(self.duration))
            if project is not None:
                head.append("[%s]" % project)
            print(" ".join(head), file=file)

        for line in self.body:
            print(line, file=file)

    @classmethod
    def parse(cls, logparser, lines, date=None, start=None, end=None):
        # Read entry head
        entry_lineno = lines.lineno
        entry_head = lines.next()

        # Read entry body
        entry_body = cls._read_body(lines)

        # Parse entry head
        log.debug("%s:%d: log header: %s %s-%s", lines.fname, entry_lineno, date, start, end)
        entry_date = logparser.parse_date(date)
        if entry_date is None:
            log.warning("%s:%d: cannot parse log header date: '%s' (lang=%s)", lines.fname, entry_lineno, date, logparser.lang)
            entry_date = logparser.default
        entry_date = entry_date.date()

        if start:
            entry_begin = datetime.datetime.combine(entry_date, parsetime(start))
            if end:
                entry_until = datetime.datetime.combine(entry_date, parsetime(end))
                if entry_until < entry_begin:
                    # Deal with intervals across midnight
                    entry_until += datetime.timedelta(days=1)
            else:
                entry_until = None
            entry_fullday = False
        else:
            entry_begin = datetime.datetime.combine(entry_date, datetime.time(0))
            entry_until = entry_begin + datetime.timedelta(days=1)
            entry_fullday = True

        return cls(entry_begin, entry_until, entry_head, entry_body, entry_fullday)

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_entry.match(line)


class Command(EntryBase):
    def __init__(self, head, body, start=None):
        super().__init__(body)
        self.head = head
        self.start = start

    def sync(self, project):
        if self.start is None:
            begin = datetime.datetime.combine(datetime.date.today(), datetime.time(0))
            until = begin + datetime.timedelta(days=1)
            head = begin.strftime("%d %B:")
            res = Entry(begin, until, head, self.body, True)
            if self.head == "++":
                self.body.append(" +")
        else:
            begin = datetime.datetime.combine(datetime.date.today(), self.start)
            head = begin.strftime("%d %B: %H:%M-")
            res = Entry(begin, None, head, self.body, False)
            if self.head.endswith("+"):
                self.body.append(" +")

        res._sync_body(project)
        return res

    def print(self, file):
        print(self.head, file=file)
        for line in self.body:
            print(line, file=file)

    @classmethod
    def parse(cls, logparser, lines, start=None):
        # Read entry head
        lineno = lines.lineno
        head = lines.next().rstrip()

        # Read entry body
        body = cls._read_body(lines)

        # Request for creation of a new log entry
        if start is not None:
            start = parsetime(start)

        return cls(head, body, start)

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_new_time.match(line) or cls.re_new_day.match(line)


# TODO: turn into something like MonotonousDateParser and move parse method to
#       Log.
class LogParser(object):
    def __init__(self, lang=None):
        self.lang = lang
        # Defaults for missing parsedate values
        self.default = datetime.datetime(datetime.date.today().year, 1, 1)
        # Last datetime parsed
        self.last_dt = None
        self.parserinfo = get_parserinfo(lang)

    def parse_date(self, s, set_default=True):
        try:
            d = dateutil.parser.parse(s, default=self.default, parserinfo=self.parserinfo)
            if set_default:
                self.default = d.replace(hour=0, minute=0, second=0, microsecond=0)
            self.last_dt = d
            return d
        except (TypeError, ValueError):
            return None

    def parse(self, lines):
        components = [Timebase, Entry, Command]

        while True:
            line = lines.peek()
            if not line: break

            for c in components:
                mo = c.is_start_line(line)
                if mo:
                    el = c.parse(self, lines, **mo.groupdict())
                    if el is not None: yield el
                    break
            else:
                log.warn("%s:%d: log parse stops at unrecognised line %r", lines.fname, lines.lineno, line)
                break


class Log(list):
    def __init__(self, project, *args, **kw):
        super().__init__(*args, **kw)
        self.project = project
        # Line number in the project file where the log starts
        self._lineno = None

    def sync(self):
        """
        Sync log contents with git or any other activity data sources
        """
        new_entries = []
        for e in self:
            new_entries.append(e.sync(self.project))
        self[::] = new_entries

    def parse(self, lines, **kw):
        self._lineno = lines.lineno
        lp = LogParser(**kw)
        for el in lp.parse(lines):
            self.append(el)

    def print(self, file):
        """
        Write the log as a project log section to the given output file.

        Returns True if the log section was printed, False if there was
        nothing to print.
        """
        if not self:
            print(datetime.date.today().year, file=file)
        else:
            for entry in self:
                entry.print(file)
        return True

    def get_open_entry(self):
        """
        Return the last open entry if one is present, else None
        """
        for entry in self[::-1]:
            if not isinstance(entry, Entry): continue
            if not entry.is_open: return None
            return entry
        return None

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return Timebase.is_start_line(line) or Entry.is_start_line(line)
