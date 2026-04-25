import abc
import argparse
import datetime as dt
import inspect
import logging
import os
import shutil
import sys
import tarfile
from collections.abc import Iterator
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

import egtlib
from egtlib.utils import (
    HoursCol,
    LastEntryCol,
    SummaryCol,
    TaskStatCol,
    format_td,
    format_duration,
)

from . import cli, reports
from .body import BodyEntry
from .config import Config

log = logging.getLogger(__name__)

type Subparsers = "argparse._SubParsersAction[Any]"

COMMANDS: list[type["Command"]] = []


class Command(cli.Command, abc.ABC):
    """Base for Egt commands."""

    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        #: Egt configuration
        self.config = Config(load=True)

    @abc.abstractmethod
    def main(self) -> None:
        """Main command body."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Make the command automatically available on the CLI."""
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            COMMANDS.append(cls)


class Scan(Command):
    """
    Update the list of known project files, by scanning everything below the
    home directory.
    """

    def main(self) -> None:
        if self.args.roots:
            dirs = self.args.roots
        else:
            dirs = [Path.home()]
        from .state import State

        State.rescan(dirs, config=self.config)

    @classmethod
    def add_subparser(
        cls, subparsers: "argparse._SubParsersAction[Any]"
    ) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        parser.add_argument(
            "roots",
            nargs="*",
            type=Path,
            help="root directories to search (default: the home directory)",
        )
        return parser


class EgtCommand(Command, abc.ABC):
    """Base for Egt commands."""

    def make_egt(self, filter: list[str] = []) -> egtlib.Egt:
        return egtlib.Egt(
            config=self.config, filter=filter, show_archived=self.args.archived
        )

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        parser.add_argument(
            "--archived",
            action="store_true",
            help="also show archived projects",
        )
        return parser


class ProjectsCommand(EgtCommand, abc.ABC):
    """Command that works on a selection of projects."""

    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.egt = self.make_egt(filter=self.args.projects)
        if not self.egt.projects:
            raise cli.Fail("No projects found. Run 'egt scan' first.")

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        parser.add_argument(
            "projects", nargs="*", help="projects list or filter (default: all)"
        )
        return parser


class List(ProjectsCommand):
    """
    List known projects.
    """

    def main(self) -> None:
        homedir = os.path.expanduser("~")
        projects = self.egt.projects

        if self.args.age:
            projects.sort(key=lambda p: -p.mtime)
            now = dt.datetime.now()
            ages = []
            for project in projects:
                age = now - dt.datetime.fromtimestamp(project.mtime)
                ages.append(format_td(age))
            age_len = max(len(a) for a in ages)

        name_len = max(len(x.name) for x in projects)
        for idx, p in enumerate(projects):
            if self.args.files:
                if self.args.age:
                    print(ages[idx].ljust(age_len), p.abspath)
                else:
                    print(p.abspath)
            else:
                path = p.path.as_posix()
                if p.path.is_relative_to(homedir):
                    path = "~/" + p.path.relative_to(homedir).as_posix()
                if self.args.age:
                    print(
                        p.name.ljust(name_len), ages[idx].ljust(age_len), path
                    )
                else:
                    print(p.name.ljust(name_len), path)

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        parser.add_argument(
            "--files", action="store_true", help="list paths to .egt files"
        )
        parser.add_argument(
            "--age", action="store_true", help="sort by age and show ages"
        )
        return parser


