from __future__ import absolute_import
from .utils import atomic_writer
from ConfigParser import RawConfigParser as ConfigParser
from .project import Project

class State(object):
    def __init__(self):
        self.clear()

    def clear(self):
        self.projects = {}

    def load(self):
        self.clear()

        cp = ConfigParser()
        cp.read(["egt.conf"])
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
        with atomic_writer("egt.conf") as fd:
            cp.write(fd)
