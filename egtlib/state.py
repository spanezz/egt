from .utils import atomic_writer
from .project import Project
from .scan import scan
from configparser import RawConfigParser
from xdg import BaseDirectory
from collections import namedtuple
import os.path
import logging

log = logging.getLogger(__name__)

ProjectInfo = namedtuple("ProjectInfo", ["fname"])


class State:
    """
    Cached information about known projects.
    """

    def __init__(self, config):
        self.config = config
        # Map project names to ProjectInfo objects
        self.projects = {}

    def load(self):
        # Build a list of standard path locations
        paths = []
        for path in BaseDirectory.load_data_paths("egt"):
            paths.append(os.path.join(path, "state"))

        cp = RawConfigParser()
        cp.read(paths)
        for secname in cp.sections():
            if secname.startswith("proj "):
                name = secname.split(None, 1)[1]
                fname = cp.get(secname, "fname")
                self.projects[name] = ProjectInfo(fname=fname)

    def save(self):
        cp = RawConfigParser()
        for name, p in self.projects.items():
            secname = "proj %s" % name
            cp.add_section(secname)
            cp.set(secname, "fname", p.fname)

        outdir = BaseDirectory.save_data_path('egt')
        cfgfname = os.path.join(outdir, "state")
        with atomic_writer(cfgfname, "wt") as fd:
            cp.write(fd)
        log.debug("updated state in %s", cfgfname)

    def rescan(self, dirs):
        # Read and detect duplicates
        new_projects = dict()
        for dirname in dirs:
            for fname in scan(dirname):
                try:
                    p = Project.from_file(self.config, fname)
                except Exception as e:
                    log.warn("%s: failed to parse: %s", fname, str(e))
                    continue
                if p.name in new_projects:
                    log.warn("%s: project %s already exists in %s: skipping", fname, p.name, p.abspath)
                else:
                    new_projects[p.name] = ProjectInfo(fname=p.abspath)

        # Log the difference with the old info
        old_projects = set(self.projects.keys())
        for name, p in new_projects.items():
            old_projects.discard(name)
            op = self.projects.get(name, None)
            if op is None:
                log.info("add %s: %s", name, p.fname)
            elif op.fname != p.fname:
                log.info("mv %s: %s -> %s", name, p.fname, p.fname)
            else:
                log.info("hit %s: %s", name, p.fname)
        for name in old_projects:
            log.info("rm %s", name)

        # Commit the new project set
        self.projects = new_projects
        self.save()