class Summary(ProjectsCommand):
    """
    Print a summary of the activity on all projects
    """

    def _load_col_config(
        self, projs: list[egtlib.Project]
    ) -> tuple[list[SummaryCol], dict[str, SummaryCol]]:
        COLUMNS = {
            "name": SummaryCol("Name", "l", lambda p: p.name),
            "tags": SummaryCol("Tags", "l", lambda p: " ".join(sorted(p.tags))),
            "logs": SummaryCol(
                "Logs", "r", lambda p: str(len(list(p.log.entries)))
            ),
            "tasks": TaskStatCol("Tasks", "r", projs),
            "hours": HoursCol("Hrs", "c"),
            "last": LastEntryCol("Last entry", "r"),
        }
        active_cols = []
        for col in self.config.summary_columns:
            if col in COLUMNS:
                active_cols.append(COLUMNS[col])
                active_cols[-1].init_data()
        return active_cols, COLUMNS

    def main(self) -> None:
        from texttable import Texttable

        projs = self.egt.projects

        active_cols, columns = self._load_col_config(projs)
        termsize = shutil.get_terminal_size((80, 25))
        if self.args.width:
            table = Texttable(max_width=self.args.width)
        else:
            table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align([c.align for c in active_cols])
        table.add_row([c.label for c in active_cols])

        if self.args.name:
            sorted_projects = sorted(projs, key=lambda p: p.name)
        elif self.args.tasks:
            sorted_projects = sorted(
                projs, key=lambda p: columns["tasks"].task_stats[p.name]
            )
        else:
            blanks = []
            worked = []
            for p in projs:
                if p.last_updated is None:
                    blanks.append(p)
                else:
                    worked.append(p)

            blanks.sort(key=lambda p: p.name)
            worked.sort(key=lambda p: p.last_updated)
            sorted_projects = blanks + worked

        def add_summary(p: egtlib.Project) -> None:
            table.add_row([c.func(p) for c in active_cols])

        #        res["mins"] = self.elapsed
        #        res["last"] = self.last_updated
        #        res["tags"] = self.tags
        #        res["entries"] = len(self.log)
        #        #"%s" % format_duration(mins),
        #        #format_td(dt.datetime.now() - self.last_updated)),
        #        print "%s\t%s" % (self.name, ", ".join(stats))

        for p in sorted_projects:
            add_summary(p)

        print(table.draw())

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        sorting = parser.add_mutually_exclusive_group()
        sorting.add_argument(
            "--name", action="store_true", help="sort projects by name"
        )
        sorting.add_argument(
            "--tasks",
            action="store_true",
            help="sort projects by number of tasks",
        )
        sorting.add_argument(
            "--update",
            action="store_true",
            help="sort projects by last log-update (default)",
        )
        parser.add_argument(
            "--width",
            type=int,
            help="width of output, useful when piped to other command",
        )
        return parser


class Term(ProjectsCommand):
    """
    Open a terminal in the directory of the given project(s)
    """

    def main(self) -> None:
        for proj in self.egt.projects:
            proj.spawn_terminal()


class Work(ProjectsCommand):
    """
    Open a terminal in a project directory, and edit the project file.
    """

    def main(self) -> None:
        for proj in self.egt.projects:
            proj.spawn_terminal(with_editor=True)


class Edit(ProjectsCommand):
    """
    Open a terminal in a project directory, and edit the project file.
    """

    def main(self) -> None:
        for proj in self.egt.projects:
            proj.run_editor()


class Grep(EgtCommand):
    """
    Run 'git grep' on all project .git dirs
    """

    def main(self) -> None:
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.run_grep([self.args.pattern])

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        parser.add_argument("pattern", help="pattern to pass to git grep")
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        return parser


class MrConfig(ProjectsCommand):
    """
    Print a mr configuration snippet for all git projects
    """

    def main(self) -> None:
        for proj in self.egt.projects:
            for gd in proj.gitdirs():
                print(f"[{gd.parent.absolute()}]")
                print()


class Weekrpt(ProjectsCommand):
    """
    Compute weekly reports
    """

    def weekrpt(
        self,
        tags: set[str] | None = None,
        end: dt.date | None = None,
        days: int = 7,
        projs: list[egtlib.Project] | None = None,
    ) -> dict[str, Any]:
        rep = reports.WeeklyReport()
        if projs:
            for p in projs:
                rep.add(p)
        else:
            for p in self.egt.projects:
                if not tags or p.tags.issuperset(tags):
                    rep.add(p)
        return rep.report(end, days)

    def main(self) -> None:
        from texttable import Texttable

        end = None

        termsize = shutil.get_terminal_size((80, 25))
        table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align(("l", "r", "r", "r", "r"))
        table.set_cols_dtype(("t", "i", "i", "i", "i"))
        table.add_row(("Tag", "Entries", "Hours", "h/day", "h/wday"))
        rep = self.weekrpt(end=end)
        print()
        print(f" * Activity from {rep['begin']} to {rep['until']}")
        print()
        log = rep["log"]

        # Global stats
        table.add_row(
            (
                "(any)",
                rep["count"],
                rep["hours"],
                rep["hours_per_day"],
                rep["hours_per_workday"],
            )
        )

        # Per-tag stats
        all_tags = set()
        for p in self.egt.projects:
            all_tags |= p.tags
        for t in sorted(all_tags):
            rep = self.weekrpt(end=end, tags={t})
            table.add_row(
                (
                    t,
                    rep["count"],
                    rep["hours"],
                    rep["hours_per_day"],
                    rep["hours_per_workday"],
                )
            )

        print(table.draw())
        print()

        # Per-package stats
        table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align(("l", "r", "r", "r", "r"))
        table.set_cols_dtype(("t", "i", "i", "i", "i"))
        table.add_row(("Project", "Entries", "Hours", "h/day", "h/wday"))
        for p in self.egt.projects:
            rep = self.weekrpt(end=end, projs=[p])
            if not rep["count"]:
                continue
            table.add_row(
                (
                    p.name,
                    rep["count"],
                    rep["hours"],
                    rep["hours_per_day"],
                    rep["hours_per_workday"],
                )
            )

        print(table.draw())
        print()

        log.sort(key=lambda x: x[0].begin)
        for log_entry, p in log:
            log_entry.print(sys.stdout, project=p)


