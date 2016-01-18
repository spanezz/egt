import re


class Regexps:
    """
    Repository of precompiled regexps
    """
    event_range = re.compile(r"\s*--\s*")
    meta_head = re.compile(r"^\w.*:")
    log_date = re.compile("^(?:(?P<year>\d{4})|-+\s*(?P<date>.+?))\s*$")
    log_head = re.compile(r"^(?P<date>(?:\S| \d).*?):\s+(?P<start>\d+:\d+)-\s*(?P<end>\d+:\d+)?")


class Lines:
    def __init__(self, pathname, fd=None):
        # File name being parsed
        self.fname = pathname
        # Current line being parsed
        self.lineno = 0
        # Read the file, split in trimmed lines
        if fd is None:
            with open(self.fname) as fd:
                self.lines = [x.rstrip() for x in fd]
        else:
            self.lines = [x.rstrip() for x in fd]

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

