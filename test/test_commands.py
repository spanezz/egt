# coding: utf8
import unittest
from .utils import ProjectTestMixin
from configparser import ConfigParser
import os
from egtlib.state import State
import egtlib

body_p = """Name: test

2016
15 march: 9:00-9:30
 - wrote unit tests

Write more unit tests
"""

body_p1 = """
"""

body_p2 = """
"""


class TestCommands(ProjectTestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.p = os.path.join(self.workdir.name, ".egt")
        with open(self.p, "wt") as fd: fd.write(body_p)
        self.p1 = os.path.join(self.workdir.name, "p1.egt")
        with open(self.p1, "wt") as fd: fd.write(body_p1)
        self.p2 = os.path.join(self.workdir.name, "p2.egt")
        with open(self.p2, "wt") as fd: fd.write(body_p2)

    def test_scan(self):
        State.rescan([self.workdir.name], statedir=self.workdir.name)
        state = State()
        state.load(self.workdir.name)
        self.assertIn("test", state.projects)
        self.assertIn("p1", state.projects)
        self.assertIn("p2", state.projects)
        self.assertEqual(len(state.projects), 3)

    def test_list(self):
        State.rescan([self.workdir.name], statedir=self.workdir.name)
        egt = egtlib.Egt(config=ConfigParser(), statedir=self.workdir.name)
        names = set(p.name for p in egt.projects)
        self.assertIn("test", names)
        self.assertIn("p1", names)
        self.assertIn("p2", names)
        self.assertEqual(len(names), 3)

    # TODO: test_summary
    # TODO: test_term
    # TODO: test_work
    # TODO: test_edit
    # TODO: test_grep
    # TODO: test_mrconfig
    # TODO: test_weekrpt
    # TODO: test_printlog
    # TODO: test_annotate
    # TODO: test_archive
    # TODO: test_serve
    # TODO: test_completion

    def test_backup(self):
        State.rescan([self.workdir.name], statedir=self.workdir.name)
        egt = egtlib.Egt(config=ConfigParser(), statedir=self.workdir.name)
        tarfname = os.path.join(self.workdir.name, "backup.tar")
        with open(tarfname, "wb") as fd:
            egt.backup(fd)

        # Test backup contents
        names = []
        import tarfile
        with tarfile.open(tarfname, "r") as tar:
            for f in tar:
                names.append(f.name)

        wd = os.path.relpath(self.workdir.name, "/")
        self.assertIn(os.path.join(wd, ".egt"), names)
        self.assertIn(os.path.join(wd, "p1.egt"), names)
        self.assertIn(os.path.join(wd, "p2.egt"), names)
        self.assertEqual(len(names), 3)
