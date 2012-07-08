
def annotate_with_indent_and_markers(lines):
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

class BodyParser(object):
    def __init__(self, lines):
        # Annotated lines generator
        self.lines = GeneratorLookahead(annotate_with_indent_and_markers(lines))

    def parse_body(self):
        self.parse_next_actions()
        self.parse_someday_maybe()

    def parse_next_actions(self):
        while True:
            i, m, l = self.lines.peek()

            # End of next actions, return the first line of someday/maybe
            if m == '*':
                return

            # Start of a context line
            elif i == 0 and l.rstrip().endswith(":"):
                contexts = frozenset(l.strip(" :\t").split())
                self.lines.pop()
                self.parse_next_action_list(contexts)

            # Contextless context lines
            elif m == '-':
                self.parse_next_action_list(frozenset())

            # Empty lines
            elif m == ' ':
                # TODO append it somewhere
                self.lines.pop()

            # Freeform text
            else:
                # TODO: append it somewhere
                self.lines.pop()

    def parse_next_action_list(self):
        last_indent = 0
        #for i, m, l, in self.lines:

    def parse_someday_maybe(self):
        someday_maybe = []
        while True:
            i, m, l = self.lines,pop()
            someday_maybe.append(l)