class Monthrpt(ProjectsCommand):
    """
    Compute monthly reports
    """

    def main(self) -> None:
        from texttable import Texttable

        by_day: dict[dt.date, int] = Counter()
        for p in self.egt.projects:
            for e in p.log.entries:
                by_day[e.begin.date()] += e.duration

        termsize = shutil.get_terminal_size((80, 25))
        table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align(("l", "r"))
        table.set_cols_dtype(("t", "i"))
        table.add_row(("Day", "Hours"))

        for day, duration in sorted(by_day.items()):
            table.add_row((str(day), format_duration(duration)))

        print(table.draw())
        print()


class PrintCommand(ProjectsCommand):
    """Command that print egt files in part or whole."""

    def print_log(self) -> None:
        log = []
        projs = set()
        for p in self.egt.projects:
            for log_entry in p.log.entries:
                log.append((log_entry, p))
            projs.add(p)

        log.sort(key=lambda x: x[0].begin)
        if len(projs) == 1:
            for log_entry, p in log:
                log_entry.print(sys.stdout)
        else:
            for log_entry, p in log:
                log_entry.print(sys.stdout, p)


class PrintLog(PrintCommand):
    """
    Output the log for one or more projects
    """

    NAME = "print_log"

    def main(self) -> None:
        self.print_log()


class Cat(PrintCommand):
    """
    Output the content of one or more project files
    """

    NAME = "cat"

    def main(self) -> None:
        if self.args.log:
            self.print_log()
            return

        for p in self.egt.projects:
            if self.args.raw:
                with open(p.abspath) as fd:
                    print(fd.read(), end="")
            else:
                p.sync_tasks(modify_state=False)
                p.print(sys.stdout)

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-r",
            "--raw",
            action="store_true",
            help="print the egt-file(s) directly, do not update task info",
        )
        group.add_argument(
            "-l",
            "--log",
            action="store_true",
            help="limit output to (merged) project log",
        )
        return parser


class Annotate(EgtCommand):
    """
    Print a project file on stdout, annotating its contents with anything
    useful that can be computed.
    """

    def get_project(self) -> egtlib.Project | None:
        """Return the project to annotate."""
        path = Path(self.args.project)
        if self.args.stdin:
            return egtlib.Project.from_file(
                path, fd=sys.stdin, config=self.config
            )
        if path.exists():
            return egtlib.Project.from_file(path, config=self.config)

        egt = egtlib.Egt(config=self.config, show_archived=True)
        if p := egt.get(self.args.project):
            return p

        log.info("No project found.")
        return None

    def main(self) -> None:
        if (proj := self.get_project()) is None:
            return

        proj.annotate()
        proj.print(sys.stdout)

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        parser.add_argument("project", help="project to work on")
        parser.add_argument(
            "--stdin",
            action="store_true",
            help="read project file data from stdin",
        )
        return parser


