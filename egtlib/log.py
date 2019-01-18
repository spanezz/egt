from typing import List, Optional, Type, TextIO
from .utils import format_duration
from . import utils
from .lang import get_parserinfo
from . import project
from .parse import Lines
import dateutil.parser
import datetime
import sys
import re
import logging

log = logging.getLogger(__name__)


def parsetime(s: str) -> datetime.time:
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

    def sync(self, project: "project.Project"):
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
    def parse(cls, logparser: "LogParser", lines: Lines, **kw):
        raise RuntimeError("parse called on EntryBase instead of the real class")

    @classmethod
    def is_start_line(cls, line: str):
        return False


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
    def parse(cls, logparser: "LogParser", lines: Lines, **kw):
        val: str = kw["date"] or kw["year"]
        log.debug("%s:%d: timebase: %s", lines.fname, lines.lineno, val)
        # Just parse the next line, storing it nowhere, but updating
        # the 'default' datetime context
        dt = logparser.parse_date(val)
        line = lines.next()
        if dt is None:
            return None
        return cls(line, dt)

    @classmethod
    def is_start_line(cls, line: str):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_timebase.match(line)


class Entry(EntryBase):
    """
    Free text log entry with a time header
    """
    re_entry = re.compile(r"^(?P<date>(?:\S| \d)[^:]*):\s*(?:(?P<start>\d+:\d+)-\s*(?P<end>\d+:\d+)?|$)")
    re_tail = re.compile(r"(?P<head>:\s*\d+:\d+-\s*\d+:\d+).*")

    def __init__(self, begin: datetime.datetime, until: Optional[datetime.datetime], head: str, body: List[str], fullday: bool):
        super().__init__(body)
        # Datetime of beginning of log entry timespan
        self.begin = begin
        # Datetime of end of log entry timespan, None if open
        self.until = until
        # Text line of the head part of the log entry
        self.head = head
        # If true, the entry spans the whole day
        self.fullday = fullday

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

    def sync(self, project: "project.Project"):
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

        td = (until - self.begin)
        return (td.days * 86400 + td.seconds) / 60

    @property
    def formatted_duration(self):
        return format_duration(self.duration)

    def print_lead_timeref(self, file):
        print(self.begin.year, file=file)

    def print(self, file=sys.stdout, project: "project.Project" = None):
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
    def parse(cls, logparser: "LogParser", lines: Lines, **kw):
        # Read entry head
        entry_lineno = lines.lineno
        entry_head = lines.next()

        # Read entry body
        entry_body = cls._read_body(lines)

        # Parse entry head
        log.debug("%s:%d: log header: %s %s-%s", lines.fname, entry_lineno, kw["date"], kw["start"], kw["end"])
        entry_date = logparser.parse_date(kw["date"])
        if entry_date is None:
            log.warning("%s:%d: cannot parse log header date: '%s' (lang=%s)", lines.fname, entry_lineno, kw["date"], logparser.lang)
            entry_date = logparser.default
        entry_date = entry_date.date()

        entry_until: Optional[datetime.datetime]

        start = kw.get("start")
        end = kw.get("end")
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
    def is_start_line(cls, line: str):
        """
        Check if the next line looks like the start of a log block
        """
        return cls.re_entry.match(line)


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

    def sync(self, project: "project.Project"):
        if self.start is None:
            begin = datetime.datetime.combine(utils.today(), datetime.time(0))
            until = begin + datetime.timedelta(days=1)
            head = begin.strftime("%d %B:")
            res = Entry(begin, until, head, self.body, True)
            if self.head == "++":
                self.body.append(" +")
        else:
            begin = datetime.datetime.combine(utils.today(), self.start)
            head = begin.strftime("%d %B: %H:%M-")
            res = Entry(begin, None, head, self.body, False)
            if self.head.endswith("+"):
                self.body.append(" +")

        res._sync_body(project)
        return res

    def print_lead_timeref(self, file):
        raise RuntimeError("Cannot output a log with a Command as the very first element, without a previous time reference")

    def print(self, file=sys.stdout):
        print(self.head, file=file)
        for line in self.body:
            print(line, file=file)

    @classmethod
    def parse(cls, logparser: "LogParser", lines: Lines, **kw):
        # Read entry head
        head = lines.next().rstrip()

        # Read entry body
        body = cls._read_body(lines)

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


# TODO: turn into something like MonotonousDateParser and move parse method to
#       Log.
class LogParser:
    def __init__(self, lang=None):
        self.lang = lang
        # Defaults for missing parsedate values
        self.default = datetime.datetime(utils.today().year, 1, 1)
        # Last datetime parsed
        self.last_dt = None
        self.parserinfo = get_parserinfo(lang)

    def parse_date(self, s: str, set_default=True):
        try:
            d = dateutil.parser.parse(s, default=self.default, parserinfo=self.parserinfo)
            if set_default:
                self.default = d.replace(hour=0, minute=0, second=0, microsecond=0)
            self.last_dt = d
            return d
        except (TypeError, ValueError):
            return None

    def parse(self, lines: Lines):
        components: List[Type[EntryBase]] = [Timebase, Entry, Command]

        while True:
            line = lines.peek()
            if not line:
                break

            for c in components:
                mo = c.is_start_line(line)
                if mo:
                    el = c.parse(self, lines, **mo.groupdict())
                    if el is not None:
                        yield el
                    break
            else:
                log.warn("%s:%d: log parse stops at unrecognised line %r", lines.fname, lines.lineno, line)
                break


class LogPrinter:
    def __init__(self, file: TextIO, today: Optional[datetime.date] = None):
        self.today: datetime.date = today if today is not None else utils.today()
        self.file = file
        self.has_time_ref = False
        self.last_reference_time: Optional[datetime.datetime] = None

    def print(self, entry: EntryBase):
        if not self.has_time_ref:
            entry.print_lead_timeref(self.file)
            self.has_time_ref = True
        entry.print(self.file)
        reftime = entry.reference_time()
        if reftime is not None:
            self.last_reference_time = reftime

    def done(self):
        this_year = self.today.year
        if self.last_reference_time is None or self.last_reference_time.year != this_year:
            print(this_year, file=self.file)


class Log:
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

    def sync(self):
        """
        Sync log contents with git or any other activity data sources
        """
        new_entries = []
        for e in self._entries:
            new_entries.append(e.sync(self.project))
        self._entries = new_entries

    def parse(self, lines: Lines, **kw):
        self._lineno = lines.lineno
        lp = LogParser(**kw)
        for el in lp.parse(lines):
            self._entries.append(el)

    def print(self, file=sys.stdout, today=None):
        """
        Write the log as a project log section to the given output file.

        Returns True if the log section was printed, False if there was
        nothing to print.
        """
        printer = LogPrinter(file, today=today)
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
