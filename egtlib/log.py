from __future__ import annotations

import datetime
import re
import sys
from collections import Counter
from typing import Generator, List, Optional, TextIO, Type

import dateutil.parser

from . import project, utils
from .lang import get_parserinfo
from .parse import Lines
from .utils import format_duration


class LogParser:
    ENTRY_TYPES: List[Type["EntryBase"]] = []

    def __init__(self, lines: Lines, lang: Optional[str] = None):
        self.lines = lines
        self.lang = lang
        self.parserinfo = get_parserinfo(lang)
        # Defaults for missing parsedate values
        self.default = datetime.datetime(utils.today().year, 1, 1)
        # Log of parse errors
        self.errors: List[str] = []

    @classmethod
    def register_entry_type(cls, c: Type["EntryBase"]):
        cls.ENTRY_TYPES.append(c)
        return c

    def log_parse_error(self, lineno, msg):
        self.errors.append("line {}: {}".format(lineno + 1, msg))

    def parse_date(self, s: str):
        try:
            d = dateutil.parser.parse(s, default=self.default, parserinfo=self.parserinfo)
        except (TypeError, ValueError):
            return None
        self.default = d.replace(hour=0, minute=0, second=0, microsecond=0)
        return d

    def parse_entries(self) -> Generator["EntryBase", None, None]:
        while True:
            line = self.lines.peek()
            if not line:
                break

            for c in self.ENTRY_TYPES:
                mo = c.is_start_line(line)
                if mo:
                    el = c.parse(self, **mo.groupdict())
                    if el is not None:
                        yield el
                    break
            else:
                self.log_parse_error(self.lines.lineno, "log parse stops at unrecognised line " + repr(line))
                break


def parsetime(s: str) -> datetime.time:
    """
    Parse a time in the form hh:mm, and return the corresponding datetime.time
    """
    h, m = s.split(":")
    return datetime.time(int(h), int(m), 0)


class EntryBase:
    """
    Base class for log entries
    """

    def __init__(self, body: List[str] = None):
        # List of lines with the body of the log entry
        self.body: List[str]
        if body is None:
            self.body = []
        else:
            self.body = body

    def sync(self, project: "project.Project", today: datetime.date):
        """
        When syncing logs, return the transformed version of this entry.

        If no transformation is required, just return self.
        """
        return self

    def reference_time(self) -> Optional[datetime.datetime]:
        """
        Return the reference time for this log entry
        """
        raise NotImplementedError("reference_time called on EntryBase")

    def print_lead_timeref(self, file):
        """
        Assuming this is the first entry of the log being printed, print a time
        reference before the entry if it is needed to be able to reparse the
        entry correctly
        """
        raise NotImplementedError("print_lead_timeref called on EntryBase")

    @classmethod
    def _read_body(cls, lines: Lines) -> List[str]:
        # Read entry body
        body = []
        while True:
            line = lines.peek()
            if not line:
                break
            if not line[0].isspace():
                break
            if Entry.is_start_line(line):
                break
            body.append(lines.next())
        return body

    def print(self, file=sys.stdout) -> None:
        raise RuntimeError("print called on EntryBase instead of the real class")

    @classmethod
    def parse(cls, logparser: "LogParser", **kw):
        raise RuntimeError("parse called on EntryBase instead of the real class")

    @classmethod
    def is_start_line(cls, line: str):
        return False


@LogParser.register_entry_type
class Timebase(EntryBase):
    """
    Log entry providing a time reference for the next log entries
    """

    re_timebase = re.compile(r"^(?:(?P<year>\d{4})|-+\s*(?P<date>.+?))\s*$")

    def __init__(self, line: str, dt: datetime.datetime):
        super().__init__()
        self.line = line
        self.dt = dt

    def reference_time(self) -> Optional[datetime.datetime]:
        return self.dt

    def print(self, file=sys.stdout):
        print(self.line, file=file)

    def print_lead_timeref(self, file):
        # Nothing to do, since a timebase is a full time reference
        pass

    @classmethod
    def parse(cls, logparser: "LogParser", **kw):
        val: str = kw["date"] or kw["year"]
        # Just parse the next line, storing it nowhere, but updating
        # the 'default' datetime context
        dt = logparser.parse_date(val)
        line = logparser.lines.next()
        if dt is None:
            return None
        return cls(line, dt)

    @classmethod
    def is_start_line(cls, line: str):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_timebase.match(line)


