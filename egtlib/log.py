# coding: utf8
from __future__ import absolute_import
from .utils import format_duration
import datetime


class Log(object):
    def __init__(self, begin, until, head, body):
        self.begin = begin
        self.until = until
        self.head = head
        self.body = body
        self.day_billing = None

    @property
    def duration(self):
        """
        Return the duration in minutes
        """
        if not self.until:
            until = datetime.datetime.now()
        else:
            until = self.until

        td = (until - self.begin)
        return (td.days * 86400 + td.seconds) / 60

    @property
    def formatted_duration(self):
        return format_duration(self.duration)

    def output(self, project=None, file=None):
        head = [self.begin.strftime("%d %B: %H:%M-")]
        if self.until:
            head.append(self.until.strftime("%H:%M "))
            if self.day_billing is None:
                head.append(format_duration(self.duration))
            elif self.day_billing == 0.0:
                head.append("-")
            elif self.day_billing == 0.5:
                head.append("½d")
            else:
                head.append("{:.1}d".format(self.day_billing))
        if project is not None:
            head.append(" [%s]" % project)
        print("".join(head), file=file)
        print(self.body, file=file)
