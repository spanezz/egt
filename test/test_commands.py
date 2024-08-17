from __future__ import annotations

import argparse
import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

import egtlib
from egtlib import commands
from egtlib.commands import Completion
from egtlib.config import Config
from egtlib.state import State

from .utils import ProjectTestMixin

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
        self.p = self.workdir / "p"
        self.p.mkdir()
        (self.p / ".egt").write_text(body_p)

        self.p1 = self.workdir / "p1"
        self.p1.mkdir()
        (self.p1 / ".egt").write_text(body_p1)

        self.p2 = self.workdir / "p2"
        self.p2.mkdir()
        (self.p2 / ".egt").write_text(body_p2)

    def build_command(self, command_cls: type[commands.EgtCommand] | str, *args: str, rescan: bool = True):
        """Instantiate the EgtCommand class for the given command."""
        if rescan:
            State.rescan([self.workdir], statedir=self.workdir, config=Config())
        if isinstance(command_cls, str):
            for cls in commands.COMMANDS:
                if cls.command_name() == command_cls:
                    command_cls = cls
                    break
            else:
                raise KeyError(f"command {command_cls} not found")

        parser = argparse.ArgumentParser(description="egt test command")
        parser.add_argument("--version", action="version", version="%(prog)s 0.0")
        parser.add_argument("--verbose", "-v", action="store_true", help="verbose output")
        parser.add_argument("--debug", action="store_true", help="debug output")
        subparsers = parser.add_subparsers(help="egt subcommands", required=True, dest="command")
        command_cls.add_subparser(subparsers)
        parsed_args = parser.parse_args([command_cls.command_name()] + list(args))
        with mock.patch("egtlib.config.Config.load"):
            try:
                return command_cls(parsed_args)
            except SystemExit as e:
                self.fail(f"Command argument parsing exited with code {e.code}")

    def run_command(
        self, command_cls: type[commands.EgtCommand], *args: str, rescan: bool = True
    ) -> tuple[int, str, str]:
        """Run a command returning stdout and stderr."""
        cmd = self.build_command(command_cls, *args, rescan=rescan)
        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        with (
            mock.patch("egtlib.state.State.get_state_dir", return_value=self.workdir),
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            try:
                cmd.main()
                exit_code = 0
            except SystemExit as e:
                exit_code = e.code
        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_scan(self):
        State.rescan([self.workdir], statedir=self.workdir, config=Config())
        state = State()
        state.load(self.workdir)
        self.assertIn("test", state.projects)
        self.assertIn("p1", state.projects)
        self.assertIn("p2", state.projects)
        self.assertEqual(len(state.projects), 3)

    def test_list(self):
        State.rescan([self.workdir], statedir=self.workdir, config=Config())
        egt = egtlib.Egt(config=Config(), statedir=self.workdir)
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
        State.rescan([self.workdir], statedir=self.workdir, config=Config())
        egt = egtlib.Egt(config=Config(), statedir=self.workdir)
        with mock.patch("egtlib.cli.Command.setup_logging"):
            for subtest in subtests:
                with self.subTest(config=subtest["cmd"]):
                    mock_arg = mock.Mock(subcommand=subtest["cmd"])
                    completion = Completion(mock_arg)
                    with mock.patch.object(completion, "make_egt", return_value=egt):
                        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                            completion.main()
                    names = mock_stdout.getvalue().split("\n")[:-1]
                    self.assertEqual(names, subtest["res"])

    # TODO: test_summary
    # TODO: test_term
    # TODO: test_work
    # TODO: test_edit
    # TODO: test_grep

    def test_mrconfig(self):
        (self.p1 / ".git").mkdir()
        (self.p2 / ".git").mkdir()
        self.maxDiff = None
        code, stdout, stderr = self.run_command("mrconfig")
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout.splitlines(),
            [
                f"[{self.p1}]",
                "",
                f"[{self.p2}]",
                "",
            ],
        )
        self.assertEqual(code, 0)

    # TODO: test_weekrpt
    # TODO: test_printlog
    # TODO: test_annotate
    # TODO: test_archive
    # TODO: test_serve

    def test_backup(self):
        State.rescan([self.workdir], statedir=self.workdir, config=Config())
        egt = egtlib.Egt(config=Config(), statedir=self.workdir)
        tarfname = self.workdir / "backup.tar"
        with open(tarfname, "wb") as fd:
            egt.backup(fd)

        # Test backup contents
        names = []
        import tarfile

        with tarfile.open(tarfname, "r") as tar:
            for f in tar:
                names.append(Path(f.name))

        wd = self.workdir.relative_to("/")
        self.assertIn(wd / ".egt", names)
        self.assertIn(wd / "p1.egt", names)
        self.assertIn(wd / "p2.egt", names)
        self.assertEqual(len(names), 3)
