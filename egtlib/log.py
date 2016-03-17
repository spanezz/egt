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


class Timebase:
    re_timebase = re.compile("^(?:(?P<year>\d{4})|-+\s*(?P<date>.+?))\s*$")

    def __init__(self, line, dt):
        self.line = line
        self.dt = dt

    def print(self, file):
        print(self.line, file=file)

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_timebase.match(line)


class Entry(object):
    re_entry = re.compile(r"^(?P<date>(?:\S| \d)[^:]*):\s*(?:(?P<start>\d+:\d+)-\s*(?P<end>\d+:\d+)?|$)")
    re_tail = re.compile(r"(?P<head>:\s*\d+:\d+-\s*\d+:\d+).*")
    re_new_time = re.compile(r"^(?P<start>\d{1,2}:\d{2})\s*$")
    re_new_day = re.compile(r"^\+\s*$")

    def __init__(self, begin, until, head, body, fullday):
        # Datetime of beginning of log entry timespan
        self.begin = begin
        # Datetime of end of log entry timespan, None if open
        self.until = until
        # Text line of the head part of the log entry
        self.head = head
        # List of lines with the body of the log entry
        self.body = body
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
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_entry.match(line) or cls.re_new_time.match(line) or cls.re_new_day.match(line)


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

    def parse_timebase(self, lines, year, date):
        val = date or year
        log.debug("%s:%d: timebase: %s", lines.fname, lines.lineno, val)
        # Just parse the next line, storing it nowhere, but updating
        # the 'default' datetime context
        dt = self.parse_date(val)
        line = lines.next()
        if dt is None: return None
        return Timebase(line, dt)

    def parse_entry(self, lines, date=None, start=None, end=None):
        # Read entry head
        entry_lineno = lines.lineno
        entry_head = lines.next()

        # Read entry body
        entry_body = []
        while True:
            line = lines.peek()
            if not line: break
            if Timebase.is_start_line(line): break
            if Entry.is_start_line(line): break
            entry_body.append(lines.next())

        if date is None:
            # Request for creation of a new log entry
            if start is None:
                entry_begin = datetime.datetime.combine(datetime.date.today(), datetime.time(0))
                entry_until = entry_begin + datetime.timedelta(days=1)
                entry_head = entry_begin.strftime("%d %B:")
                entry_fullday = True
            else:
                entry_begin = datetime.datetime.combine(datetime.date.today(), parsetime(start))
                entry_until = None
                entry_head = entry_begin.strftime("%d %B: %H:%M-")
                entry_fullday = False
        else:
            # Parse entry head
            log.debug("%s:%d: log header: %s %s-%s", lines.fname, entry_lineno, date, start, end)
            entry_date = self.parse_date(date)
            if entry_date is None:
                log.warning("%s:%d: cannot parse log header date: '%s' (lang=%s)", lines.fname, entry_lineno, date, self.lang)
                entry_date = self.default
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

        return Entry(entry_begin, entry_until, entry_head, entry_body, entry_fullday)

    def parse(self, lines):
        while True:
            line = lines.peek()
            if not line: break

            # Look for a date context
            mo = Timebase.is_start_line(line)
            if mo:
                el = self.parse_timebase(lines, **mo.groupdict())
                if el is not None: yield el
                continue

            # Look for a log head
            mo = Entry.is_start_line(line)
            if mo:
                el = self.parse_entry(lines, **mo.groupdict())
                if el is not None: yield el
                continue

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
        open_entry = self.get_open_entry()
        if open_entry is None: return
        if not open_entry.body: return
        if open_entry.body[-1].strip() != "+": return
        open_entry.body.pop()
        from .git import collect_achievements
        collect_achievements(self.project, open_entry)

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