@LogParser.register_entry_type
class Entry(EntryBase):
    """
    Free text log entry with a time header
    """

    re_entry = re.compile(
        r"^"
        r"(?P<date>(?:\S| \d)[^:]*):\s*"  # Date header
        r"(?:(?P<trange>(?P<start>\d+:\d+)\s*-\s*(?P<end>\d+:\d+)?)?)\s*"  # Optional time interval
        r"(?P<notes>(?:(?:\+\S+|\[[^]]+\]|\d+[a-z]+)\s*)*)"  # Tags and project name
        r"$"
    )
    re_projname = re.compile(r"\s*\[[^]]+\]\s*$")
    re_tag = re.compile(r"\s*\+\S+\s*$")
    re_hours = re.compile(r"^")

    def __init__(
        self,
        begin: datetime.datetime,
        until: Optional[datetime.datetime],
        head: str,
        body: List[str],
        fullday: bool,
        tags: List[str] = [],
    ):
        super().__init__(body)
        # Datetime of beginning of log entry timespan
        self.begin = begin
        # Datetime of end of log entry timespan, None if open
        self.until = until
        # Text line of the head part of the log entry
        self.head = head
        # If true, the entry spans the whole day
        self.fullday = fullday
        # Log entry tags
        self.tags = tags

    def reference_time(self) -> Optional[datetime.datetime]:
        return self.begin

    @property
    def is_open(self):
        """
        Check if this log entry is still been edited
        """
        if self.fullday:
            return self.begin.date() == utils.today()
        else:
            return self.until is None

    def _sync_body(self, project: "project.Project"):
        """
        Sync log body with git or any other activity data sources
        """
        if not self.body:
            return
        if self.body[-1].strip() != "+":
            return
        self.body.pop()
        from .git import collect_achievements

        collect_achievements(project, self)

    def sync(self, project: "project.Project", today: datetime.date):
        self._sync_body(project)
        return self

    @property
    def duration(self):
        """
        Return the duration in minutes
        """
        if self.fullday:
            return 24 * 60

        if not self.until:
            until = datetime.datetime.now()
        else:
            until = self.until

        td = until - self.begin
        return (td.days * 86400 + td.seconds) / 60

    @property
    def formatted_duration(self):
        return format_duration(self.duration)

    def print_lead_timeref(self, file):
        print(self.begin.year, file=file)

    def print(self, file=sys.stdout, project: Optional["project.Project"] = None):
        mo = self.re_entry.match(self.head)
        if not mo:
            raise RuntimeError("Header line was parsed right during parsing, and not during printing")
        line = [mo.group("date") + ":"]
        if not self.fullday:
            line.append(mo.group("trange"))
            if self.until:
                line.append(format_duration(self.duration))

        line += ["+" + tag for tag in self.tags]

        if project is not None:
            line.append("[%s]" % project.name)

        print(" ".join(line), file=file)

        for bline in self.body:
            print(bline, file=file)

    @classmethod
    def parse(cls, logparser: "LogParser", **kw):
        entry_lineno = logparser.lines.lineno
        # Read entry head line
        head = logparser.lines.next()
        # Read entry body
        body = cls._read_body(logparser.lines)

        # Parse entry head
        date = logparser.parse_date(kw["date"])
        if date is None:
            logparser.log_parse_error(
                entry_lineno, "cannot parse log header date: {} (lang={})".format(repr(kw["date"]), logparser.lang)
            )
            date = logparser.default

        # Parse start-end times
        start = kw.get("start")
        end = kw.get("end")
        begin: datetime.datetime
        until: Optional[datetime.datetime]
        if start:
            begin = datetime.datetime.combine(date, parsetime(start))
            if end:
                until = datetime.datetime.combine(date, parsetime(end))
                if until < begin:
                    # Deal with intervals across midnight
                    until += datetime.timedelta(days=1)
            else:
                until = None
            fullday = False
        else:
            begin = datetime.datetime.combine(date, datetime.time(0))
            until = begin + datetime.timedelta(days=1)
            fullday = True

        # Parse tags
        tags: List[str] = []
        notes = kw.get("notes")
        if notes:
            for note in notes.split():
                if note[0] == "+":
                    tags.append(note[1:])
                elif note[0] == "[":
                    # Ignore project name
                    pass
                elif note[0].isdigit():
                    # Ignore hour count
                    pass
                else:
                    logparser.log_parse_error(entry_lineno, "unrecognised annotation {}".format(repr(note)))

        return cls(begin, until, head, body, fullday, tags)

    @classmethod
    def is_start_line(cls, line: str):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_entry.match(line)


