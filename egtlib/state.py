from .utils import atomic_writer
from .project import Project
from .scan import scan
from xdg import BaseDirectory
from collections import namedtuple
import os.path
import logging

log = logging.getLogger(__name__)

class State:
    """
    Cached information about known projects.
    """

    def __init__(self, config):
        self.config = config
        # Map project names to ProjectInfo objects
        self.projects = {}
        # Main state directory
        self.state_dir = BaseDirectory.save_data_path('egt')

    def load(self):
        statefile = os.path.join(self.state_dir, "state.json")
        if os.path.exists(statefile):
            # Load state from JSON file
            import json
            with open(statefile, "rt") as fd:
                state = json.load(fd)
            self.projects = state["projects"]
            return

        statefile = os.path.join(self.state_dir, "state")
        if os.path.exists(statefile):
            # Load state from legacy .ini file
            from configparser import RawConfigParser
            cp = RawConfigParser()
            cp.read([statefile])
            for secname in cp.sections():
                if secname.startswith("proj "):
                    name = secname.split(None, 1)[1]
                    fname = cp.get(secname, "fname")
                    self.projects[name] = { "fname": fname }
            return

    def save(self):
        statefile = os.path.join(self.state_dir, "state.json")
        with atomic_writer(statefile, "wt") as fd:
            import json
            json.dump({
                "projects": self.projects
            }, fd, indent=1)

        # Clean up old version of state file
        old_statefile = os.path.join(self.state_dir, "state")
        if os.path.exists(old_statefile):
            os.unlink(old_statefile)
        log.debug("updated state in %s", statefile)

    def rescan(self, dirs):
        # Read and detect duplicates
        new_projects = dict()
        for dirname in dirs:
            for fname in scan(dirname):
                try:
                    p = Project.from_file(self.config, fname)
                except Exception as e:
                    log.exception("%s: failed to parse: %s", fname, str(e))
                    continue
                if p.name in new_projects:
                    log.warn("%s: project %s already exists in %s: skipping", fname, p.name, p.abspath)
                else:
                    new_projects[p.name] = { "fname": p.abspath }

        # Log the difference with the old info
        old_projects = set(self.projects.keys())
        for name, p in new_projects.items():
            old_projects.discard(name)
            op = self.projects.get(name, None)
            if op is None:
                log.info("add %s: %s", name, p["fname"])
            elif op["fname"] != p["fname"]:
                log.info("mv %s: %s -> %s", name, p["fname"], p["fname"])
            else:
                log.info("hit %s: %s", name, p["fname"])
        for name in old_projects:
            log.info("rm %s", name)

        # Commit the new project set
        self.projects = new_projects
        self.save()
