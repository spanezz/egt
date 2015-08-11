import logging
import datetime
import sys
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
    def __init__(self, config=None, filter=[], archived=False):
        self.config = config
        self.state = State(self.config, archived)
        self.filter = ProjectFilter(filter)

    @property
    def projects(self):
        return sorted((p for p in self.state.projects.values() if self.filter.matches(p)), key=lambda p:p.name)

    @property
    def all_tags(self):
        res = set()
        for p in self.projects:
            res.update(p.tags)
        return sorted(res)

    def project(self, name):
        # FIXME: inefficient, but for now it will do
        for p in self.projects:
            if p.name == name:
                return p
        return None

    def project_by_name(self, name):
        """
        Return a Project by its name
        """
        for k, v in self.state.projects.items():
            if v.name == name:
                return v
        return None

    def scan(self, dirs):
        return self.state.rescan(dirs)

    def print_next_actions(self):
        """
        Print the first group of next actions in each project that has no
        context and no event date.
        """
        for p in self.projects:
            for el in p.body:
                if el.TAG == "spacer": continue
                if el.TAG != "next-actions": break
                if el.contexts: break
                if el.event: break
                print(" * {}".format(p.name))
                for l in el.lines:
                    print(l)
                print()
                break

    def print_context_actions(self, contexts=[]):
        for p in self.projects:
            has_name = False
            for el in p.body:
                if el.TAG != "next-actions": continue
                if contexts:
                    if el.contexts.isdisjoint(contexts): continue
                else:
                    if el.contexts: continue

                if not has_name:
                    has_name = True
                    print(" * {}".format(p.name))
                for l in el.lines:
                    print(l)

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

    def calendar(self, start=None, end=None, days=7):
        if start is None:
            start = datetime.date.today()
        if end is None:
            end = start + datetime.timedelta(days=days)

        log.debug("Calendar %s--%s filter:%s", start, end, ",".join(self.filter.args))

        events = []
        for p in self.projects:
            for na in p.next_events(start, end):
                events.append(na)

        events.sort(key=lambda x: x.event["start"])

        return events

    def backup(self, out=sys.stdout):
        import tarfile
        tarout = tarfile.open(None, "w|", fileobj=out)
        for p in self.projects:
            p.backup(tarout)
        tarout.close()
