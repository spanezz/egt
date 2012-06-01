from __future__ import absolute_import
from .utils import atomic_writer
from .project import Project
from ConfigParser import RawConfigParser as ConfigParser
from xdg import BaseDirectory
import os.path
import logging

log = logging.getLogger(__name__)

class State(object):
    def __init__(self):
        self.clear()

    def clear(self):
        self.projects = {}

    def load(self):
        self.clear()

        # Build a list of standard path locations
        paths = []
        for path in BaseDirectory.load_data_paths("egt"):
            paths.append(os.path.join(path, "state"))

        cp = ConfigParser()
        cp.read(paths)
        for secname in cp.sections():
            if secname.startswith("dir "):
                p = secname.split(None, 1)[1]
                proj = Project(p)
                proj.from_cp(cp)
                self.projects[p] = proj

    def save(self):
        cp = ConfigParser()
        for k, v in self.projects.iteritems():
            v.to_cp(cp)
        outdir = BaseDirectory.save_data_path('egt')
        cfgfname = os.path.join(outdir, "state")
        with atomic_writer(cfgfname) as fd:
            cp.write(fd)
        log.debug("updated state in %s", cfgfname)