class Archive(ProjectsCommand):
    """
    Output the log for one or more projects
    """

    def main(self) -> None:
        cutoff = dt.datetime.strptime(self.args.month, "%Y-%m").date()
        cutoff = (cutoff + dt.timedelta(days=40)).replace(day=1)

        with self.report_fd() as fd:
            for p in self.egt.projects:
                archives = p.archive(
                    cutoff,
                    report_fd=fd,
                    save=self.args.remove_old,
                    combined=self.args.singlefile,
                )
                for archive in archives:
                    print(f"Archived {p.name}: {archive.abspath}")

    @contextmanager
    def report_fd(self) -> Iterator[IO[str]]:
        if self.args.output:
            with open(self.args.output, "wt") as fd:
                yield fd
        else:
            yield sys.stdout

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        last_month = dt.date.today().replace(day=1) - dt.timedelta(days=1)
        parser.add_argument(
            "--month",
            "-m",
            action="store",
            default=last_month.strftime("%Y-%m"),
            help="print log until the given month (default: %(default)s)",
        )
        parser.add_argument(
            "--remove-old",
            action="store_true",
            help="rewrite the original project file removing archived entries",
        )
        parser.add_argument(
            "--output",
            "-o",
            action="store",
            help="output of aggregated archived logs"
            " (default: standard output)",
        )
        parser.add_argument(
            "--singlefile",
            "-s",
            action="store_true",
            help="write archive log lines into a single file",
        )
        return parser


class Backup(ProjectsCommand):
    """
    Backup of egt project core information
    """

    def backup(self, out: IO[bytes] = sys.stdout.buffer) -> None:
        with tarfile.open(mode="w|", fileobj=out) as tarout:
            for p in self.egt.projects:
                p.backup(tarout)

    def main(self) -> None:
        out = self.config.backup_output
        if out:
            out = dt.datetime.now().strftime(out)
            with open(out, "wb") as fd:
                self.backup(fd)
        else:
            self.backup(sys.stdout.buffer)


class Next(ProjectsCommand):
    """
    Show the top of the notes of the most recent .egt files
    """

    def get_lead_entries(
        self, project: egtlib.Project
    ) -> tuple[BodyEntry | None, BodyEntry | None]:
        first: BodyEntry | None = None
        second: BodyEntry | None = None
        for entry in project.body.content:
            if entry.is_empty():
                continue
            if first is None:
                first = entry
                continue

            first_indent = first.indent + (" " * len(first.bullet))
            if len(entry.indent) > len(
                first_indent
            ) and entry.indent.startswith(first_indent):
                second = entry
            break
        return first, second

    def main(self) -> None:
        from texttable import Texttable

        termsize = shutil.get_terminal_size((80, 25))
        table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align(("l", "l", "l"))
        table.add_row(("Name", "Age", "First entry"))

        now = dt.datetime.today()
        projects = []
        for project in self.egt.projects:
            # Find the first two non-empty entries
            entry, next_entry = self.get_lead_entries(project)
            if not entry:
                continue

            mtime = dt.datetime.fromtimestamp(project.mtime)

            # Get the project time or due date timestamp
            if entry.get_content().startswith("# "):
                # If the first line is a heading, then there is no now&next
                # section
                sort_key = (1, now - mtime, "")
            elif date := entry.get_date():
                # Sort by due date
                ts = dt.datetime.combine(date, dt.time(0))
                if ts > now:
                    sort_key = (0, ts - now, "+")
                else:
                    sort_key = (0, ts - now, "")
            else:
                # Sort by age
                sort_key = (0, now - mtime, "")

            text = entry.get_content()
            if next_entry:
                if not text.endswith(":"):
                    text += ": "
                else:
                    text += " "
                text += next_entry.get_content()

            projects.append((sort_key, project, text))

        projects.sort()

        for (part, age, sign), project, text in projects:
            if part == 0:
                fmt_age = sign + format_td(age)
            else:
                fmt_age = "(" + format_td(age) + ")"

            table.add_row((project.name, fmt_age, text))

        print(table.draw())


class Completion(EgtCommand):
    """
    Tab completion support
    """

    def main(self) -> None:
        if not self.args.subcommand:
            raise cli.Fail("Usage: egt completion {commands|projects|tags}")
        if self.args.subcommand == "commands":
            for c in COMMANDS:
                print(c.NAME or c.__name__.lower())
        elif self.args.subcommand == "projects":
            e = self.make_egt()
            names = e.project_names
            for n in names:
                print(n)
        elif self.args.subcommand == "tags":
            e = self.make_egt()
            res = set()
            for p in e.projects:
                res |= p.tags
            for n in sorted(res):
                print(n)
        else:
            raise cli.Fail("Usage: egt completion {commands|projects|tags}")

    @classmethod
    def add_subparser(cls, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = super().add_subparser(subparsers)
        parser.add_argument(
            "subcommand",
            nargs="?",
            default=None,
            help="command for which to provide completion",
        )
        return parser
