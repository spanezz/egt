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

    def __init__(self, *, indent: str = ""):
        # Indentation at the beginning of the lines
        self.indent = indent

    def is_empty(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__}.is_empty() has been called on raw BodyEntry object")

    def get_date(self) -> datetime.date | None:
        raise NotImplementedError(f"{self.__class__.__name__}.get_date() has been called on raw BodyEntry object")

    def get_content(self) -> str:
        raise NotImplementedError(f"{self.__class__.__name__}.get_content() has been called on raw BodyEntry object")

    def print(self, file: TextIO | None = None) -> None:
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

    def get_date(self) -> datetime.date | None:
        return None

    def get_content(self) -> str:
        return ""

    def __repr__(self):
        return f"EmptyLine(indent={self.indent!r})"


class Line(BodyEntry):
    """
    An entry with a line of text
    """

    def __init__(self, *, indent: str = "", bullet: str = "", date: str | None = None, text: str):
        super().__init__(indent=indent)
        self.bullet = bullet or ""
        self.text = text
        self.date: datetime.date | None
        self.date_suffix: str | None

        if date is None:
            self.date = None
            self.date_suffix = None
        else:
            self.date = datetime.datetime.strptime(date[:10], "%Y-%m-%d")
            self.date_suffix = date[10:]

    def is_empty(self) -> bool:
        return False

    def get_date(self) -> datetime.date | None:
        return self.date

    def get_content(self) -> str:
        return self.text

    def print(self, file: TextIO | None = None) -> None:
        if self.date:
            print(f"{self.indent}{self.bullet}{self.date:%Y-%m-%d}{self.date_suffix}{self.text}", file=file)
        else:
            print(self.indent + self.bullet + self.text, file=file)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"indent={self.indent!r}, bullet={self.bullet!r},"
            f" date={self.date:%Y-%M-%d}, date_suffix={self.date_suffix!r},"
            f" text={self.text!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not super().__eq__(other):
            return False
        o = cast(Line, other)
        return (
            self.bullet == o.bullet
            and self.date == o.date
            and self.date_suffix == o.date_suffix
            and self.text == o.text
        )


class Body:
    """
    The text body of a Project file, as anything that follows the metadata and
    the log
    """

    re_task = re.compile(r"^(?P<indent>\s*)t(?P<id>\d*)\s+(?P<text>.+)$")
    re_line = re.compile(r"^(?P<indent>\s*)(?P<bullet>[-*+]\s+)?(?P<date>\d{4}-\d{2}-\d{2}:\s*)?(?P<text>.*)$")

    def __init__(self, project: project.Project):
        from .body_task import Tasks

        self.project = project
        self.tasks = Tasks(self)

        # Line number in the project file where the body starts
        self._lineno: int | None = None

        # Text lines for the project body
        self.content: list[BodyEntry] = []

    def parse(self, lines: Lines) -> None:
        self._lineno = lines.lineno

        # Get everything until we reach the end of file
        for line in lines.rest():
            if mo := self.re_task.match(line):
                self.content.append(self.tasks.create_task(**mo.groupdict()))
            elif mo := self.re_line.match(line):
                if mo.group("text") or mo.group("bullet") or mo.group("date"):
                    self.content.append(Line(**mo.groupdict()))
                else:
                    self.content.append(EmptyLine())

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
