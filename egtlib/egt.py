import datetime
import logging
import re
import sys
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Set, TextIO

import taskw

from .project import Project
from .state import State
from .utils import intervals_intersect
from .config import Config

log = logging.getLogger(__name__)


class WeeklyReport(object):
    def __init__(self):
        self.projs: List["Project"] = []

    def add(self, p: Project) -> None:
        self.projs.append(p)

    def report(self, end: datetime.date = None, days: int = 7) -> Dict[str, Any]:
        if end is None:
            d_until = datetime.date.today()
        else:
            d_until = end
        d_begin = d_until - datetime.timedelta(days=days)

        res: Dict[str, Any] = dict(
            begin=d_begin,
            until=d_until,
        )

        log = []
        count = 0
        mins = 0
        for p in self.projs:
            for e in p.log.entries:
                if intervals_intersect(
                    e.begin.date(), e.until.date() if e.until else datetime.date.today(), d_begin, d_until
                ):
                    log.append((e, p))
                    count += 1
                    mins += e.duration

        res.update(
            count=count,
            hours=mins / 60,
            hours_per_day=mins / 60 / days,
            hours_per_workday=mins / 60 / 5,  # FIXME: properly compute work days in period
            log=log,
        )

        return res


class ProjectFilter:
    """
    Filter for projects, based on a list of keywords.

    A keyword can be:
        +tag  matches projects that have this tag
        -tag  matches projects that do not have this tag
        name  matches projects with this name
          NN  matches the project of the taskwarrior task with ID NN
           _  matches the project of the last taskwarrior task completed today
     pattern  if only one keyword: fnmatch pattern to match against project names

    A project matches the filter if its name is explicitly listed. If it is
    not, it matches if its tag set contains all the +tag tags, and does not
    contain any of the -tag tags.
    """

    def __init__(self, args: List[str]):
        self._tw: Optional[taskw.TaskWarrior] = None
        self.args = args
        self.names: Set[str] = set()
        self.tags_wanted: Set[str] = set()
        self.tags_unwanted: Set[str] = set()
        self.bad_filter: bool = False

        for f in args:
            if f == "_":
                tasks = self.tw.filter_tasks({"status": "completed", "end": datetime.date.today()})
                try:
                    self.names.add(tasks[0]["project"])
                except (IndexError, KeyError):
                    self.bad_filter = True
            elif f.startswith("+"):
                self.tags_wanted.add(f[1:])
            elif f.startswith("-"):
                self.tags_unwanted.add(f[1:])
            else:
                if f.isdecimal():
                    task = self.tw.get_task(id=int(f))
                    try:
                        self.names.add(task[1]["project"])
                    except (IndexError, KeyError):
                        self.bad_filter = True
                else:
                    self.names.add(f)
        if self.bad_filter:
            log.warn("bad filter no projects will match")

    @property
    def tw(self) -> taskw.TaskWarrior:
        if self._tw is None:
            self._tw = taskw.TaskWarrior(marshal=True)
        return self._tw

    def matches(self, project: Project) -> bool:
        """
        Check if this project matches the filter.
        """
        # do not match if the filter was bad
        # (prevents accidentlly running on all projects)
        if self.bad_filter:
            return False
        if self.names and project.name not in self.names:
            # project-name is not mached exactly
            exact_match = False
            # check if a pattern is matches
            pattern_match = False
            if len(self.names) == 1:
                import fnmatch

                (pattern,) = self.names
                pattern_match = fnmatch.fnmatch(project.name, pattern)
            if not exact_match and not pattern_match:
                return False
        if self.tags_wanted and self.tags_wanted.isdisjoint(project.tags):
            return False
        if self.tags_unwanted and not self.tags_unwanted.isdisjoint(project.tags):
            return False
        return True


class Egt:
    """
    Collection of parsed .egt files as Project objects
    """

    def __init__(
        self,
        config: Config,
        filter: List[str] = [],
        show_archived: bool = False,
        statedir: Path | None = None,
    ):
        self.config = config
        self.state = State()
        self.state.load(statedir)
        self.show_archived = show_archived
        self.filter = ProjectFilter(filter)
        # Dict mapping project names to Project objects.
        # It is built lazily when needed, and is None when not yet built.
        self._projects: Optional[Dict[str, Project]] = None

    def load_project(self, path: Path, project_fd: Optional[TextIO] = None) -> Optional[Project]:
        """
        Return a Project object given its file name.

        Returns None if the file does not exist or no suitable project could be
        created from that file.
        """
        from .project import Project

        # TODO: remove after Path migration
        assert isinstance(path, Path)

        if not Project.has_project(path):
            log.warning("project %s has disappeared: please rerun scan", path)
            return None
        proj = Project.from_file(path, fd=project_fd, config=self.config)
        if not self.show_archived and proj.archived:
            return None
        proj.default_tags.update(self._default_tags(path))
        if not self.filter.matches(proj):
            return None
        return proj

    def _load_projects(self) -> Dict[str, Project]:
        projs = {}
        for name, info in self.state.projects.items():
            proj = self.load_project(Path(info["fname"]))
            if proj is None:
                continue
            projs[proj.name] = proj
        return projs

    def _default_tags(self, abspath: Path) -> Set[str]:
        """
        Guess tags from the project file pathname
        """
        tags: Set[str] = set()
        str_path = abspath.as_posix()
        for tag, regexp in self.config.autotag_rules:
            if re.search(regexp, str_path):
                tags.add(tag)
        return tags

    @property
    def loaded_projects(self) -> Dict[str, Project]:
        if self._projects is None:
            self._projects = self._load_projects()
        return self._projects

    @property
    def projects(self) -> List[Project]:
        return sorted(self.loaded_projects.values(), key=lambda p: p.name)

    @property
    def project_names(self):
        return sorted(self.loaded_projects.keys())

    @property
    def all_tags(self) -> List[str]:
        res: Set[str] = set()
        for p in self.projects:
            res.update(p.tags)
        return sorted(res)

    def project(self, name: str, project_fd: Optional[TextIO] = None) -> Optional[Project]:
        """
        Return a Project by its name
        """
        # Try loading from _projects, if we have already loaded it
        if self._projects is not None:
            return self._projects.get(name, None)

        # Otherwise, look it up on state and load it on the fly
        info = self.state.projects.get(name, None)
        if info is None:
            return None
        return self.load_project(info["fname"], project_fd=project_fd)

    def weekrpt(
        self, tags: List[str] = None, end: datetime.date = None, days: int = 7, projs: List[Project] = None
    ) -> Dict[str, Any]:
        rep = WeeklyReport()
        if projs:
            for p in projs:
                rep.add(p)
        else:
            for p in self.projects:
                if not tags or p.tags.issuperset(tags):
                    rep.add(p)
        return rep.report(end, days)

    def backup(self, out: BinaryIO = sys.stdout.buffer) -> None:
        import tarfile

        tarout = tarfile.open(None, "w|", fileobj=out)
        for p in self.projects:
            p.backup(tarout)
        tarout.close()
