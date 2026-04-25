import argparse
import contextlib
import datetime as dt
import io
import sys
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
    def setUp(self) -> None:
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

        self.config = mock.create_autospec(Config)
        self.config.summary_columns = ["name", "tags", "logs", "hours", "last"]
        self.config.backup_output = self.workdir.as_posix()
        self.config.date_format = "%d %B"
        self.config.time_format = "%H:%M"
        self.config.sync_tw_annotations = True
        self.config.autotag_rules = []
        self.config.state_dir = self.workdir

    def build_command[C: commands.EgtCommand](
        self,
        command_cls_or_name: type[C] | str,
        *args: str,
        rescan: bool = True,
    ) -> C:
        """Instantiate the EgtCommand class for the given command."""
        if rescan:
            State.rescan([self.workdir], config=self.config)

        command_cls: type[C]
        if isinstance(command_cls_or_name, str):
            for cls in commands.COMMANDS:
                if cls.command_name() == command_cls_or_name:
                    command_cls = cls  # type: ignore[assignment]
                    break
            else:
                raise KeyError(f"command {command_cls} not found")
        else:
            command_cls = command_cls_or_name

        parser = argparse.ArgumentParser(description="egt test command")
        parser.add_argument(
            "--version", action="version", version="%(prog)s 0.0"
        )
        parser.add_argument(
            "--verbose", "-v", action="store_true", help="verbose output"
        )
        parser.add_argument("--debug", action="store_true", help="debug output")
        subparsers = parser.add_subparsers(
            help="egt subcommands", required=True, dest="command"
        )
        command_cls.add_subparser(subparsers)
        parsed_args = parser.parse_args(
            [command_cls.command_name()] + list(args)
        )
        with mock.patch("egtlib.commands.Config", return_value=self.config):
            try:
                return command_cls(parsed_args)
            except SystemExit as e:
                self.fail(f"Command argument parsing exited with code {e.code}")

    def run_command(
        self,
        command_cls: type[commands.EgtCommand],
        *args: str,
        rescan: bool = True,
    ) -> tuple[int, str, str]:
        """Run a command returning stdout and stderr."""
        cmd = self.build_command(command_cls, *args, rescan=rescan)
        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            try:
                cmd.main()
                exit_code = 0
            except SystemExit as e:
                exit_code = e.code
        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_scan(self) -> None:
        State.rescan([self.workdir], statedir=self.workdir, config=self.config)
        state = State(self.config)
        state.load(self.workdir)
        self.assertIn("test", state.projects)
        self.assertIn("p1", state.projects)
        self.assertIn("p2", state.projects)
        self.assertEqual(len(state.projects), 3)

    def test_list(self) -> None:
        State.rescan([self.workdir], statedir=self.workdir, config=self.config)
        egt = egtlib.Egt(config=self.config, statedir=self.workdir)
        names = {p.name for p in egt.projects}
        self.assertIn("test", names)
        self.assertIn("p1", names)
        self.assertIn("p2", names)
        self.assertEqual(len(names), 3)

    def test_complete(self) -> None:
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
                    with mock.patch.object(
                        completion, "make_egt", return_value=egt
                    ):
                        with mock.patch(
                            "sys.stdout", new_callable=io.StringIO
                        ) as mock_stdout:
                            completion.main()
                    names = mock_stdout.getvalue().split("\n")[:-1]
                    self.assertEqual(names, subtest["res"])

    # TODO: test_summary
    # TODO: test_term
    # TODO: test_work
    # TODO: test_edit
    # TODO: test_grep

    def test_mrconfig(self) -> None:
        (self.p1 / ".git").mkdir()
        (self.p2 / ".git").mkdir()
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

    def test_annotate_stdin_and_file(self) -> None:
        cur_year = str(dt.date.today().year)

        file = self.workdir / "test.egt"
        file.write_text("")

        stdin = io.StringIO("test")
        orig_stdin = sys.stdin
        sys.stdin = stdin
        try:
            code, stdout, stderr = self.run_command(
                "annotate", "--stdin", file.as_posix()
            )
        finally:
            sys.stdin = orig_stdin
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout.splitlines(),
            [cur_year, "", "test"],
        )

    def test_annotate_stdin_only(self) -> None:
        cur_year = str(dt.date.today().year)

        stdin = io.StringIO("test")
        orig_stdin = sys.stdin
        sys.stdin = stdin
        try:
            code, stdout, stderr = self.run_command(
                "annotate",
                "--stdin",
                (self.workdir / "does-not-exist").as_posix(),
            )
        finally:
            sys.stdin = orig_stdin
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout.splitlines(),
            [cur_year, "", "test"],
        )

    # TODO: test_archive
    # TODO: test_serve

    def test_backup(self) -> None:
        cmd = self.build_command(commands.Backup)

        e = cmd.make_egt()
        tarfname = self.workdir / "backup.tar"
        with open(tarfname, "wb") as fd:
            cmd.backup(e, fd)

        # Test backup contents
        names = []
        import tarfile

        with tarfile.open(tarfname, "r") as tar:
            for f in tar:
                names.append(Path(f.name))

        wd = self.workdir.relative_to("/")
        self.assertIn(wd / "p" / ".egt", names)
        self.assertIn(wd / "p1" / ".egt", names)
        self.assertIn(wd / "p2" / ".egt", names)
        self.assertEqual(len(names), 3)
