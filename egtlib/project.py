from typing import Optional, TextIO, Any, List
import os.path
import subprocess
import datetime
import sys
import json
from .lang import set_locale
from .utils import format_duration, intervals_intersect, today, atomic_writer, stream_output
from .meta import Meta
from .log import Log
from .body import Body
import logging

log = logging.getLogger(__name__)


class ProjectState(object):
    def __init__(self, project: "Project"):
        statedir = project.statedir
        if statedir is None:
            from .state import State
            statedir = State.get_state_dir()
        # TODO: ensure name does not contain '/'
        self.abspath = os.path.join(statedir, "project-{}.json".format(project.name))
        self._state: Optional[dict] = None

    def get(self, name: str) -> Any:
        if self._state is None:
            self._state = self._load()
        return self._state.get(name, None)

    def set(self, name: str, val: Any) -> None:
        if self._state is None:
            self._state = self._load()
        self._state[name] = val
        self._save()

    def _load(self) -> dict:
        if not os.path.exists(self.abspath):
            return {}
        with open(self.abspath, "rt") as fd:
            return json.load(fd)

    def _save(self) -> None:
        with atomic_writer(self.abspath, "wt") as fd:
            json.dump(self._state, fd, indent=1)


class Project(object):
    def __init__(self, abspath, statedir=None):
        self.statedir = statedir
        self.abspath = abspath
        self.default_path, basename = os.path.split(abspath)
        if basename == ".egt":
            self.default_name = os.path.basename(self.default_path)
        else:
            self.default_name = os.path.splitext(basename)[0]
        self.default_tags = set()
        self.archived = False

        # Project state, loaded lazily, None if not loaded
        self._state = None

        self.meta = Meta()
        self.log = Log(self)
        self.body = Body(self)

    def set_locale(self) -> None:
        """
        Set the current locale to the one specified in the project header
        """
        set_locale(self.meta.get("lang"))

    @property
    def state(self):
        if not self._state:
            self._state = ProjectState(self)
        return self._state

    @property
    def name(self):
        name = self.meta.get("name", self.default_name)
        if not self.archived:
            return name

        since, until = self.formal_period
        if until:
            return name + until.strftime("-%Y-%m-%d")
        elif since:
            return name + since.strftime("-%Y-%m-%d")
        else:
            return name

    @property
    def path(self):
        return self.meta.get("path", self.default_path)

    @property
    def tags(self):
        return self.default_tags | self.meta.tags

    @classmethod
    def from_file(self, abspath, fd=None):
        # Default values, can be overridden by file metadata
        p = Project(abspath)
        # Load the actual data
        p.load(fd=fd)
        return p

    @classmethod
    def mock(self, abspath, name=None, path=None, tags=None):
        p = Project(abspath)
        if path is not None:
            p.default_path = path
        if name is not None:
            p.default_name = name
        if tags is not None:
            p.default_tags = tags
        return p

    def load(self, fd: Optional[TextIO] = None):
        from .parse import Lines
        lines = Lines(self.abspath, fd=fd)

        # Parse optionalmetadata

        # If it starts with a log, there is no metadata: stop
        # If the first line doesn't look like a header, stop
        first = lines.peek()
        if first is None:
            return
        if not Log.is_start_line(first) and Meta.is_start_line(first):
            log.debug("%s:%d: parsing metadata", lines.fname, lines.lineno)
            self.meta.parse(lines)

        lines.skip_empty_lines()

        # Parse log entries
        if lines.peek() is None:
            return
        if self.log.is_start_line(lines.peek()):
            log.debug("%s:%d: parsing log", lines.fname, lines.lineno)
            self.log.parse(lines, lang=self.meta.get("lang", None))
            lines.skip_empty_lines()

        # Parse body
        log.debug("%s:%d: parsing body", lines.fname, lines.lineno)
        self.body.parse(lines)

        # Allow to group archived projects with the same name.
        # Compute it separately to skip the archieve name mangling performed by
        # the name property on archived project names
        self.group = self.meta.get("name", self.default_name)

        # Quick access to 'archive' meta attribute
        if self.meta.get("archived", "false").lower() in ("true", "yes"):
            self.archived = True

    def print(self, out, today=None):
        """
        Serialize the whole project as a project file to the given file
        descriptor.
        """
        from . import utils
        if today is None:
            today = utils.today()

        if self.meta.print(out):
            print(file=out)

        if self.log.print(out, today=today):
            print(file=out)

        self.body.print(out)

    @property
    def last_updated(self):
        """
        Datetime when this project was last updated
        """
        last = self.log.last_entry
        if last is None:
            return None
        if last.until:
            return last.until
        return datetime.datetime.now()

    @property
    def elapsed(self):
        mins = 0
        for l in self.log.entries:
            mins += l.duration
        return mins

    @property
    def formatted_elapsed(self):
        return format_duration(self.elapsed)

    @property
    def formatted_tags(self):
        return ", ".join(sorted(self.tags))

    @property
    def next_actions(self):
        for el in self.body:
            if el.TAG != "next-actions":
                continue
            yield el

    @property
    def contexts(self):
        """
        Return a set with all contexts in this project
        """
        res = set()
        for el in self.body:
            if el.TAG != "next-actions":
                continue
            res |= el.contexts
        return res

    @property
    def formal_period(self):
        """
        Compute the begin and end dates for this project.

        If Start-date and End-date are provided in the metadata, return those.
        Else infer them from the first or last log entries.
        """
        since = self.meta.get("start-date", None)
        until = self.meta.get("end-date", None)
        if since is None:
            e = self.log.first_entry
            if e is not None:
                since = e.begin.date()
        elif since is not None:
            since = datetime.datetime.strptime(since, "%Y-%m-%d").date()
        if until is None:
            e = self.log.last_entry
            if e is not None:
                until = e.until
            if until is None:
                # Deal with entries that are still open
                until = today()
            else:
                until = until.date()
        elif until is not None:
            until = datetime.datetime.strptime(until, "%Y-%m-%d").date()
        return since, until

    def next_events(self, since=None, until=None):
        """
        Return the next events within the given date range
        """
        for na in self.next_actions:
            if na.event is None:
                continue
            d_since = na.event.get("start", None)
            if d_since is not None:
                d_since = d_since.date()
            d_until = na.event.get("end", None)
            if d_until is not None:
                d_until = d_until.date()
            else:
                d_until = d_since
            if not intervals_intersect(d_since, d_until, since, until):
                continue
            yield na

    def spawn_terminal(self, with_editor=False):
        from .system import run_work_session
        run_work_session(self, with_editor)

    def run_editor(self):
        from .system import run_editor
        run_editor(self)

    def run_grep(self, args):
        for gd in self.gitdirs():
            cwd = os.path.abspath(os.path.join(gd, ".."))
            cmd = ["git", "grep"] + args
            log.info("%s: git grep %s", cwd, " ".join(cmd))
            p = subprocess.Popen(cmd, cwd=cwd, close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for ltype, line in stream_output(p):
                if ltype == "stdout":
                    print("{}:{}".format(self.name, line), file=sys.stdout)
                elif ltype == "stderr":
                    print("{}:{}".format(self.name, line), file=sys.stderr)

    def gitdirs(self, depth=2, root=None):
        """
        Find all .git directories below the project path
        """
        # Default to self.path
        if root is None:
            root = self.path

        # Check the current dir
        cand = os.path.join(root, ".git")
        if os.path.isdir(cand):
            yield cand

        # Recurse into subdirs if we still have some way to go
        if depth > 1:
            for fn in os.listdir(root):
                if fn.startswith("."):
                    continue
                d = os.path.join(root, fn)
                if os.path.isdir(d):
                    for gd in self.gitdirs(depth - 1, d):
                        yield gd

    def backup(self, tarout):
        backup_paths = [x.strip() for x in self.meta.get("backup", "").split("\n")]

        # Backup the main todo/log file
        tarout.add(self.abspath)

        # Backup .git/config and .git/hooks
        if ".git" not in backup_paths and not self.meta.get("abstract", False):
            for gd in self.gitdirs():
                tarout.add(os.path.join(gd, "config"))
                hookdir = os.path.join(gd, "hooks")
                for fn in os.listdir(hookdir):
                    if fn.startswith("."):
                        continue
                    if fn.endswith(".sample"):
                        continue
                    tarout.add(os.path.join(hookdir, fn))
            # TODO: a shellscript with command to clone the .git again
            # TODO: a diff with uncommitted changes
            # (if you don't push, you don't back up, and it's fair enough)

        # Add all paths listed in the 'backup' metadata, one per line
        for p in backup_paths:
            if not p:
                continue
            path = os.path.join(self.path, p)
            if not os.path.exists(path):
                continue
            tarout.add(path)

    def archive_month(self, archive_dir: str, month: datetime.date) -> Optional["Project"]:
        """
        Write log entries for the given month to an archive file
        """
        # Generate the target file name
        if "%" in archive_dir:
            archive_dir = month.strftime(archive_dir)
        archive_dir = os.path.expanduser(archive_dir)
        pathname = os.path.join(archive_dir, month.strftime("%Y%m-") + self.name + ".egt")
        if os.path.exists(pathname):
            log.info("%s not archived for %04d-%02d: %s already exists", self.name, month.year, month.month, pathname)
            return None

        # Select the log entries
        next_month = (month + datetime.timedelta(days=40)).replace(day=1)
        entries = self.log.detach_entries(month, next_month)
        if not entries:
            return None

        # Create a new project
        archived = Project(pathname)
        archived.meta = self.meta.copy()
        archived.log._entries = entries
        archived.meta.set("archived", "yes")
        duration = sum(e.duration for e in entries)
        archived.meta.set("total", format_duration(duration))
        archived.archived = True
        with open(pathname, "wt") as out:
            archived.print(out)
        return archived

    def archive(self, cutoff: datetime.date) -> List["Project"]:
        """
        Archive contents until the given cutoff date (excluded).

        Returns the list of archive file names written.
        """
        archive_dir = self.meta.get("archive-dir", None)
        if archive_dir is None:
            log.info("%s not archived: archive-dir not found in header", self.name)
            return []

        # Get the datetime of the first Entry in the log
        archived = []
        date = self.log.first_entry.begin.date()

        # Iterate until cutoff
        while date < cutoff:
            arc = self.archive_month(archive_dir, date)
            if arc is not None:
                archived.append(arc)
            date = (date + datetime.timedelta(days=40)).replace(day=1)

        return archived

    @classmethod
    def has_project(cls, abspath):
        return os.path.exists(abspath)
