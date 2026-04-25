import contextlib
import datetime as dt
import json
import logging
import os.path
import subprocess
import sys
import tarfile
from collections.abc import Iterator
from functools import cached_property
from pathlib import Path
from typing import IO, Any, Self, cast, Generator

from .body import Body
from .config import Config
from .lang import set_locale
from .log import Log
from .meta import Meta
from .utils import atomic_writer, format_duration, stream_output, today

log = logging.getLogger(__name__)


class ProjectState:
    """
    Project information cached in the state directory
    """

    def __init__(self, project: "Project"):
        statedir = project.statedir
        # TODO: ensure name does not contain '/'
        self.abspath = statedir / f"project-{project.name}.json"
        self._state: dict | None = None

    def get(self, name: str) -> Any:
        if self._state is None:
            self._state = self._load()
        return self._state.get(name, None)

    def set(self, name: str, val: Any) -> None:
        if self._state is None:
            self._state = self._load()
        self._state[name] = val
        self._save()

    def _load(self) -> dict[str, Any]:
        if not self.abspath.exists():
            return {}
        with self.abspath.open("r") as fd:
            state = json.load(fd)
            if not isinstance(state, dict):
                log.error("%s: JSON data is not a dict: ignoring", self.abspath)
                return {}
            return state

    def _save(self) -> None:
        with atomic_writer(self.abspath, "wt") as fd:
            json.dump(self._state, fd, indent=1)


