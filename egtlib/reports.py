import datetime as dt
from typing import Any

from .project import Project
from .utils import intervals_intersect


class WeeklyReport:
    def __init__(self) -> None:
        self.projs: list["Project"] = []

    def add(self, p: Project) -> None:
        self.projs.append(p)

    def report(
        self, end: dt.date | None = None, days: int = 7
    ) -> dict[str, Any]:
        if end is None:
            d_until = dt.date.today()
        else:
            d_until = end
        d_begin = d_until - dt.timedelta(days=days)

        res: dict[str, Any] = dict(
            begin=d_begin,
            until=d_until,
        )

        log = []
        count = 0
        mins = 0
        for p in self.projs:
            for e in p.log.entries:
                if intervals_intersect(
                    e.begin.date(),
                    e.until.date() if e.until else dt.date.today(),
                    d_begin,
                    d_until,
                ):
                    log.append((e, p))
                    count += 1
                    mins += e.duration

        res.update(
            count=count,
            hours=mins / 60,
            hours_per_day=mins / 60 / days,
            hours_per_workday=mins
            / 60
            / 5,  # FIXME: properly compute work days in period
            log=log,
        )

        return res
