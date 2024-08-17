from __future__ import annotations

from pathlib import Path
from typing import TextIO
from collections.abc import Generator


class Lines:
    """
    Access a text file line by line, with line numbers
    """

    def __init__(self, path: Path, fd: TextIO | None = None):
        # File name being parsed
        self.path = path
        # Current line being parsed
        self.lineno = 0
        # Read the file, split in trimmed lines
        self.lines: list[str]
        if fd is None:
            with self.path.open("r") as fd:
                self.lines = [x.rstrip() for x in fd]
        else:
            self.lines = [x.rstrip() for x in fd]

    def peek(self) -> str | None:
        """
        Return the next line to be parsed, without advancing the cursor.
        Return None if we are at the end.
        """
        if self.lineno < len(self.lines):
            return self.lines[self.lineno]
        else:
            return None

    def next(self) -> str:
        """
        Return the next line to be parsed, advancing the cursor.
        Raise RuntimeError if we are at the end.
        """
        if self.lineno >= len(self.lines):
            raise RuntimeError("Lines.next() called at the end of the input")
        res = self.lines[self.lineno]
        self.lineno += 1
        return res

    def rest(self) -> Generator[str, None, None]:
        """
        Generate all remaining lines
        """
        yield from self.lines[self.lineno :]

    def discard(self) -> None:
        """
        Just advance the cursor to the next line
        """
        if self.lineno < len(self.lines):
            self.lineno += 1

    def skip_empty_lines(self) -> None:
        while True:
            line = self.peek()
            if line is None:
                break
            if line:
                break
            self.discard()
