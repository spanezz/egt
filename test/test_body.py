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

    def test_empty(self):
        proj = self.project(
            body=[]
        )
        self.assertEqual(proj.body.content, [])

    def test_lines(self):
        proj = self.project(
            body=["first line", "", "second line", "* third line"]
        )
        self.assertEqual(proj.body.content, [
            body.Line(indent="", text="first line"),
            body.EmptyLine(indent=""),
            body.Line(indent="", text="second line"),
            body.BulletListLine(indent="", bullet="* ", text="third line"),
        ])

    def test_indent(self):
        proj = self.project(
            body=[
                "first line",
                "  ",
                "  second line",
                "  * third line"]
        )
        self.assertEqual(proj.body.content, [
            body.Line(indent="", text="first line"),
            # Right spaces are stripped by the parser
            body.EmptyLine(indent=""),
            body.Line(indent="  ", text="second line"),
            body.BulletListLine(indent="  ", bullet="* ", text="third line"),
        ])
