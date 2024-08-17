from __future__ import annotations

import datetime
import io
import unittest

from egtlib import Project
from egtlib.config import Config

from .utils import ProjectTestMixin


class TestAnnotate(ProjectTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.projectfile = self.workdir / ".egt"

    def annotate(self, text: str | list[str], today: datetime.date = datetime.date(2019, 2, 1)) -> str:
        with self.projectfile.open("w") as fd:
            if isinstance(text, str):
                fd.write(text)
            else:
                for line in text:
                    print(line, file=fd)

        proj = Project(self.projectfile, statedir=self.workdir, config=Config())
        proj.body.tasks.force_load_tw(config_filename=self.taskrc)
        proj.load()

        proj.annotate(today=today)
        with io.StringIO() as fd:
            proj.print(fd, today=today)
            return fd.getvalue()

    def test_empty(self) -> None:
        self.assertEqual(self.annotate(""), "2019\n\n")

    def test_randomtext(self) -> None:
        self.assertEqual(self.annotate("randomtext\n"), "2019\n\nrandomtext\n")
        self.assertEqual(self.annotate("\nrandomtext\n"), "2019\n\nrandomtext\n")
        self.assertEqual(self.annotate("\n\nrandomtext\n"), "2019\n\nrandomtext\n")

    def test_meta_only(self) -> None:
        self.assertEqual(self.annotate("Lang: it\n"), "Lang: it\n\n2019\n\n")

    def test_parse_error(self) -> None:
        res = self.annotate("Lang: it\n\n2019\n01 pippo:\n - error\n")
        self.assertEqual(
            res.splitlines(),
            [
                "Lang: it",
                "Parse-Errors: line 4: cannot parse log header date: '01 pippo' (lang=it)",
                "",
                "2019",
                "01 pippo:",
                " - error",
                "",
            ],
        )

    def test_parse_errors_fixed(self) -> None:
        res = self.annotate("Lang: it\nParse-Errors: foo\n\n2019\n01 marzo:\n - fixed\n")
        self.assertEqual(
            res.splitlines(),
            [
                "Lang: it",
                "",
                "2019",
                "01 marzo:",
                " - fixed",
                "",
            ],
        )

    def test_totals(self) -> None:
        self.maxDiff = None

        res = self.annotate(
            [
                "Lang: it",
                "Total:",
                "",
                "2019",
                "01 marzo: 10:00-12:00",
                " - fixed",
                "02 marzo: 10:00-11:00",
                " - fixed",
            ]
        )
        self.assertEqual(
            res.splitlines(),
            [
                "Lang: it",
                "Total: 3h",
                "",
                "2019",
                "01 marzo: 10:00-12:00 2h",
                " - fixed",
                "02 marzo: 10:00-11:00 1h",
                " - fixed",
                "",
            ],
        )

        res = self.annotate(
            [
                "Lang: it",
                "Total: 3h",
                "",
                "2019",
                "01 marzo: 10:00-12:00",
                " - fixed",
                "02 marzo: 10:00-11:00 +tag",
                " - fixed",
            ]
        )
        self.assertEqual(
            res.splitlines(),
            [
                "Lang: it",
                "Total:",
                " *: 3h",
                " tag: 1h",
                "",
                "2019",
                "01 marzo: 10:00-12:00 2h",
                " - fixed",
                "02 marzo: 10:00-11:00 1h +tag",
                " - fixed",
                "",
            ],
        )
