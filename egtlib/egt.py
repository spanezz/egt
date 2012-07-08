from __future__ import absolute_import
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


class Egt(object):
    def __init__(self, tags=[]):
        self.state = State()
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

    def project_by_name(self, name):
        """
        Return a Project by its name
        """
        for k, v in self.state.projects.iteritems():
            if v.name == name:
                return v
        return None

    def scan(self):
        return self.state.rescan()

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
