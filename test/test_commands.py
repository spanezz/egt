# coding: utf8
import unittest
from unittest import mock
from io import StringIO
from .utils import ProjectTestMixin
import os
from egtlib.state import State
from egtlib.commands import Completion
import egtlib

body_p = """Name: test

2016
15 march: 9:00-9:30
 - wrote unit tests

Write more unit tests
"""

body_p1 = """Name: p1
tags: foo, bar
"""

body_p2 = """Name: p2
tags: blubb, foo
"""


class TestCommands(ProjectTestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.p = os.path.join(self.workdir.name, ".egt")
        with open(self.p, "wt") as fd:
            fd.write(body_p)
        self.p1 = os.path.join(self.workdir.name, "p1.egt")
        with open(self.p1, "wt") as fd:
            fd.write(body_p1)
        self.p2 = os.path.join(self.workdir.name, "p2.egt")
        with open(self.p2, "wt") as fd:
            fd.write(body_p2)

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
        egt = egtlib.Egt(config=None, statedir=self.workdir.name)
        names = set(p.name for p in egt.projects)
        self.assertIn("test", names)
        self.assertIn("p1", names)
        self.assertIn("p2", names)
        self.assertEqual(len(names), 3)

    def test_complete(self):
        subtests = [
            {"cmd": "projects", "res": ["p1", "p2", "test"]},
            {"cmd": "tags", "res": ["bar", "blubb", "foo"]},
        ]
        State.rescan([self.workdir.name], statedir=self.workdir.name)
        egt = egtlib.Egt(config=None, statedir=self.workdir.name)
        with mock.patch("egtlib.cli.Command.setup_logging"):
            for subtest in subtests:
                with self.subTest(config=subtest["cmd"]):
                    mock_arg = mock.Mock(subcommand=subtest["cmd"])
                    completion = Completion(mock_arg)
                    with mock.patch.object(completion, "make_egt", return_value=egt):
                        with mock.patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                            completion.main()
                    names = mock_stdout.getvalue().split("\n")[:-1]
                    self.assertEqual(names, subtest["res"])

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

    def test_backup(self):
        State.rescan([self.workdir.name], statedir=self.workdir.name)
        egt = egtlib.Egt(config=None, statedir=self.workdir.name)
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
