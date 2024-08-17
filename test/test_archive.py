from __future__ import annotations

import datetime
import io
import os
import unittest

from egtlib import Project
from egtlib.config import Config

from .utils import ProjectTestMixin


class TestArchive(ProjectTestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.projectfile = self.workdir / ".egt"
        self.reportfile = self.workdir / "report.egt"

    def archive(self, text, today=datetime.date(2019, 2, 1)):
        with self.projectfile.open("w") as fd:
            if isinstance(text, str):
                fd.write(text)
            else:
                for line in text:
                    print(line, file=fd)

        proj = Project(self.projectfile, statedir=self.workdir, config=Config())
        proj.load()
        proj.meta.set("Name", "test")
        proj.meta.set("Archive-Dir", self.workdir)
        with open(self.reportfile, "wt") as fd:
            return proj, proj.archive(cutoff=today.replace(day=1), report_fd=fd, combined=False)

    def to_text(self, proj, today=datetime.date(2019, 2, 1)):
        with io.StringIO() as fd:
            proj.print(fd, today=today)
            return fd.getvalue()

    def test_archive(self):
        proj, archives = self.archive(
            [
                "2019",
                "01 january: 10:00-12:00",
                " - broken",
                "01 february: 10:00-11:00",
                " - fixed",
            ]
        )

        self.assertEqual(len(archives), 1)
        arc = archives[0]
        self.assertEqual(arc.abspath, self.workdir / "201901-test.egt")

        self.assertEqual(
            self.to_text(arc).splitlines(),
            [
                "Name: test",
                f"Archive-Dir: {self.workdir}",
                "Archived: yes",
                "Total: 2h",
                "",
                "2019",
                "01 january: 10:00-12:00 2h",
                " - broken",
                "",
            ],
        )

        self.assertEqual(
            self.to_text(proj).splitlines(),
            [
                "Name: test",
                f"Archive-Dir: {self.workdir}",
                "",
                "2019",
                "01 february: 10:00-11:00 1h",
                " - fixed",
                "",
            ],
        )

        with open(self.reportfile, "rt") as fd:
            self.assertEqual(
                [x.rstrip() for x in fd],
                [
                    "Name: test",
                    f"Archive-Dir: {self.workdir}",
                    "Archived: yes",
                    "Total: 2h",
                    "",
                    "2019",
                    "01 january: 10:00-12:00 2h",
                    " - broken",
                    "",
                ],
            )

    def test_archive_multi(self):
        proj, archives = self.archive(
            [
                "2018",
                "15 december: 9:00-13:00",
                " - worked",
                "2019",
                "01 january: 10:00-12:00",
                " - broken",
                "01 february: 10:00-11:00",
                " - fixed",
            ]
        )

        self.assertEqual(len(archives), 2)

        arc = archives[0]
        self.assertEqual(arc.abspath, self.workdir / "201812-test.egt")
        self.assertEqual(
            self.to_text(arc).splitlines(),
            [
                "Name: test",
                f"Archive-Dir: {self.workdir}",
                "Archived: yes",
                "Total: 4h",
                "",
                "2018",
                "15 december: 9:00-13:00 4h",
                " - worked",
                "",
            ],
        )

        arc = archives[1]
        self.assertEqual(arc.abspath, self.workdir / "201901-test.egt")
        self.assertEqual(
            self.to_text(arc).splitlines(),
            [
                "Name: test",
                f"Archive-Dir: {self.workdir}",
                "Archived: yes",
                "Total: 2h",
                "",
                "2019",
                "01 january: 10:00-12:00 2h",
                " - broken",
                "",
            ],
        )

        self.assertEqual(
            self.to_text(proj).splitlines(),
            [
                "Name: test",
                f"Archive-Dir: {self.workdir}",
                "",
                "2019",
                "01 february: 10:00-11:00 1h",
                " - fixed",
                "",
            ],
        )

        with open(self.reportfile, "rt") as fd:
            self.assertEqual(
                [x.rstrip() for x in fd],
                [
                    "Name: test",
                    f"Archive-Dir: {self.workdir}",
                    "Archived: yes",
                    "Total: 4h",
                    "",
                    "2018",
                    "15 december: 9:00-13:00 4h",
                    " - worked",
                    "",
                    "Name: test",
                    f"Archive-Dir: {self.workdir}",
                    "Archived: yes",
                    "Total: 2h",
                    "",
                    "2019",
                    "01 january: 10:00-12:00 2h",
                    " - broken",
                    "",
                ],
            )

    def test_archive_tagged(self):
        proj, archives = self.archive(
            [
                "2019",
                "01 january: 10:00-12:00 +tag1 +tag2",
                " - broken",
                "02 january: 10:00-11:00 +tag1",
                " - fixed",
                "03 january: 10:00-13:00",
                " - really fixed",
            ]
        )

        self.assertEqual(len(archives), 1)
        arc = archives[0]
        self.assertEqual(arc.abspath, self.workdir / "201901-test.egt")

        self.assertEqual(
            self.to_text(arc).splitlines(),
            [
                "Name: test",
                f"Archive-Dir: {self.workdir}",
                "Archived: yes",
                "Total:",
                " *: 6h",
                " tag1: 3h",
                " tag2: 2h",
                "",
                "2019",
                "01 january: 10:00-12:00 2h +tag1 +tag2",
                " - broken",
                "02 january: 10:00-11:00 1h +tag1",
                " - fixed",
                "03 january: 10:00-13:00 3h",
                " - really fixed",
                "",
            ],
        )

        remainder = [
            "Name: test",
            f"Archive-Dir: {self.workdir}",
            "",
            "2019",
            str(datetime.date.today().year),
            "",
        ]
        self.assertEqual(self.to_text(proj, today=None).splitlines(), remainder)
        with proj.abspath.open("r") as fd:
            self.assertEqual([x.rstrip() for x in fd], remainder)

    def test_no_old_data(self):
        proj, archives = self.archive(
            [
                "2019",
                "01 february: 10:00-13:00",
                " - fixed",
            ]
        )

        self.assertEqual(len(archives), 0)

        remainder = [
            "Name: test",
            f"Archive-Dir: {self.workdir}",
            "",
            "2019",
            "01 february: 10:00-13:00 3h",
            " - fixed",
            str(datetime.date.today().year),
            "",
        ]
        self.assertEqual(self.to_text(proj, today=None).splitlines(), remainder)
        with proj.abspath.open("r") as fd:
            self.assertEqual([x.rstrip() for x in fd], remainder)

    def test_empty(self):
        proj, archives = self.archive(
            [
                "2019",
            ]
        )

        self.assertEqual(len(archives), 0)

        remainder = [
            "Name: test",
            f"Archive-Dir: {self.workdir}",
            "",
            "2019",
            str(datetime.date.today().year),
            "",
        ]
        self.assertEqual(self.to_text(proj, today=None).splitlines(), remainder)
        with proj.abspath.open("r") as fd:
            self.assertEqual([x.rstrip() for x in fd], remainder)