@LogParser.register_entry_type
class Command(EntryBase):
    """
    Log entry with a user query, to be expanded with the query result
    """

    re_new_time = re.compile(r"^(?P<start>\d{1,2}:\d{2})-?\s*\+?\s*$")
    re_new_day = re.compile(r"^\+\+?\s*$")

    def __init__(self, head: str, body: List[str], start: Optional[datetime.time] = None):
        super().__init__(body)
        self.head = head
        self.start = start

    def reference_time(self) -> Optional[datetime.datetime]:
        return None

    def sync(self, project: "project.Project", today: datetime.date):
        date_format = project.config.get("config", "date-format") + ":"
        datetime_format = date_format + " " + project.config.get("config", "time-format") + "-"
        if self.start is None:
            begin = datetime.datetime.combine(today, datetime.time(0))
            until = begin + datetime.timedelta(days=1)
            head = begin.strftime(date_format)
            res = Entry(begin, until, head, self.body, True)
            if self.head == "++":
                self.body.append(" +")
        else:
            begin = datetime.datetime.combine(today, self.start)
            head = begin.strftime(datetime_format)
            res = Entry(begin, None, head, self.body, False)
            if self.head.endswith("+"):
                self.body.append(" +")

        res._sync_body(project)
        return res

    def print_lead_timeref(self, file):
        raise RuntimeError(
            "Cannot output a log with a Command as the very first element, without a previous time reference"
        )

    def print(self, file=sys.stdout):
        print(self.head, file=file)
        for line in self.body:
            print(line, file=file)

    @classmethod
    def parse(cls, logparser: "LogParser", **kw):
        # Read entry head
        head = logparser.lines.next().rstrip()

        # Read entry body
        body = cls._read_body(logparser.lines)

        # Request for creation of a new log entry
        start = kw.get("start")
        if start is not None:
            start = parsetime(start)

        return cls(head, body, start)

    @classmethod
    def is_start_line(cls, line: str):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_new_time.match(line) or cls.re_new_day.match(line)


class LogPrinter:
    def __init__(self, file: TextIO, today: Optional[datetime.date] = None, archived: bool = False):
        self.today: datetime.date = today if today is not None else utils.today()
        self.file = file
        self.has_time_ref = False
        self.last_reference_time: Optional[datetime.datetime] = None
        self.archived = archived

    def print(self, entry: EntryBase):
        if not self.has_time_ref:
            entry.print_lead_timeref(self.file)
            self.has_time_ref = True
        entry.print(self.file)
        reftime = entry.reference_time()
        if reftime is not None:
            self.last_reference_time = reftime

    def done(self):
        if self.archived:
            return
        this_year = self.today.year
        if self.last_reference_time is None or self.last_reference_time.year != this_year:
            print(this_year, file=self.file)


class Log:
    """
    Time-based log section of a .egt file
    """

    def __init__(self, project: "project.Project"):
        self.project = project
        # Line number in the project file where the log starts
        self._lineno: Optional[int] = None
        # Array of Entry
        self._entries: List[EntryBase] = []

    @property
    def entries(self):
        """
        Generate all the Entry entries of this log
        """
        for e in self._entries:
            if not isinstance(e, Entry):
                continue
            yield e

    @property
    def first_entry(self):
        """
        Return the first Entry of the log
        """
        for e in self._entries:
            if not isinstance(e, Entry):
                continue
            return e
        return None

    @property
    def last_entry(self):
        """
        Return the last Entry of the log
        """
        for e in self._entries[::-1]:
            if not isinstance(e, Entry):
                continue
            return e
        return None

    def detach_entries(self, since, until):
        """
        Remove from the log the entries that go between the first Entry within
        the given interval and the last Entry within the given interval
        """
        first = None
        last = None
        for idx, e in enumerate(self._entries):
            if not isinstance(e, Entry):
                continue
            if e.begin.date() >= since and e.begin.date() < until:
                if first is None:
                    first = idx
                    last = idx
                else:
                    last = idx

        if first is None:
            return []

        # If we removed Entry entries making two Timebase entries consecutive,
        # remove the first of the two
        res = self._entries[first:last + 1]
        del self._entries[first:last + 1]
        if (
            first > 0
            and first < len(self._entries)
            and isinstance(self._entries[first - 1], Timebase)
            and isinstance(self._entries[first], Timebase)
        ):
            self._entries.pop(first - 1)
        return res

    def durations(self) -> Counter:
        """
        Compute durations, total and by tag
        """
        res: Counter = Counter()
        for e in self.entries:
            duration = e.duration
            res[""] += duration
            for tag in e.tags:
                res[tag] += duration
        return res

    def sync(self, today=None):
        """
        Sync log contents with git or any other activity data sources
        """
        if today is None:
            today = utils.today()
        self.project.set_locale()
        new_entries = []
        for e in self._entries:
            new_entries.append(e.sync(self.project, today=today))
        self._entries = new_entries

    def parse(self, lines: Lines, lang: str = None):
        self._lineno = lines.lineno

        log_parser = LogParser(lines, lang)
        for el in log_parser.parse_entries():
            self._entries.append(el)

        if log_parser.errors:
            self.project.meta.set("parse-errors", "\n".join(log_parser.errors))
        else:
            self.project.meta.unset("parse-errors")

    def print(self, file=sys.stdout, today=None):
        """
        Write the log as a project log section to the given output file.

        Returns True if the log section was printed, False if there was
        nothing to print.
        """
        # self.project.set_locale()
        printer = LogPrinter(file, today=today, archived=self.project.archived)
        for entry in self._entries:
            printer.print(entry)
        printer.done()
        return True

    @classmethod
    def is_start_line(cls, line: str):
        """
        Check if the next line looks like the start of a log block
        """
        return Timebase.is_start_line(line) or Entry.is_start_line(line)
