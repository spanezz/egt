import re


class Lines:
    def __init__(self, pathname, fd=None):
        # File name being parsed
        self.fname = pathname
        # Current line being parsed
        self.lineno = 0
        # Read the file, split in trimmed lines
        if fd is None:
            with open(self.fname, "rt") as fd:
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
            line = self.peek()
            if line is None: break
            if line: break
            self.discard()
