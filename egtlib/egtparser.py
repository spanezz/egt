# coding: utf8
from __future__ import absolute_import
import re
import datetime
import dateutil.parser
from .dateutil import get_parserinfo


def annotate_with_indent_and_markers(lines):
    """
    Annotate each line with indent level and bullet marker

    Markers are:
        None: ordinary line
         ' ': empty line
         '-': dash bullet
         '*': star bullet
    """
    last_indent = 0
    last_empty_lines = []
    for l in lines:
        if not l or l.isspace():
            # Empty line, get indent of previous line if followed by
            # continuation of same or higher indent level, else indent 0
            last_empty_lines.append(l)
        else:
            # Compute indent
            lev = 0
            mlev = 0
            marker = None
            for c in l:
                if c == ' ':
                    lev += 1
                elif c == '\t':
                    lev += 8
                elif marker is None and c in "*-":
                    marker = c
                    mlev = lev
                    lev += 1
                else:
                    break
            if last_empty_lines:
                if marker is None:
                    mlev = lev
                if mlev >= last_indent:
                    empty_lev = last_indent
                else:
                    empty_lev = 0
                for x in last_empty_lines:
                    yield empty_lev, ' ', x
                last_empty_lines = []
            last_indent = lev
            yield lev, marker, l
    for l in last_empty_lines:
        yield 0, ' ', l


class GeneratorLookahead(object):
    """
    Wrap a generator providing a 1-element lookahead
    """
    def __init__(self, gen):
        self.gen = gen
        self.has_lookahead = False
        self.lookahead = None

    def peek(self):
        if not self.has_lookahead:
            self.lookahead = self.gen.next()
            self.has_lookahead = True
        return self.lookahead

    def pop(self):
        if self.has_lookahead:
            self.has_lookahead = False
            return self.lookahead
        else:
            return self.gen.next()


class EventParser(object):
    def __init__(self, lang):
        # Defaults for missing parsedate values
        self.re_range = re.compile(r"\s*--\s*")
        self.default = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.parserinfo = get_parserinfo(lang)
        # TODO: remember the last date to use as default for time-only things

    def _parse(self, s, set_default=True):
        try:
            d = dateutil.parser.parse(s, default=self.default, parserinfo=self.parserinfo)
            if set_default:
                self.default = d.replace(hour=0, minute=0, second=0, microsecond=0)
            return d
        except ValueError, e:
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
        mo = self.re_range.search(s)
        if mo:
            #print "R"
            # Parse range
            since = s[:mo.start()]
            until = s[mo.end():]
            since = self._parse(since)
            until = self._parse(until, set_default=False)
            return dict(
                start=since,
                end=until,
                allDay=False,
            )
        elif s[0].isdigit():
            #print "D"
            return self._to_event(self._parse(s))
        elif s.startswith("d:"):
            #print "P"
            return self._to_event(self._parse(s[2:]))
        return None

class Spacer(object):
    TAG = "spacer"

    def __init__(self, lines):
        self.lines = lines

class FreeformText(object):
    TAG = "freeform"

    def __init__(self, lines):
        self.lines = lines

class NextActions(object):
    TAG = "next-actions"

    def __init__(self, lines, contexts=None, event=None):
        # TODO: identify datetimes and parse them into datetime objects
        self.contexts = frozenset(contexts) if contexts is not None else frozenset()
        self.lines = lines
        self.event = event

    def at(self, ev):
        """
        Return a copy of this next action list, with a given event
        """
        return NextActions(list(self.lines), self.contexts, ev)

class SomedayMaybe(object):
    TAG = "someday-maybe"

    def __init__(self, lines):
        self.lines = lines


class BodyParser(object):
    def __init__(self, lines, lang=None):
        self.lang = lang
        # Annotated lines generator
        self.lines = GeneratorLookahead(annotate_with_indent_and_markers(lines))
        self.parsed = []

    def add_to_spacer(self, line):
        if not self.parsed or self.parsed[-1].TAG != Spacer.TAG:
            self.parsed.append(Spacer([]))
        self.parsed[-1].lines.append(line)

    def add_to_freeform(self, line):
        if not self.parsed or self.parsed[-1].TAG != FreeformText.TAG:
            self.parsed.append(FreeformText([]))
        self.parsed[-1].lines.append(line)

    def parse_body(self):
        try:
            self.parse_next_actions()
            self.parse_someday_maybe()
        except StopIteration:
            pass
        return self.parsed

    def parse_next_actions(self):
        eparser = EventParser(self.lang)
        while True:
            i, m, l = self.lines.peek()

            if m == '*':
                # End of next actions, return the first line of someday/maybe
                return
            elif i == 0 and l.rstrip().endswith(":"):
                # Start of a context line
                contexts = []
                events = []
                for t in re.split(r"\s*,\s*", l.strip(" :\t")):
                    ev = eparser.parsedate(t)
                    if ev is not None:
                        events.append(ev)
                    else:
                        contexts.append(t)
                self.parse_next_action_list(contexts, events)
            elif m == '-':
                # Contextless context lines
                self.parse_next_action_list()
            elif m == ' ':
                # Empty lines
                self.add_to_spacer(l)
                self.lines.pop()
            else:
                # Freeform text
                self.add_to_freeform(l)
                self.lines.pop()

    def parse_next_action_list(self, contexts=None, events=[]):
        na = NextActions([], contexts)

        if contexts is not None:
            # Store the context line
            na.lines.append(self.lines.pop()[2])

        last_indent = None
        while True:
            i, m, l = self.lines.peek()
            if m == "*": break
            if last_indent is None:
                last_indent = i
            if i < last_indent:
                break
            na.lines.append(l)
            self.lines.pop()
            last_indent = i

        if not events:
            self.parsed.append(na)
        else:
            for e in events:
                self.parsed.append(na.at(e))

    def parse_someday_maybe(self):
        self.parsed.append(SomedayMaybe([]))
        while True:
            i, m, l = self.lines.pop()
            self.parsed[-1].lines.append(l)
