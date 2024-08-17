from __future__ import annotations

import unittest

from egtlib import body
from .utils import ProjectTestMixin


class TestBody(ProjectTestMixin, unittest.TestCase):
    DEFAULT_META = {
        "Name": "testprj",
        "Tags": "testtag1, testtag2",
    }

    DEFAULT_LOG = [
        "2016",
        "15 march: 9:30-",
        " - wrote more unit tests",
    ]

    def test_empty(self) -> None:
        proj = self.project(body=[])
        self.assertEqual(proj.body.content, [])

    def test_lines(self) -> None:
        proj = self.project(body=["first line", "", "second line", "* third line"])
        self.assertEqual(
            proj.body.content,
            [
                body.Line(indent="", text="first line"),
                body.EmptyLine(indent=""),
                body.Line(indent="", text="second line"),
                body.Line(indent="", bullet="* ", text="third line"),
            ],
        )

    def test_indent(self) -> None:
        proj = self.project(body=["first line", "  ", "  second line", "  * third line"])
        self.assertEqual(
            proj.body.content,
            [
                body.Line(indent="", text="first line"),
                # Right spaces are stripped by the parser
                body.EmptyLine(indent=""),
                body.Line(indent="  ", text="second line"),
                body.Line(indent="  ", bullet="* ", text="third line"),
            ],
        )

    def test_paragraph(self) -> None:
        proj = self.project(body=["first line", "  ", " * second line", "   third line"])
        self.assertEqual(
            proj.body.content,
            [
                body.Line(indent="", text="first line"),
                body.EmptyLine(),
                body.Line(indent=" ", bullet="* ", text="second line"),
                body.Line(indent="   ", text="third line"),
            ],
        )

    def test_date(self) -> None:
        proj = self.project(
            body=["2022-10-01: first line", "  ", " * 2022-10-15:  second line", "   2022-10-30: third line"]
        )
        self.assertEqual(
            proj.body.content,
            [
                body.Line(indent="", date="2022-10-01: ", text="first line"),
                body.EmptyLine(),
                body.Line(indent=" ", bullet="* ", date="2022-10-15:  ", text="second line"),
                body.Line(indent="   ", date="2022-10-30: ", text="third line"),
            ],
        )
