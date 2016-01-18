# coding: utf8
from __future__ import absolute_import
from .utils import format_duration
from .parse import Regexps
from .dateutil import get_parserinfo
import dateutil.parser
import datetime
import logging

log = logging.getLogger(__name__)

def parsetime(s):
    h, m = s.split(":")
    return datetime.time(int(h), int(m), 0)



class Entry(object):
    def __init__(self, begin, until, head, body):
        self.begin = begin
        self.until = until
        self.head = head
        self.body = body
        self.day_billing = None

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

    def output(self, project=None, file=None):
        head = [self.begin.strftime("%d %B: %H:%M-")]
        if self.until:
            head.append(self.until.strftime("%H:%M "))
            if self.day_billing is None:
                head.append(format_duration(self.duration))
            elif self.day_billing == 0.0:
                head.append("-")
            elif self.day_billing == 0.5:
                head.append("½d")
            else:
                head.append("{:.1}d".format(self.day_billing))
        if project is not None:
            head.append(" [%s]" % project)
        print("".join(head), file=file)
        print(self.body, file=file)


class EventParser(object):
    def __init__(self, lang=None):
        self.lang = lang
        # Defaults for missing parsedate values
        self.default = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.parserinfo = get_parserinfo(lang)
        # TODO: remember the last date to use as default for time-only things

    def parse(self, s, set_default=True):
        try:
            d = dateutil.parser.parse(s, default=self.default, parserinfo=self.parserinfo)
            if set_default:
                self.default = d.replace(hour=0, minute=0, second=0, microsecond=0)
            return d
        except (TypeError, ValueError):
            return None

    def _to_event(self, dt):
        if dt is None: return None
        return dict(
            start=dt,
            end=None,
            allDay=(dt.hour == 0 and dt.minute == 0 and dt.second == 0)
        )

    def parsedate(self, s):
        """
        Return the parsed date, or None if it wasn't recognised
        """
        if not s:
            return None
        mo = Regexps.event_range.search(s)
        if mo:
            # print "R"
            # Parse range
            since = s[:mo.start()]
            until = s[mo.end():]
            since = self.parse(since)
            until = self.parse(until, set_default=False)
            return dict(
                start=since,
                end=until,
                allDay=False,
            )
        elif s[0].isdigit():
            # print "D"
            return self._to_event(self.parse(s))
        elif s.startswith("d:"):
            # print "P"
            return self._to_event(self.parse(s[2:]))
        return None


class LogParser(object):
    def __init__(self, lang=None):
        self.ep = EventParser(lang=lang)
        self.ep.default = datetime.datetime(datetime.date.today().year, 1, 1)
        self.begin = None
        self.until = None
        self.loghead = None
        self.logbody = []

    def flush(self):
        res = Entry(self.begin, self.until, self.loghead, "\n".join(self.logbody))
        self.begin = None
        self.end = None
        self.loghead = None
        self.logbody = []
        return res

    def parse(self, lines):
        entries = []
        while True:
            line = lines.next()
            if not line: break

            # Look for a date context
            mo = Regexps.log_date.match(line)
            if mo:
                if self.begin is not None:
                    entries.append(self.flush())
                val = mo.group("date") or mo.group("year")
                log.debug("%s:%d: stand-alone date: %s", lines.fname, lines.lineno, val)
                # Just parse the next line, storing it nowhere, but updating
                # the 'default' datetime context
                self.ep.parse(val)
                continue

            # Look for a log head
            mo = Regexps.log_head.match(line)
            if mo:
                try:
                    if self.begin is not None:
                        entries.append(self.flush())
                    self.loghead = line
                    log.debug("%s:%d: log header: %s %s-%s", lines.fname, lines.lineno, mo.group("date"), mo.group("start"), mo.group("end"))
                    date = self.ep.parse(mo.group("date"))
                    if date is None:
                        log.warning("%s:%d: cannot parse log header date: '%s' (lang=%s)", lines.fname, lines.lineno, mo.group("date"), self.ep.lang)
                        date = self.ep.default
                    date = date.date()
                    self.begin = datetime.datetime.combine(date, parsetime(mo.group("start")))
                    if mo.group("end"):
                        self.until = datetime.datetime.combine(date, parsetime(mo.group("end")))
                        if self.until < self.begin:
                            # Deal with intervals across midnight
                            self.until += datetime.timedelta(days=1)
                    else:
                        self.until = None
                    continue
                except ValueError as e:
                    log.error("%s:%d: %s", lines.fname, lines.lineno, str(e))

            # Else append to the previous log body
            self.logbody.append(line)

        if self.begin is not None:
            entries.append(self.flush())

        return entries


class Log(object):
    @classmethod
    def parse(cls, lines, **kw):
        lp = LogParser(**kw)
        return lp.parse(lines)

    @classmethod
    def is_log_start(cls, line):
        """
        Check if the next line looks like the start of a log block
        """
        return Regexps.log_date.match(line) or Regexps.log_head.match(line)
