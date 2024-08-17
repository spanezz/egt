from __future__ import annotations

import json
import logging
from pathlib import Path

from xdg import BaseDirectory

from .project import Project
from .scan import scan
from .utils import atomic_writer
from .config import Config

log = logging.getLogger(__name__)


class PathEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return obj.as_posix()
        return json.JSONEncoder.default(self, obj)


class State:
    """
    Cached information about known projects.
    """

    def __init__(self):
        # Map project names to ProjectInfo objects
        self.projects = {}

    def load(self, statedir: Path | None = None) -> None:
        if statedir is None:
            statedir = self.get_state_dir()

        statefile = statedir / "state.json"
        if statefile.exists():
            # Load state from JSON file
            with statefile.open("r") as fd:
                state = json.load(fd)
            self.projects = state["projects"]
            return

        # TODO: remove support for legacy format
        statefile = statedir / "state"
        if statefile.exists():
            # Load state from legacy .ini file
            from configparser import RawConfigParser

            cp = RawConfigParser()
            cp.read([statefile])
            for secname in cp.sections():
                if secname.startswith("proj "):
                    name = secname.split(None, 1)[1]
                    fname = cp.get(secname, "fname")
                    self.projects[name] = {"fname": fname}
            return

    @classmethod
    def rescan(cls, dirs: list[Path], *, config: Config, statedir: Path | None = None) -> None:
        """
        Rebuild the state looking for files in the given directories.

        If statedir is None, the state is saved in the default state
        directory. If it is not None, it is the directory in which state is to
        be saved.
        """
        if statedir is None:
            statedir = cls.get_state_dir()

        # Read and detect duplicates
        projects: dict[str, dict] = {}
        for dirname in dirs:
            for fname in scan(dirname):
                try:
                    p = Project.from_file(fname, config=config)
                except Exception as e:
                    log.exception("%s: failed to parse: %s", fname, str(e))
                    continue
                if p.name in projects:
                    log.warn("%s: project %s already exists in %s: skipping", fname, p.name, projects[p.name]["fname"])
                else:
                    projects[p.name] = {"fname": p.abspath}

        # Log the difference with the old info
        # old_projects = set(self.projects.keys())
        # for name, p in new_projects.items():
        #     old_projects.discard(name)
        #     op = self.projects.get(name, None)
        #     if op is None:
        #         log.info("add %s: %s", name, p["fname"])
        #     elif op["fname"] != p["fname"]:
        #         log.info("mv %s: %s -> %s", name, p["fname"], p["fname"])
        #     else:
        #         log.info("hit %s: %s", name, p["fname"])
        # for name in old_projects:
        #     log.info("rm %s", name)

        # Commit the new project set
        statefile = statedir / "state.json"
        with atomic_writer(statefile, "wt") as fd:
            json.dump({"projects": projects}, fd, cls=PathEncoder, indent=1)

        # Clean up old version of state file
        old_statefile = statedir / "state"
        if old_statefile.exists():
            log.warn("%s: legacy state file removed", old_statefile)
            old_statefile.unlink()

        # TODO: scan statedir removing project-$NAME.json files for all
        # projects that disappeared.

        log.debug("%s: new state written", statefile)

    @classmethod
    def get_state_dir(cls) -> Path:
        return Path(BaseDirectory.save_data_path("egt"))
