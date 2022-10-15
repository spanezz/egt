from __future__ import annotations

import datetime
import logging
import os
import sys
import typing
from configparser import RawConfigParser
from contextlib import contextmanager
from typing import Type

import egtlib
from . import cli

log = logging.getLogger(__name__)


COMMANDS: typing.List[Type["cli.Command"]] = []


def register(c: Type["cli.Command"]):
    COMMANDS.append(c)
    return c


class EgtCommand(cli.Command):
    def __init__(self, args):
        super().__init__(args)
        self.args = args
        self.config = RawConfigParser()
        self.config.read([os.path.expanduser("~/.egt.conf")])

    def make_egt(self, filter: typing.List[str] = []):
        return egtlib.Egt(config=self.config, filter=filter, show_archived=self.args.archived)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("--archived", action="store_true", help="also show archived projects")
        return parser


@register
class Scan(EgtCommand):
    """
    Update the list of known project files, by scanning everything below the
    home directory.
    """
    def main(self):
        if self.args.roots:
            dirs = self.args.roots
        else:
            dirs = [os.path.expanduser("~")]
        from .state import State
        State.rescan(dirs)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("roots", nargs="*", help="root directories to search (default: the home directory)")
        return parser


@register
class List(EgtCommand):
    """
    List known projects.
    """
    def main(self):
        e = self.make_egt(filter=self.args.projects)
        if not e.projects:
            print("No projects found. Run 'egt scan' first.", file=sys.stderr)
            return
        name_len = max((len(x.name) for x in e.projects))
        homedir = os.path.expanduser("~")
        for p in e.projects:
            if self.args.files:
                print(p.abspath)
            elif p.path.startswith(homedir):
                print(p.name.ljust(name_len), "~%s" % p.path[len(homedir):])
            else:
                print(p.name.ljust(name_len), p.path)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="*", help="projects list or filter (default: all)")
        parser.add_argument("--files", action="store_true", help="list paths to .egt files")
        return parser


@register
class Summary(EgtCommand):
    """
    Print a summary of the activity on all projects
    """
    def main(self):
        import shutil

        from texttable import Texttable

        from egtlib.utils import format_duration, format_td
        termsize = shutil.get_terminal_size((80, 25))
        table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align(("l", "l", "r", "c", "r"))
        table.add_row(("Name", "Tags", "Logs", "Hrs", "Last entry"))
        e = self.make_egt(self.args.projects)
        projs = e.projects

        blanks = []
        worked = []
        for p in projs:
            if p.last_updated is None:
                blanks.append(p)
            else:
                worked.append(p)

        blanks.sort(key=lambda p: p.name)
        worked.sort(key=lambda p: p.last_updated)

        now = datetime.datetime.now()

        def add_summary(p):
            table.add_row((
                p.name,
                " ".join(sorted(p.tags)),
                len(list(p.log.entries)),
                format_duration(p.elapsed, tabular=True) if p.last_updated else "--",
                "%s ago" % format_td(now - p.last_updated, tabular=True) if p.last_updated else "--",
            ))

#        res["mins"] = self.elapsed
#        res["last"] = self.last_updated
#        res["tags"] = self.tags
#        res["entries"] = len(self.log)
#        #"%s" % format_duration(mins),
#        #format_td(datetime.datetime.now() - self.last_updated)),
#        print "%s\t%s" % (self.name, ", ".join(stats))

        for p in blanks:
            add_summary(p)
        for p in worked:
            add_summary(p)

        print(table.draw())

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="*", help="list of projects to summarise (default: all)")
        return parser


@register
class Term(EgtCommand):
    """
    Open a terminal in the directory of the given project(s)
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.spawn_terminal()

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="+", help="project(s) for which to open a terminal")
        return parser


@register
class Work(EgtCommand):
    """
    Open a terminal in a project directory, and edit the project file.
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.spawn_terminal(with_editor=True)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="+", help="project(s) to work on")
        return parser


@register
class Edit(EgtCommand):
    """
    Open a terminal in a project directory, and edit the project file.
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.run_editor()

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="+", help="project(s) to work on")
        return parser


@register
class Grep(EgtCommand):
    """
    Run 'git grep' on all project .git dirs
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.run_grep([self.args.pattern])

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("pattern", help="pattern to pass to git grep")
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        return parser


