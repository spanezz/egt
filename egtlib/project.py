from __future__ import annotations

import datetime
import json
import logging
import os.path
import subprocess
import sys
from typing import Any, List, Optional, Set, TextIO, Tuple, cast

from .body import Body
from .lang import set_locale
from .log import Log
from .meta import Meta
from .utils import atomic_writer, format_duration, stream_output, today
from .config import Config

log = logging.getLogger(__name__)


class ProjectState:
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


class Project:
    """
    A .egt file.

    The file contains:

    * Metadata (meta.Meta)
    * A time-based log (log.Log)
    * A free-text body (body.Body)
    """

    def __init__(self, abspath: str, *, config: Config, statedir: Optional[str] = None):
        self.config = config
        self.statedir = statedir
        self.abspath = abspath
        self.default_path, basename = os.path.split(abspath)
        if basename == ".egt":
            self.default_name = os.path.basename(self.default_path)
        else:
            self.default_name = os.path.splitext(basename)[0]
        self.default_tags: Set[str] = set()
        self.archived: bool = False

        # Project state, loaded lazily, None if not loaded
        self._state: Optional[ProjectState] = None

        self.meta = Meta()
        self.log = Log(self)
        self.body = Body(self)

    def set_locale(self) -> None:
        """
        Set the current locale to the one specified in the project header
        """
        set_locale(self.meta.lang)

    @property
    def state(self) -> ProjectState:
        if not self._state:
            self._state = ProjectState(self)
        return self._state

    @property
    def name(self) -> str:
        name = self.meta.name or self.default_name
        if not self.archived:
            return name

        since, until = self.formal_period
        if until:
            return f"{name}-{until:%Y-%m-%d}"
        elif since:
            return f"{name}-{since:%Y-%m-%d}"
        else:
            return name

    @property
    def path(self) -> str:
        return self.meta.path or self.default_path

    @property
    def mtime(self) -> float:
        """
        Returh the modification time of the .egt file
        """
        return os.path.getmtime(self.abspath)

    @property
    def tags(self) -> Set[str]:
        return self.default_tags | self.meta.tags

    @classmethod
    def from_file(self, abspath: str, fd: Optional[TextIO] = None, config=None):
        # Default values, can be overridden by file metadata
        p = Project(abspath, config=config)
        # Load the actual data
        p.load(fd=fd)
        return p

    @classmethod
    def mock(self, abspath: str, name: Optional[str] = None, path: Optional[str] = None, tags=None, config=None):
        p = Project(abspath, config=config if config is not None else Config())
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
        first_line = lines.peek()

        if first_line is None:
            return
        elif self.log.is_start_line(first_line):
            log.debug("%s:%d: parsing log", lines.fname, lines.lineno)
            self.log.parse(lines, lang=self.meta.lang)
            lines.skip_empty_lines()

        # Parse body
        log.debug("%s:%d: parsing body", lines.fname, lines.lineno)
        self.body.parse(lines)

        # Allow to group archived projects with the same name.
        # Compute it separately to skip the archieve name mangling performed by
        # the name property on archived project names
        self.group = self.meta.name or self.default_name

        # Quick access to 'archive' meta attribute
        if self.meta.archived:
            self.archived = True

    def print(self, out: TextIO, today: Optional[datetime.date] = None):
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

    def save(self, today: Optional[datetime.date] = None):
        """
        Save over the original source file
        """
        with atomic_writer(self.abspath, "wt") as fd:
            self.print(cast(TextIO, fd), today)

    @property
    def last_updated(self) -> Optional[datetime.datetime]:
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
    def elapsed(self) -> int:
        mins = 0
        for entry in self.log.entries:
            mins += entry.duration
        return mins

    @property
    def formatted_elapsed(self) -> str:
        return format_duration(self.elapsed)

    @property
    def formatted_tags(self) -> str:
        return ", ".join(sorted(self.tags))

    @property
    def formal_period(self) -> Tuple[datetime.date, datetime.date]:
        """
        Compute the begin and end dates for this project.

        If Start-date and End-date are provided in the metadata, return those.
        Else infer them from the first or last log entries.
        """
        if (date := self.meta.start_date):
            since = date
        elif (e := self.log.first_entry) is not None:
            since = e.begin.date()
        else:
            since = today()

        if (date := self.meta.end_date):
            until = date
        elif (e := self.log.last_entry) is not None:
            until = e.until.date() if e.until is not None else today()
        else:
            until = today()

        return since, until

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

    def _create_archive(self, pathname: str, start: datetime.date, end: datetime.date) -> Optional["Project"]:
        pathname = os.path.expanduser(pathname)
        if os.path.exists(pathname):
            log.warn("%s not archived: %s already exists", self.name, pathname)
            return None

        # Select the log entries
        entries = self.log.detach_entries(start, end)
        if not entries:
            return None

        archived = Project(pathname, config=self.config)
        archived.meta = self.meta.copy()
        archived.log._entries = entries
        archived.meta.set("archived", "yes")
        archived.meta.set_durations(archived.log.durations())
        archived.archived = True
        with open(pathname, "wt") as out:
            archived.print(out)
        return archived

    def archive_month(self, archive_dir: str, month: datetime.date) -> Tuple[datetime.date, Optional["Project"]]:
        """
        Write log entries for the given month to an archive file
        """
        # Generate the target file name
        if "%" in archive_dir:
            archive_dir = month.strftime(archive_dir)
        pathname = os.path.join(archive_dir, f"{month:%Y%m}-{self.name}.egt")

        next_month = (month + datetime.timedelta(days=40)).replace(day=1)
        return next_month, self._create_archive(pathname, month, next_month)

    def archive_range(
        self, archive_dir: str, start: datetime.date, end: datetime.date
    ) -> Tuple[datetime.date, Optional["Project"]]:
        """
        Write log entries for the given range to an archive file
        """
        # Generate the target file name
        if "%" in archive_dir:
            raise RuntimeError("Placeholders in archive-dir not supported for single-file archives")
        last_day = end - datetime.timedelta(days=1)
        pathname = os.path.join(
            archive_dir, f"{self.name}_{start:%Y-%m-%d}_to_{last_day:%Y-%m-%d}.egt"
        )

        return end, self._create_archive(pathname, start, end)

    def archive(self, cutoff: datetime.date, report_fd: Optional[TextIO], save=True, combined=True) -> List["Project"]:
        """
        Archive contents until the given cutoff date (excluded).

        Returns the list of archive file names written.
        """
        archive_dir = self.meta.get("archive-dir", None)
        if archive_dir is None:
            log.info("%s not archived: archive-dir not found in header", self.name)
            return []

        archived = []
        first_entry = self.log.first_entry
        if first_entry is None:
            log.info("%s not archived: log is empty", self.name)
        else:
            # Get the datetime of the first Entry in the log
            date = first_entry.begin.date()

            # Iterate until cutoff
            while date < cutoff:
                if combined:
                    date, arc = self.archive_range(archive_dir, date.replace(day=1), cutoff)
                else:
                    date, arc = self.archive_month(archive_dir, date)
                if arc is not None:
                    archived.append(arc)
                    if report_fd is not None:
                        arc.print(report_fd)

        # Save without the archived enties
        if save:
            self.save()

        return archived

    def sync_tasks(self, modify_state=True):
        """
        Sync project with taskwarrior
        """
        self.body.tasks.sync_tasks(modify_state=modify_state)

    def annotate(self, today: Optional[datetime.date] = None):
        """
        Fill in fields, resolve commands, and perform all pending actions
        embedded in the project
        """
        self.sync_tasks(modify_state=True)
        self.log.sync(today=today)
        if self.meta.has("total"):
            self.meta.set_durations(self.log.durations())

    @classmethod
    def has_project(cls, abspath):
        return os.path.exists(abspath)
