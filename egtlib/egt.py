from __future__ import absolute_import
import os
import os.path
import logging
import datetime
import itertools
import sys
from .state import State
from .project import Project
from .utils import intervals_intersect

log = logging.getLogger(__name__)


class WeeklyReport(object):
    def __init__(self):
        self.projs = []

    def add(self, p):
        self.projs.append(p)

    def report(self, end=None, days=7):
        if end is None:
            d_until = datetime.date.today()
        else:
            d_until = end
        d_begin = d_until - datetime.timedelta(days=days)

        res = dict(
            begin=d_begin,
            until=d_until,
        )

        log = []
        count = 0
        mins = 0
        for p in self.projs:
            for l in p.log:
                if intervals_intersect(l.begin.date(), l.until.date() if l.until else datetime.date.today(), d_begin, d_until):
                    log.append((l, p))
                    count += 1
                    mins += l.duration

        res.update(
            count=count,
            hours=mins / 60,
            hours_per_day=mins / 60 / days,
            hours_per_workday=mins / 60 / 5,  # FIXME: properly compute work days in period
            log=log,
        )

        return res


class Egt(object):
    def __init__(self, tags=[]):
        self.state = State()
        self.state.load()
        self.update_project_info()
        self.tags = frozenset(tags)

    @property
    def projects(self):
        if not self.tags:
            return self.state.projects
        else:
            return dict(x for x in self.state.projects.iteritems() if not x[1].tags.isdisjoint(self.tags))

    @property
    def all_tags(self):
        res = set()
        for p in self.projects.itervalues():
            res.update(p.tags)
        return sorted(res)

    def project(self, name):
        # FIXME: inefficient, but for now it will do
        for p in self.projects.itervalues():
            if p.name == name:
                return p
        return None

    def update_project_info(self):
        projs = self.state.projects

        # Load activity files
        for p in self.state.projects.itervalues():
            p.load()

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

    def project_by_name(self, name):
        """
        Return a Project by its name
        """
        for k, v in self.state.projects.iteritems():
            if v.name == name:
                return v
        return None

    def weekrpt(self, tags=None, end=None, days=7):
        rep = WeeklyReport()
        if tags is None:
            for p in self.projects.itervalues():
                rep.add(p)
        else:
            for p in self.projects.itervalues():
                if p.tags.issuperset(tags):
                    rep.add(p)

        return rep.report(end, days)

    def backup(self, out=sys.stdout):
        import tarfile
        tarout = tarfile.open(None, "w|", fileobj=out)
        for p in self.projects.itervalues():
            p.backup(tarout)
        tarout.close()
