import egtlib
from .utils import format_duration
from configparser import RawConfigParser
import os
import datetime
import calendar
import sys
import io
import logging

log = logging.getLogger(__name__)


class CommandError(Exception):
    pass


class Command:
    COMMANDS = []

    def __init__(self, args):
        self.args = args
        self.config = RawConfigParser()
        self.config.read([os.path.expanduser("~/.egt.conf")])

    def make_egt(self, filter=[]):
        return egtlib.Egt(config=self.config, filter=filter, show_archived=self.args.archived)

    @classmethod
    def add_args(cls, subparser):
        pass

    @classmethod
    def register(cls, c):
        cls.COMMANDS.append(c)


@Command.register
class Scan(Command):
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
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("roots", nargs="*", help="root directories to search (default: the home directory)")


@Command.register
class List(Command):
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
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="*", help="projects list or filter (default: all)")
        subparser.add_argument("--files", action="store_true", help="list paths to .egt files")


@Command.register
class Summary(Command):
    """
    Print a summary of the activity on all projects
    """
    def main(self):
        from egtlib.texttable import Texttable
        from egtlib.utils import format_duration, format_td
        import shutil
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

        for p in blanks: add_summary(p)
        for p in worked: add_summary(p)

        print(table.draw())

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="*", help="list of projects to summarise (default: all)")


@Command.register
class Term(Command):
    """
    Open a terminal in the directory of the given project(s)
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.spawn_terminal()

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="+", help="project(s) for which to open a terminal")


@Command.register
class Work(Command):
    """
    Open a terminal in a project directory, and edit the project file.
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.spawn_terminal(with_editor=True)

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="+", help="project(s) to work on")


@Command.register
class Edit(Command):
    """
    Open a terminal in a project directory, and edit the project file.
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.run_editor()

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="+", help="project(s) to work on")


@Command.register
class Grep(Command):
    """
    Run 'git grep' on all project .git dirs
    """
    def main(self):
        e = self.make_egt(self.args.projects)
        for proj in e.projects:
            proj.run_grep([self.args.pattern])

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("pattern", help="pattern to pass to git grep")
        subparser.add_argument("projects", nargs="*", help="project(s) to work on")


@Command.register
class MrConfig(Command):
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
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="*", help="project(s) to work on")


@Command.register
class Weekrpt(Command):
    """
    Compute weekly reports
    """
    def main(self):
        from egtlib.texttable import Texttable
        import shutil
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
            if not rep["count"]: continue
            table.add_row((p.name, rep["count"], rep["hours"], rep["hours_per_day"], rep["hours_per_workday"]))

        print(table.draw())
        print()

        log.sort(key=lambda x: x[0].begin)
        for l, p in log:
            l.print(sys.stdout, project=p.name)

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="*", help="project(s) to work on")


@Command.register
class PrintLog(Command):
    """
    Output the log for one or more projects
    """
    NAME = "print_log"

    def main(self):
        e = self.make_egt(self.args.projects)
        log = []
        projs = set()
        for p in e.projects:
            for l in p.log.entries:
                log.append((l, p))
            projs.add(p)

        log.sort(key=lambda x: x[0].begin)
        if len(projs) == 1:
            for l, p in log:
                l.print(sys.stdout)
        else:
            for l, p in log:
                l.print(sys.stdout)

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="*", help="project(s) to work on")


@Command.register
class Annotate(Command):
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

        proj.body.sync_tasks()

        lang = proj.meta.get("lang")
        if lang:
            import locale
            try:
                locname = locale.normalize(lang + ".UTF-8")
                locale.setlocale(locale.LC_ALL, locname)
            except locale.Error as e:
                log.warn("Cannot set locale %s: %s", locname, e)

        # Sync logs after setting locale, so we get the right day/month names
        proj.log.sync()
        proj.print(sys.stdout)

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("project", help="project to work on")
        subparser.add_argument("--stdin", action="store_true", help="read project file data from stdin")


@Command.register
class Archive(Command):
    """
    Output the log for one or more projects
    """
    def write_archive(self, project, entries, cutoff):
        pathname = project.meta.get("archive-dir", None)
        if pathname is None: return "not archived: archive-dir not found in header"
        if "%" in pathname:
            pathname = cutoff.strftime(pathname)
        pathname = os.path.expanduser(pathname)
        pathname = os.path.join(pathname, cutoff.strftime("%Y%m-") + project.name + ".egt")
        if os.path.exists(pathname):
            return "not archived: {} already exists".format(pathname)
        duration = sum(e.duration for e in entries)
        with io.open(pathname, "wt") as fd:
            if "name" not in project.meta._raw:
                print("Name:", project.name, file=fd)
            project.meta.set("archived", "yes")
            project.meta.print(file=fd)
            print("{}: {}".format("Total", format_duration(duration)), file=fd)
            print(file=fd)
            for l in entries:
                l.print(file=fd)
        return pathname

    def main(self):
        # TODO: move to Project and unit test it
        cutoff = datetime.datetime.strptime(self.args.month, "%Y-%m").date()
        cutoff = cutoff.replace(day=calendar.monthrange(cutoff.year, cutoff.month)[1])
        e = self.make_egt(self.args.projects)
        archive_results = {}
        for p in e.projects:
            # TODO: copy timebase and entry, ignore commands
            # TODO: generate initial timebase in archived log
            entries = list(l for l in p.log.entries if l.begin.date() <= cutoff)
            if not entries: continue
            archive_results[p.name] = self.write_archive(p, entries, cutoff)
            duration = sum(e.duration for e in entries)
            # TODO: use Meta.print
            if "name" not in p.meta._raw:
                print("Name:", p.name)
            p.meta.print()
            print("{}: {}".format("Total", format_duration(duration)))
            print()
            # TODO: use Log.print or entry.print
            for l in entries:
                l.print()
            print()
        for name, res in sorted(archive_results.items()):
            print("Archived {}: {}".format(name, res))

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="*", help="project(s) to work on")
        last_month = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
        subparser.add_argument("--month", "-m", action="store", default=last_month.strftime("%Y-%m"), help="print log until the given month (default: %(default)s)")


@Command.register
class Backup(Command):
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
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("projects", nargs="*", help="project(s) to work on")


@Command.register
class Completion(Command):
    """
    Tab completion support
    """
    def main(self):
        if not self.args.subcommand:
            raise CommandError("Usage: egt completion {projects|tags|contexts}")
        if self.args.subcommand == "projects":
            e = self.make_egt()
            names = sorted(e.projects.keys())
            for n in names:
                print(n)
        elif self.args.subcommand == "tags":
            e = self.make_egt()
            res = set()
            for p in e.projects:
                res |= p.tags
            for n in sorted(res):
                print(n)
        elif self.args.subcommand == "contexts":
            e = self.make_egt()
            res = set()
            for p in e.projects:
                res |= p.contexts
            for n in sorted(res):
                print(n)
        else:
            raise CommandError("Usage: egt completion {projects|tags|contexts}")

    @classmethod
    def add_args(cls, subparser):
        super().add_args(subparser)
        subparser.add_argument("subcommand", nargs="?", default=None, help="command for which to provide completion")
