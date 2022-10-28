from __future__ import annotations

import datetime
import re
from typing import cast, List, Optional, TextIO

from . import project
from .parse import Lines


class BodyEntry:
    """
    Base class for elements that compose a project body
    """
    def __init__(self, *, indent: str):
        # Indentation at the beginning of the lines
        self.indent = indent

    def is_empty(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__}.is_empty() has been called on raw BodyEntry object")

    def get_date(self) -> Optional[datetime.date]:
        raise NotImplementedError(f"{self.__class__.__name__}.get_date() has been called on raw BodyEntry object")

    def get_content(self) -> str:
        raise NotImplementedError(f"{self.__class__.__name__}.get_content() has been called on raw BodyEntry object")

    def print(self, file: Optional[TextIO] = None) -> None:
        print(self.indent + self.get_content(), file=file)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        o = cast(BodyEntry, other)
        return self.indent == o.indent


class EmptyLine(BodyEntry):
    """
    One empty line
    """
    def is_empty(self) -> bool:
        return True

    def get_date(self) -> Optional[datetime.date]:
        return None

    def get_content(self) -> str:
        return ""

    def __repr__(self):
        return f"EmptyLine(indent={self.indent!r})"


class LineEntry(BodyEntry):
    """
    An entry with a line of text
    """
    re_date = re.compile(r"^(\d{4}-\d{2}-\d{2}:\s*)(.*)$")

    def __init__(self, *, indent: str, text: str):
        super().__init__(indent=indent)
        self.date_str: Optional[str]
        self.date: Optional[datetime.date]

        if (mo := self.re_date.match(text)):
            self.date_str = mo.group(1)
            self.date = datetime.datetime.strptime(self.date_str[:10], "%Y-%m-%d")
            self.text = mo.group(2)
        else:
            self.date_str = None
            self.date = None
            self.text = text

    def is_empty(self) -> bool:
        return False

    def get_date(self) -> Optional[datetime.date]:
        return self.date

    def get_content(self) -> str:
        if self.date_str:
            return self.date_str + self.text
        else:
            return self.text

    def __repr__(self):
        return (f"{self.__class__.__name__}("
                f"indent={self.indent!r}, date_str={self.date_str!r}, text={self.text!r})")

    def __eq__(self, other: object) -> bool:
        if not super().__eq__(other):
            return False
        o = cast(LineEntry, other)
        return self.date_str == o.date_str and self.text == o.text


class BulletListLine(LineEntry):
    """
    One line with a bullet point
    """
    def __init__(self, indent: str, bullet: str, text: str):
        super().__init__(indent=indent, text=text)
        self.bullet = bullet

    def print(self, file: Optional[TextIO] = None) -> None:
        print(self.indent + self.bullet + self.get_content(), file=file)

    def __eq__(self, other: object) -> bool:
        if not super().__eq__(other):
            return False
        o = cast(BulletListLine, other)
        return self.bullet == o.bullet

    def __repr__(self):
        return (f"{self.__class__.__name__}("
                f"indent={self.indent!r}, bullet={self.bullet!r},"
                f" date_str={self.date_str!r}, text={self.text!r})")


class Line(LineEntry):
    """
    One line of text
    """
    def print(self, file: Optional[TextIO] = None) -> None:
        print(self.indent + self.get_content(), file=file)


class Body:
    """
    The text body of a Project file, as anything that follows the metadata and
    the log
    """

    re_task = re.compile(r"^(?P<indent>\s*)t(?P<id>\d*)\s+(?P<text>.+)$")
    re_bullet_line = re.compile(r"^(?P<indent>\s*)(?P<bullet>[-*+]\s+)(?P<text>.*)$")
    re_line = re.compile(r"^(?P<indent>\s*)(?P<text>.*)$")

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
            elif (mo := self.re_bullet_line.match(line)):
                self.content.append(BulletListLine(**mo.groupdict()))
            elif (mo := self.re_line.match(line)):
                if mo.group("text"):
                    self.content.append(Line(**mo.groupdict()))
                else:
                    self.content.append(EmptyLine(indent=mo.group("indent")))

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
