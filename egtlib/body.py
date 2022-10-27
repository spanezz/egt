from __future__ import annotations

import re
from typing import List, Optional, TextIO

from . import project
from .parse import Lines


class BodyEntry:
    """
    Base class for elements that compose a project body
    """
    def __init__(self, indent: str):
        # Indentation at the beginning of the lines
        self.indent = indent

    def is_empty(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} has been called on raw BodyEntry object")

    def print(self, file: Optional[TextIO] = None) -> None:
        raise NotImplementedError(f"{self.__class__.__name__} has been called on raw BodyEntry object")


class EmptyLine(BodyEntry):
    """
    One empty line
    """
    def is_empty(self) -> bool:
        return True

    def print(self, file: Optional[TextIO] = None) -> None:
        print(self.indent, file=file)

    def __repr__(self):
        return "EmptyLine()"


class Line(BodyEntry):
    """
    One line of text
    """

    def __init__(self, indent: str, line: str):
        super().__init__(indent=indent)
        self.line = line

    def is_empty(self) -> bool:
        return False

    def print(self, file: Optional[TextIO] = None) -> None:
        print(self.indent + self.line, file=file)

    def __repr__(self):
        return f"Line({self.line!r})"


class Body:
    """
    The text body of a Project file, as anything that follows the metadata and
    the log
    """

    re_task = re.compile(r"^(?P<indent>\s*)t(?P<id>\d*)\s+(?P<text>.+)$")
    re_line = re.compile(r"^(?P<indent>\s*)(?P<line>.*)$")

    def __init__(self, project: "project.Project"):
        from .body_task import Tasks

        self.project = project
        self.tasks = Tasks(self)

        # Line number in the project file where the body starts
        self._lineno: Optional[int] = None

        # Text lines for the project body
        self.content: List[BodyEntry] = []

    def parse(self, lines: Lines) -> None:
        self._lineno = lines.lineno

        # Get everything until we reach the end of file
        for line in lines.rest():
            if (mo := self.re_task.match(line)):
                self.content.append(self.tasks.create_task(**mo.groupdict()))
            elif (mo := self.re_line.match(line)):
                if mo.group("line"):
                    self.content.append(Line(**mo.groupdict()))
                else:
                    self.content.append(EmptyLine(mo.group("indent")))

        self.tasks.post_parse_hook()

    def print(self, file: TextIO) -> bool:
        """
        Write the body as a project body section to the given output file.

        Returns True if the body section was printed, False if there was
        nothing to print.
        """
        # Print the rest of the known contents
        for el in self.content:
            el.print(file=file)
        return True
