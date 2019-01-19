from typing import List, Dict
from .utils import atomic_writer
from .project import Project
from .scan import scan
from xdg import BaseDirectory
import os.path
import json
import logging

log = logging.getLogger(__name__)


class State:
    """
    Cached information about known projects.
    """

    def __init__(self):
        # Map project names to ProjectInfo objects
        self.projects = {}

    def load(self, statedir: str = None) -> None:
        if statedir is None:
            statedir = self.get_state_dir()

        statefile = os.path.join(statedir, "state.json")
        if os.path.exists(statefile):
            # Load state from JSON file
            with open(statefile, "rt") as fd:
                state = json.load(fd)
            self.projects = state["projects"]
            return

        # TODO: remove support for legacy format
        statefile = os.path.join(statedir, "state")
        if os.path.exists(statefile):
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
    def rescan(cls, dirs: List[str], statedir: str = None) -> None:
        """
        Rebuild the state looking for files in the given directories.

        If statedir is None, the state is saved in the default state
        directory. If it is not None, it is the directory in which state is to
        be saved.
        """
        if statedir is None:
            statedir = cls.get_state_dir()

        # Read and detect duplicates
        projects: Dict[str, dict] = {}
        for dirname in dirs:
            for fname in scan(dirname):
                try:
                    p = Project.from_file(fname)
                except Exception as e:
                    log.exception("%s: failed to parse: %s", fname, str(e))
                    continue
                if p.name in projects:
                    log.warn("%s: project %s already exists in %s: skipping", fname, p.name, p.abspath)
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
        statefile = os.path.join(statedir, "state.json")
        with atomic_writer(statefile, "wt") as fd:
            json.dump({
                "projects": projects
            }, fd, indent=1)

        # Clean up old version of state file
        old_statefile = os.path.join(statedir, "state")
        if os.path.exists(old_statefile):
            log.warn("%s: legacy state file removed", old_statefile)
            os.unlink(old_statefile)

        # TODO: scan statedir removing project-$NAME.json files for all
        # projects that disappeared.

        log.debug("%s: new state written", statefile)

    @classmethod
    def get_state_dir(cls) -> str:
        return BaseDirectory.save_data_path('egt')
