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
            print(self.begin.strftime("%d %B:"), file=file)
        else:
            # FIXME: alternative possibility: check by regexp (\d+:\d+ \d+\w+$) if
            # head has duration, and if not just concat to it, so we preserve
            # original head
            head = [self.begin.strftime("%d %B: %H:%M-")]
            if self.until:
                head.append(self.until.strftime("%H:%M "))
                head.append(format_duration(self.duration))
            if project is not None:
                head.append(" [%s]" % project)
            print("".join(head), file=file)

        for line in self.body:
            print(line, file=file)

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_entry.match(line)


class LogParser(object):
    re_new_entry = re.compile(r"^(?P<time>\d{1,2}:\d{2})\s*$")

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

    def parse_entry(self, lines, date, start, end):
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
            if self.re_new_entry.match(line): break
            entry_body.append(lines.next())

        # Parse entry head
        try:
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
        except ValueError as e:
            log.error("%s:%d: %s", lines.fname, entry_lineno, str(e))
            return None

        return Entry(entry_begin, entry_until, entry_head, entry_body, entry_fullday)

    def parse_new_time(self, lines, time):
        lines.next()
        entry_begin = dateutil.parser.parse(time, default=datetime.datetime.now().replace(second=0, microsecond=0), parserinfo=self.parserinfo)
        return Entry(entry_begin, None, entry_begin.strftime("%d %B: %H:%M-"), [], False)

    def parse_new_day(self, lines):
        lines.next()
        entry_begin = datetime.datetime.combine(datetime.date.today(), datetime.time(0))
        entry_until = entry_begin + datetime.timedelta(days=1)
        return Entry(entry_begin, entry_until, entry_begin.strftime("%d %B:"), [], True)

    def parse(self, lines):
        while True:
            line = lines.peek().strip()
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

            mo = self.re_new_entry.match(line)
            if mo:
                el = self.parse_new_time(lines, **mo.groupdict())
                if el is not None: yield el
                continue

            if line == "+":
                el = self.parse_new_day(lines)
                if el is not None: yield el
                continue

            log.warn("%s:%d: log parse stops at unrecognised line %r", lines.fname, lines.lineno, line)
            break


class Log(list):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        # Line number in the project file where the log starts
        self._lineno = None

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

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return Timebase.is_start_line(line) or Entry.is_start_line(line)
