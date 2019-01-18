import unittest
from .utils import ProjectTestMixin
from egtlib import Project
import io
import os
import datetime


class TestAnnotate(ProjectTestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.projectfile = os.path.join(self.workdir.name, ".egt")

    def annotate(self, text, today=datetime.date(2019, 2, 1)):
        with open(self.projectfile, "wt") as fd:
            fd.write(text)

        proj = Project(self.projectfile, statedir=self.workdir.name)
        proj.body.force_load_tw(config_filename=self.taskrc)
        proj.load()

        proj.body.sync_tasks()
        proj.log.sync(today=today)
        with io.StringIO() as fd:
            proj.print(fd, today=today)
            return fd.getvalue()

    def test_empty(self):
        self.assertEqual(self.annotate(""), "2019\n\n")

    def test_randomtext(self):
        self.assertEqual(self.annotate("randomtext\n"), "2019\n\nrandomtext\n")
        self.assertEqual(self.annotate("\nrandomtext\n"), "2019\n\nrandomtext\n")
        self.assertEqual(self.annotate("\n\nrandomtext\n"), "2019\n\nrandomtext\n")

    def test_meta_only(self):
        self.assertEqual(self.annotate("Lang: it\n"), "Lang: it\n\n2019\n\n")

    def test_parse_error(self):
        res = self.annotate("Lang: it\n\n01 pippo:\n - error\n")
        self.assertEqual(res.splitlines(), [
            "Lang: it",
            "Parse-Errors: line 3: cannot parse log header date: '01 pippo' (lang=it)",
            "",
            "2019",
            "01 pippo:",
            " - error",
            "",
        ])

    def test_parse_errors_fixed(self):
        res = self.annotate("Lang: it\nParse-Errors: foo\n\n01 marzo:\n - fixed\n")
        self.assertEqual(res.splitlines(), [
            "Lang: it",
            "",
            "2019",
            "01 marzo:",
            " - fixed",
            "",
        ])