@register
class MrConfig(EgtCommand):
    """
    Print a mr configuration snippet for all git projects
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for name, proj in e.projects.items():
            for gd in proj.gitdirs():
                gd = os.path.abspath(os.path.join(gd, ".."))
                print("[{}]".format(gd))
                print()

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        return parser


@register
class Weekrpt(EgtCommand):
    """
    Compute weekly reports
    """
    def main(self):
        import shutil

        from texttable import Texttable

        # egt weekrpt also showing stats by project, and by tags
        e = self.make_egt(self.args.projects)
        # TODO: add an option to choose the current time
        # if self.args.projects:
        #     end = datetime.datetime.strptime(self.args.projects[0], "%Y-%m-%d").date()
        # else:
        #     end = None
        end = None

        termsize = shutil.get_terminal_size((80, 25))
        table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align(("l", "r", "r", "r", "r"))
        table.set_cols_dtype(('t', "i", "i", "i", "i"))
        table.add_row(("Tag", "Entries", "Hours", "h/day", "h/wday"))
        rep = e.weekrpt(end=end)
        print()
        print(" * Activity from %s to %s" % (rep["begin"], rep["until"]))
        print()
        log = rep["log"]

        # Global stats
        table.add_row(("(any)", rep["count"], rep["hours"], rep["hours_per_day"], rep["hours_per_workday"]))

        # Per-tag stats
        all_tags = set()
        for p in e.projects:
            all_tags |= p.tags
        for t in sorted(all_tags):
            rep = e.weekrpt(end=end, tags=frozenset((t,)))
            table.add_row((t, rep["count"], rep["hours"], rep["hours_per_day"], rep["hours_per_workday"]))

        print(table.draw())
        print()

        # Per-package stats
        table = Texttable(max_width=termsize.columns)
        table.set_deco(Texttable.HEADER)
        table.set_cols_align(("l", "r", "r", "r", "r"))
        table.set_cols_dtype(('t', "i", "i", "i", "i"))
        table.add_row(("Project", "Entries", "Hours", "h/day", "h/wday"))
        for p in e.projects:
            rep = e.weekrpt(end=end, projs=[p])
            if not rep["count"]:
                continue
            table.add_row((p.name, rep["count"], rep["hours"], rep["hours_per_day"], rep["hours_per_workday"]))

        print(table.draw())
        print()

        log.sort(key=lambda x: x[0].begin)
        for log_entry, p in log:
            log_entry.print(sys.stdout, project=p.name)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        return parser


@register
class PrintLog(EgtCommand):
    """
    Output the log for one or more projects
    """
    NAME = "print_log"

    def main(self):
        e = self.make_egt(self.args.projects)
        log = []
        projs = set()
        for p in e.projects:
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

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        return parser


@register
class Cat(EgtCommand):
    """
    Output the content of one or more project files
    """
    NAME = "cat"

    def main(self):
        if self.args.log:
            # delegate to separate command
            action = PrintLog(self.args)
            action.main()
            return

        e = self.make_egt(self.args.projects)
        for p in e.projects:
            if self.args.raw:
                with open(p.abspath) as fd:
                    print(fd.read(), end="")
            else:
                p.sync_tasks(modify_state=False)
                p.print(sys.stdout)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-r", "--raw", action="store_true",
                           help="print the egt-file(s) directly, do not update task info)")
        group.add_argument("-l", "--log", action="store_true", help="limit output to (merged) project log")
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        return parser


@register
class Annotate(EgtCommand):
    """
    Print a project file on stdout, annotating its contents with anything
    useful that can be computed.
    """
    def main(self):
        egt = egtlib.Egt(config=self.config, show_archived=True)
        abspath = os.path.abspath(self.args.project)
        if os.path.exists(abspath):
            if self.args.stdin:
                proj = egt.load_project(abspath, project_fd=sys.stdin)
            else:
                proj = egt.load_project(abspath)
        else:
            if self.args.stdin:
                proj = egt.project(self.args.project, project_fd=sys.stdin)
            else:
                proj = egt.project(self.args.project)
        if proj is None:
            return

        proj.annotate()
        proj.print(sys.stdout)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("project", help="project to work on")
        parser.add_argument("--stdin", action="store_true", help="read project file data from stdin")
        return parser


@register
class Archive(EgtCommand):
    """
    Output the log for one or more projects
    """
    def main(self):
        cutoff = datetime.datetime.strptime(self.args.month, "%Y-%m").date()
        cutoff = (cutoff + datetime.timedelta(days=40)).replace(day=1)

        e = self.make_egt(self.args.projects)
        with self.report_fd() as fd:
            for p in e.projects:
                archives = p.archive(cutoff, report_fd=fd, save=self.args.remove_old)
                for archive in archives:
                    print("Archived {}: {}".format(p.name, archive.abspath))

    @contextmanager
    def report_fd(self):
        if self.args.output:
            with open(self.args.output, "wt") as fd:
                yield fd
        else:
            yield sys.stdout

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        last_month = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
        parser.add_argument(
                "--month", "-m", action="store", default=last_month.strftime("%Y-%m"),
                help="print log until the given month (default: %(default)s)")
        parser.add_argument(
                "--remove-old", action="store_true",
                help="rewrite the original project file removing archived entries")
        parser.add_argument(
                "--output", "-o", action="store",
                help="output of aggregated archived logs (default: standard output)")
        return parser


@register
class Backup(EgtCommand):
    """
    Backup of egt project core information
    """
    def main(self):
        out = self.config.get("config", "backup-output", fallback=None)
        e = self.make_egt(self.args.projects)
        if out:
            out = datetime.datetime.now().strftime(out)
            with open(out, "wb") as fd:
                e.backup(fd)
        else:
            e.backup(sys.stdout)

    @classmethod
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("projects", nargs="*", help="project(s) to work on")
        return parser


@register
class Completion(EgtCommand):
    """
    Tab completion support
    """
    def main(self):
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
    def add_subparser(cls, subparsers):
        parser = super().add_subparser(subparsers)
        parser.add_argument("subcommand", nargs="?", default=None, help="command for which to provide completion")
        return parser
