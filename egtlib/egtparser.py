import re


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

    def __init__(self, lines, contexts=None):
        self.contexts = contexts if contexts is not None else frozenset()
        self.lines = lines

class SomedayMaybe(object):
    TAG = "someday-maybe"

    def __init__(self, lines):
        self.lines = lines


class BodyParser(object):
    def __init__(self, lines):
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
        while True:
            i, m, l = self.lines.peek()

            if m == '*':
                # End of next actions, return the first line of someday/maybe
                return
            elif i == 0 and l.rstrip().endswith(":"):
                # Start of a context line
                contexts = frozenset(re.split(r"\s*,\s*", l.strip(" :\t")))
                self.parse_next_action_list(contexts)
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

    def parse_next_action_list(self, contexts=None):
        na = NextActions([], contexts)
        self.parsed.append(na)

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

    def parse_someday_maybe(self):
        self.parsed.append(SomedayMaybe([]))
        while True:
            i, m, l = self.lines.pop()
            self.parsed[-1].lines.append(l)