class Project:
    """
    A parsed ``.egt`` file.

    The file contains:

    * Metadata (meta.Meta)
    * A time-based log (log.Log)
    * A free-text body (body.Body)
    """

    def __init__(
        self, path: Path, *, config: Config, statedir: Path | None = None
    ) -> None:
        """
        Instantiate a project.

        :param path: Path to the .egt file
        :param config: egt configuration
        :param statedir: Directory where cached project state is saved. If
          None, the default location is used.
        """
        #: Egt configuration
        self.config = config
        #: Directory where cached project state is saved
        self.statedir = statedir or self.config.state_dir
        #: Path to the .egt file
        self.abspath = path
        #: Project tags
        self.tags: set[str] = self._default_tags()
        #: If True, the project is archived
        self.archived: bool = False

        self.meta = Meta()
        self.log = Log(self)
        self.body = Body(self)

    def _default_tags(self) -> set[str]:
        """Guess tags from the project pathname."""
        tags: set[str] = set()
        str_path = self.abspath.as_posix()
        for tag, regexp in self.config.autotag_rules:
            if regexp.search(str_path):
                tags.add(tag)
        return tags

    @contextlib.contextmanager
    def set_locale(self) -> Generator[None]:
        """
        Set the current locale to the one specified in the project header
        """
        with set_locale(self.meta.lang):
            yield

    @cached_property
    def state(self) -> ProjectState:
        """Cached project information."""
        return ProjectState(self)

    @cached_property
    def base_name(self) -> str:
        """
        Return the base name of the project.

        This is the project name without an archived suffix.
        """
        if self.meta.name is not None:
            return self.meta.name

        if self.abspath.name == ".egt":
            return self.abspath.parent.name
        else:
            return self.abspath.stem

    @property
    def name(self) -> str:
        """Project name."""
        if not self.archived:
            return self.base_name

        since, until = self.formal_period
        if until:
            return f"{self.base_name}-{until:%Y-%m-%d}"
        elif since:
            return f"{self.base_name}-{since:%Y-%m-%d}"
        else:
            return self.base_name

    @cached_property
    def path(self) -> Path:
        """Return the project directory."""
        return self.meta.path or self.abspath.parent

    @property
    def mtime(self) -> float:
        """
        Returh the modification time of the .egt file
        """
        return self.abspath.stat().st_mtime

    @classmethod
    def from_file(
        cls, path: Path, *, fd: IO[str] | None = None, config: Config
    ) -> Self:
        """
        Load a project from a ``.egt`` file.

        :param path: path to the ``.egt`` file.
        :param fd: file descriptor to load the ``.egt`` file from. If missing,
          ``path`` is opened.
        :param config: egt configuration
        """
        # Default values, can be overridden by file metadata
        p = cls(path, config=config)
        # Load the actual data
        p.load(fd=fd)
        return p

    def load(self, fd: IO[str] | None = None) -> None:
        """
        Load the project from file.

        :param fd: file descriptor to load the ``.egt`` file from. If missing,
          ``self.abspath`` is opened.
        """
        from .parse import Lines

        lines = Lines(self.abspath, fd=fd)

        try:
            # Parse optional metadata

            # If it starts with a log, there is no metadata: stop
            # If the first line doesn't look like a header, stop
            if (line := lines.peek()) is None:
                return
            if not Log.is_start_line(line) and Meta.is_start_line(line):
                log.debug("%s:%d: parsing metadata", lines.path, lines.lineno)
                self.meta.parse(lines)

            lines.skip_empty_lines()

            # Parse log entries
            if (line := lines.peek()) is None:
                return
            elif self.log.is_start_line(line):
                log.debug("%s:%d: parsing log", lines.path, lines.lineno)
                self.log.parse(lines, lang=self.meta.lang)
                lines.skip_empty_lines()

            # Parse body
            log.debug("%s:%d: parsing body", lines.path, lines.lineno)
            self.body.parse(lines)
        finally:
            # Allow to group archived projects with the same name.
            # Compute it separately to skip the archieve name mangling
            # performed by the name property on archived project names
            self.group = self.base_name

            # Add tags from project metadata
            self.tags.update(self.meta.tags)

            # Quick access to 'archive' meta attribute
            if self.meta.archived:
                self.archived = True

    def print(self, out: IO[str], *, today: dt.date | None = None) -> None:
        """
        Serialize the whole project as a project file to the given file
        descriptor.

        :param out: output file descriptor
        :param today: if present, override today's date
        """
        from . import utils

        if today is None:
            today = utils.today()

        if self.meta.print(out):
            print(file=out)

        if self.log.print(out, today=today):
            print(file=out)

        self.body.print(out)

    def save(self, today: dt.date | None = None) -> None:
        """
        Save over the original source file
        """
        with atomic_writer(self.abspath, "wt") as fd:
            self.print(cast(IO[str], fd), today=today)

    @property
    def last_updated(self) -> dt.datetime | None:
        """
        Datetime when this project was last updated
        """
        last = self.log.last_entry
        if last is None:
            return None
        if last.until:
            return last.until
        return dt.datetime.now()

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
    def formal_period(self) -> tuple[dt.date, dt.date]:
        """
        Compute the begin and end dates for this project.

        If Start-date and End-date are provided in the metadata, return those.
        Else infer them from the first or last log entries.
        """
        if date := self.meta.start_date:
            since = date
        elif (e := self.log.first_entry) is not None:
            since = e.begin.date()
        else:
            since = today()

        if date := self.meta.end_date:
            until = date
        elif (e := self.log.last_entry) is not None:
            until = e.until.date() if e.until is not None else today()
        else:
            until = today()

        return since, until

    def spawn_terminal(self, with_editor: bool = False) -> None:
        from .system import run_work_session

        run_work_session(self, with_editor)

    def run_editor(self) -> None:
        from .system import run_editor

        run_editor(self)

    def run_grep(self, args: list[str]) -> None:
        for gd in self.gitdirs():
            cwd = gd.parent.absolute()
            cmd = ["git", "grep"] + args
            log.info("%s: git grep %s", cwd, " ".join(cmd))
            p = subprocess.Popen(
                cmd,
                cwd=cwd.as_posix(),
                close_fds=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for ltype, line in stream_output(p):
                if ltype == "stdout":
                    print(f"{self.name}:{line}", file=sys.stdout)
                elif ltype == "stderr":
                    print(f"{self.name}:{line}", file=sys.stderr)

    def gitdirs(
        self, depth: int = 2, root: Path | None = None
    ) -> Iterator[Path]:
        """
        Find all .git directories below the project path
        """
        # Default to self.path
        if root is None:
            root = self.path

        # Check the current dir
        cand = root / ".git"
        if cand.is_dir():
            yield cand

        # Recurse into subdirs if we still have some way to go
        if depth > 1:
            for sub in root.iterdir():
                if sub.name.startswith("."):
                    continue
                if sub.is_dir():
                    yield from self.gitdirs(depth - 1, sub)

    def backup(self, tarout: tarfile.TarFile) -> None:
        backup_paths = [
            x.strip() for x in self.meta.get("backup", "").split("\n")
        ]

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

    def _create_archive(
        self, path: Path, start: dt.date, end: dt.date
    ) -> "Project | None":
        path = path.expanduser()
        if path.exists():
            log.warn("%s not archived: %s already exists", self.name, path)
            return None

        # Select the log entries
        entries = self.log.detach_entries(start, end)
        if not entries:
            return None

        archived = Project(path, config=self.config)
        archived.meta = self.meta.copy()
        archived.log._entries = entries
        archived.meta.set("archived", "yes")
        archived.meta.set_durations(archived.log.durations())
        archived.archived = True
        with path.open("w") as out:
            archived.print(out)
        return archived

    def archive_month(
        self, archive_dir: str, month: dt.date
    ) -> tuple[dt.date, "Project | None"]:
        """
        Write log entries for the given month to an archive file
        """
        # Generate the target file name
        if "%" in archive_dir:
            archive_dir = month.strftime(archive_dir)
        pathname = Path(archive_dir) / f"{month:%Y%m}-{self.name}.egt"

        next_month = (month + dt.timedelta(days=40)).replace(day=1)
        return next_month, self._create_archive(pathname, month, next_month)

    def archive_range(
        self, archive_dir: str, start: dt.date, end: dt.date
    ) -> tuple[dt.date, "Project | None"]:
        """
        Write log entries for the given range to an archive file
        """
        # Generate the target file name
        if "%" in archive_dir:
            raise RuntimeError(
                "Placeholders in archive-dir not supported for single-file archives"
            )
        last_day = end - dt.timedelta(days=1)
        pathname = (
            Path(archive_dir)
            / f"{self.name}_{start:%Y-%m-%d}_to_{last_day:%Y-%m-%d}.egt"
        )

        return end, self._create_archive(pathname, start, end)

    def archive(
        self,
        cutoff: dt.date,
        report_fd: IO[str] | None,
        save: bool = True,
        combined: bool = True,
    ) -> list["Project"]:
        """
        Archive contents until the given cutoff date (excluded).

        Returns the list of archive file names written.
        """
        archive_dir = self.meta.get("archive-dir", None)
        if archive_dir is None:
            log.info(
                "%s not archived: archive-dir not found in header", self.name
            )
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
                    date, arc = self.archive_range(
                        archive_dir, date.replace(day=1), cutoff
                    )
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

    def sync_tasks(self, modify_state: bool = True) -> None:
        """
        Sync project with taskwarrior
        """
        if self.body.tasks.has_taskwarrior():
            self.body.tasks.sync_tasks(modify_state=modify_state)

    def annotate(self, today: dt.date | None = None) -> None:
        """
        Fill in fields, resolve commands, and perform all pending actions
        embedded in the project
        """
        self.sync_tasks(modify_state=True)
        self.log.sync(today=today)
        if self.meta.has("total"):
            self.meta.set_durations(self.log.durations())

    @classmethod
    def has_project(cls, path: Path) -> bool:
        return path.exists()
