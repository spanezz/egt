import datetime as dt
import logging
import warnings
from functools import cached_property
from pathlib import Path

with warnings.catch_warnings(action="ignore"):
    import taskw

from .config import Config
from .project import Project
from .state import State
from .utils import contain_taskwarrior_noise

log = logging.getLogger(__name__)


class ProjectFilter:
    """
    Filter for projects, based on a list of keywords.

    A keyword can be:
        +tag  matches projects that have this tag
        -tag  matches projects that do not have this tag
        name  matches projects with this name
          NN  matches the project of the taskwarrior task with ID NN
           _  matches the project of the last taskwarrior task completed today
     pattern  if only one keyword: fnmatch pattern to match against project
              names

    A project matches the filter if its name is explicitly listed. If it is
    not, it matches if its tag set contains all the +tag tags, and does not
    contain any of the -tag tags.
    """

    def __init__(self, args: list[str]):
        self._tw: taskw.TaskWarrior | None = None
        self.args = args
        self.names: set[str] = set()
        self.tags_wanted: set[str] = set()
        self.tags_unwanted: set[str] = set()
        self.bad_filter: bool = False

        for f in args:
            if f == "_":
                with contain_taskwarrior_noise():
                    tasks = sorted(
                        self.tw.filter_tasks(
                            {
                                "status": "completed",
                                "end": dt.date.today(),
                            }
                        ),
                        key=lambda t: t["end"],
                        reverse=True,
                    )
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
                    with contain_taskwarrior_noise():
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
        if self.tags_unwanted and not self.tags_unwanted.isdisjoint(
            project.tags
        ):
            return False
        return True


class Egt:
    """
    Database of Project objects loaded from ``.egt`` files.
    """

    def __init__(
        self,
        config: Config,
        filter: list[str] = [],
        show_archived: bool = False,
        statedir: Path | None = None,
    ) -> None:
        """
        Initialize the Project database.

        :param config: egt configuration
        :param filter: list of filter arguments
        :param show_archived: set to True if archived project should be used
        :param statedir: Directory where cached project state is saved. If
          None, the default location is used.
        """
        #: egt configuration
        self.config = config
        #: Cached information about known projects
        self.state = State(self.config)
        self.state.load(statedir)
        #: If True, archived projects are not ignored by default
        self.show_archived = show_archived
        #: Current project filter
        self.filter = ProjectFilter(filter)
        #: Projects indexed by project name
        self.by_name: dict[str, Project] = {}
        self._load()

    def _load(self) -> None:
        """Fill self.by_name."""
        for name, info in self.state.projects.items():
            path = Path(info["fname"])
            if not Project.has_project(path):
                log.warning(
                    "project %s has disappeared: please rerun scan", path
                )
                continue
            proj = Project.from_file(path, config=self.config)
            if not self.show_archived and proj.archived:
                continue
            if not self.filter.matches(proj):
                continue
            self.by_name[proj.name] = proj

    def get(self, name: str) -> Project | None:
        """Return a project by name."""
        return self.by_name.get(name)

    @cached_property
    def projects(self) -> list[Project]:
        """List of projects sorted by project name."""
        return sorted(self.by_name.values(), key=lambda p: p.name)

    @cached_property
    def project_names(self) -> list[str]:
        """Sorted list of project names."""
        return sorted(self.by_name.keys())

    @property
    def all_tags(self) -> list[str]:
        """Sorted list of all known project tags."""
        res: set[str] = set()
        for p in self.projects:
            res.update(p.tags)
        return sorted(res)
