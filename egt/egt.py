from __future__ import absolute_import
import os
import os.path
import logging
import itertools
from .state import State
from .project import Project

log = logging.getLogger(__name__)

class Egt(object):
    def __init__(self):
        self.state = State()
        self.state.load()
        self.update_project_info()

    def update_project_info(self):
        projs = self.state.projects

        # Generate names
        todo = set(os.path.normpath(p) for p in self.state.projects.iterkeys())
        for parents in itertools.count(1):
            # Try generating names with this level of parents
            counts = {}
            for p in todo:
                candidate = "/".join(p.split("/")[-parents:])
                counts.setdefault(candidate, []).append(p)

            # Accept those that do not conflict
            for cand, dirs in counts.iteritems():
                if len(dirs) == 1:
                    projs[dirs[0]].name = cand
                    todo.discard(dirs[0])

            if not todo: break

    def scan(self):
        old_projects = set(self.state.projects.keys())

        for p in self._raw_scan():
            old_projects.discard(p)
            op = self.state.projects.get(p, None)
            if op is None:
                log.info("add %s", p)
                self.state.projects[p] = Project(p)
            else:
                log.debug("hit %s", p)

        for p in old_projects:
            log.info("rm %s", p)
            del self.state.projects[p]

        self.update_project_info()
        self.state.save()

    def _raw_scan(self):
        leaffilemarkers = ["manage.py", "configure.ac", "setup.py", "Rakefile"]
        leafdirmarkers = [".git", ".svn"]

        top = os.path.expanduser("~")
        for root, dirs, files in os.walk(top):
            if "ore" in files:
                yield os.path.join(top, root)

            for m in leaffilemarkers:
                if m in files:
                    dirs[0:len(dirs)] = []
                    break

            for m in leafdirmarkers:
                if m in dirs:
                    dirs[0:len(dirs)] = []
                    break

            # Prune hidden dirs
            newdirs = []
            for d in dirs:
                if d.startswith("."): continue
                newdirs.append(d)
            if len(newdirs) != len(dirs):
                dirs[0:len(dirs)] = newdirs

