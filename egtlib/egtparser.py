# coding: utf8
from __future__ import absolute_import
import re
import datetime
from collections import OrderedDict
from . import log as egtlog
from .parse import Regexps
import logging
from collections import namedtuple

log = logging.getLogger(__name__)

Line = namedtuple("Line", ("num", "ind", "mark", "line"))


def annotate_with_indent_and_markers(lines, first_lineno=1):
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
    for lineno, l in enumerate(lines):
        if not l or l.isspace():
            # Empty line, get indent of previous line if followed by
            # continuation of same or higher indent level, else indent 0
            last_empty_lines.append((lineno, l))
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
                for i, x in last_empty_lines:
                    yield Line(first_lineno + i, empty_lev, ' ', x)
                last_empty_lines = []
            last_indent = lev
            yield Line(first_lineno + lineno, lev, marker, l)
    for i, l in last_empty_lines:
        yield Line(first_lineno + i, 0, ' ', l)


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
            self.lookahead = next(self.gen)
            self.has_lookahead = True
        return self.lookahead

    def pop(self):
        if self.has_lookahead:
            self.has_lookahead = False
            return self.lookahead
        else:
            return next(self.gen)


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

    def add_to_vobject(self, cal):
        if self.event is None: return
        vevent = cal.add("vevent")
        vevent.add("categories").value = list(self.contexts)
        vevent.add("dtstart").value = self.event["start"]
        if self.event["end"]:
            vevent.add("dtend").value = self.event["start"]
        if len(self.lines) > 1:
            vevent.add("summary").value = self.lines[1].strip(" -")
        vevent.add("description").value = "\n".join(self.lines[1:])


class SomedayMaybe(object):
    TAG = "someday-maybe"

    def __init__(self, lines):
        self.lines = lines


class BodyParser(object):
    def __init__(self, lines, lang=None, fname=None, first_lineno=1):
        self.lang = lang
        self.fname = fname
        self.first_lineno = first_lineno
        # Annotated lines generator
        self.lines = GeneratorLookahead(annotate_with_indent_and_markers(lines, first_lineno))
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
        eparser = egtlog.EventParser(lang=self.lang)
        while True:
            lineno, i, m, l = self.lines.peek()

            if m == '*':
                log.debug("%s:%d: next action terminator '%s'", self.fname, lineno, l)
                # End of next actions, return the first line of someday/maybe
                return
            elif i == 0 and l.endswith(":"):
                # log.debug("%s:%d: next action context '%s'", self.lines.fname, self.lines.lineno, l)
                log.debug("%s:%d: next action context '%s'", self.fname, lineno, l)
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
                log.debug("%s:%d: contextless next action list '%s'", self.fname, lineno, l)
                # Contextless context lines
                self.parse_next_action_list()
            elif m == ' ':
                log.debug("%s:%d: spacer '%s'", self.fname, lineno, l)
                # Empty lines
                self.add_to_spacer(l)
                self.lines.pop()
            else:
                log.debug("%s:%d: freeform text '%s'", self.fname, lineno, l)
                # Freeform text
                self.add_to_freeform(l)
                self.lines.pop()

    def parse_next_action_list(self, contexts=None, events=[]):
        na = NextActions([], contexts)

        if contexts is not None:
            # Store the context line
            na.lines.append(self.lines.pop()[3])

        last_indent = None
        while True:
            try:
                lineno, i, m, l = self.lines.peek()
            except StopIteration:
                break
            if m == "*": break
            if last_indent is None:
                last_indent = i
            if i < last_indent:
                break
            na.lines.append(l)
            self.lines.pop()
            last_indent = i

        if not events:
            log.debug("%s:%d: add eventless next action", self.fname, lineno)
            self.parsed.append(na)
        else:
            for e in events:
                log.debug("%s:%d: add eventful next action start=%s", self.fname, lineno, e["start"])
                self.parsed.append(na.at(e))

    def parse_someday_maybe(self):
        log.debug("%s:%d: parsing someday/maybe", self.fname, self.lines.peek().num)
        self.parsed.append(SomedayMaybe([]))
        while True:
            lineno, i, m, l = self.lines.pop()
            self.parsed[-1].lines.append(l)


class ProjectParser(object):
    def __init__(self):
        self.lines = None
        # Current line being parsed
        self.lineno = 0
        # Defaults
        self.meta = dict()

    def peek(self):
        """
        Return the next line to be parsed, without advancing the cursor.
        Return None if we are at the end.
        """
        if self.lineno < len(self.lines):
            return self.lines[self.lineno]
        else:
            return None

    def next(self):
        """
        Return the next line to be parsed, advancing the cursor.
        Return None if we are at the end.
        """
        if self.lineno < len(self.lines):
            res = self.lines[self.lineno]
            self.lineno += 1
            return res
        else:
            return None

    def discard(self):
        """
        Just advance the cursor to the next line
        """
        if self.lineno < len(self.lines):
            self.lineno += 1

    def skip_empty_lines(self):
        while True:
            l = self.peek()
            if l is None: break
            if l: break
            self.discard()

    def parse_meta(self):
        first = self.peek()

        self.firstline_meta = None
        self.meta = OrderedDict()

        # If it starts with a log, there is no metadata: stop
        if Regexps.log_date.match(first) or Regexps.log_head.match(first):
            return

        # If the first line doesn't look like a header, stop
        if not Regexps.meta_head.match(first):
            return

        log.debug("%s:%d: parsing metadata", self.fname, self.lineno)
        self.firstline_meta = self.lineno

        # Get everything until we reach an empty line
        meta = []
        while True:
            l = self.next()
            # Stop at an empty line or at EOF
            if not l: break
            meta.append(l)
        self.meta_lines = meta

        # Parse like an email headers
        import email
        self.meta = OrderedDict(((k.lower(), v) for k, v in email.message_from_string("\n".join(meta)).items()))

    def parse_log(self):
        if egtlog.Log.is_log_start(self.peek()):
            log.debug("%s:%d: parsing log", self.fname, self.lineno)
            self.firstline_log = self.lineno
            self.log = egtlog.Log.parse(self, lang=self.meta.get("lang", None))
        else:
            self.firstline_log = None
            self.log = []

    def parse_body(self):
        log.debug("%s:%d: parsing body", self.fname, self.lineno)
        bp = BodyParser(self.lines[self.lineno:], lang=self.meta.get("lang", None), fname=self.fname, first_lineno=self.lineno)
        bp.parse_body()
        self.body = bp.parsed

    def parse(self, fname=None, fd=None):
        self.fname = fname

        # Read the file, split in trimmed lines
        if fd is None:
            with open(fname) as fd:
                self.lines = [x.rstrip() for x in fd]
        else:
            self.lines = [x.rstrip() for x in fd]

        # Reset current line cursor
        self.lineno = 0

        # Parse metadata
        self.parse_meta()

        self.skip_empty_lines()

        # Parse log entries
        self.parse_log()

        self.skip_empty_lines()

        # Parse/store body
        self.parse_body()
