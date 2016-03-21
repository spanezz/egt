import logging
import datetime
import sys
import re
from .state import State
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
        from .log import Entry
        for p in self.projs:
            for l in p.log.entries:
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


class ProjectFilter:
    """
    Filter for projects, based on a list of keywords.

    A keyword can be:
        +tag  matches projects that have this tag
        -tag  matches projects that do not have this tag
        name  matches projects with this name

    A project matches the filter if its name is explicitly listed. If it is
    not, it matches if its tag set contains all the +tag tags, and does not
    contain any of the -tag tags.
    """
    def __init__(self, args):
        self.args = args
        self.names = set()
        self.tags_wanted = set()
        self.tags_unwanted = set()

        for f in args:
            if f.startswith("+"):
                self.tags_wanted.add(f[1:])
            elif f.startswith("-"):
                self.tags_unwanted.add(f[1:])
            else:
                self.names.add(f)

    def matches(self, project):
        """
        Check if this project matches the filter.
        """
        if self.names and project.name not in self.names: return False
        if self.tags_wanted and self.tags_wanted.isdisjoint(project.tags): return False
        if self.tags_unwanted and not self.tags_unwanted.isdisjoint(project.tags): return False
        return True


class Egt:
    def __init__(self, config=None, filter=[], show_archived=False, statedir=None):
        self.config = config
        self.state = State()
        self.state.load(statedir)
        self.show_archived = show_archived
        self.filter = ProjectFilter(filter)
        # Dict mapping project names to Project objects.
        # It is built lazily when needed, and is None when not yet built.
        self._projects = None

    def load_project(self, fname, project_fd=None):
        """
        Return a Project object given its file name.

        Returns None if the file does not exist or no suitable project could be
        created from that file.
        """
        from .project import Project
        if not Project.has_project(fname):
            log.warning("project %s has disappeared from %s: please rerun scan", name, fname)
            return None
        proj = Project.from_file(fname, fd=project_fd)
        if not self.show_archived and proj.archived: return None
        proj.default_tags.update(self._default_tags(fname))
        if not self.filter.matches(proj): return None
        return proj

    def _load_projects(self):
        projs = {}
        for name, info in self.state.projects.items():
            proj = self.load_project(info["fname"])
            if proj is None: continue
            projs[proj.name] = proj
        self._projects = projs

    def _default_tags(self, abspath):
        """
        Guess tags from the project file pathname
        """
        if self.config is None: return set()
        if "autotag" not in self.config: return set()
        autotags = self.config["autotag"]
        if autotags is None: return set()

        tags = set()
        for tag, regexp in autotags.items():
            if re.search(regexp, abspath):
                tags.add(tag)
        return tags

    @property
    def projects(self):
        if self._projects is None: self._load_projects()
        return sorted(self._projects.values(), key=lambda p: p.name)

    @property
    def all_tags(self):
        res = set()
        for p in self.projects:
            res.update(p.tags)
        return sorted(res)

    def project(self, name, project_fd=None):
        """
        Return a Project by its name
        """
        # Try loading from _projects, if we have already loaded it
        if self._projects is not None:
            return self._projects.get(name, None)

        # Otherwise, look it up on state and load it on the fly
        info = self.state.projects.get(name, None)
        if info is None: return None
        return self.load_project(info["fname"], project_fd=project_fd)

    def weekrpt(self, tags=None, end=None, days=7, projs=None):
        rep = WeeklyReport()
        if projs:
            for p in projs:
                rep.add(p)
        else:
            for p in self.projects:
                if not tags or p.tags.issuperset(tags):
                    rep.add(p)
        return rep.report(end, days)

    def backup(self, out=sys.stdout):
        import tarfile
        tarout = tarfile.open(None, "w|", fileobj=out)
        for p in self.projects:
            p.backup(tarout)
        tarout.close()
