# coding: utf8
from __future__ import absolute_import
from .utils import format_duration, format_td
import datetime

class Log(object):
    def __init__(self, begin, until, body):
        self.begin = begin
        self.until = until
        self.body = body

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

    def output(self, project=None):
        head = [self.begin.strftime("%d %B: %H:%M-")]
        if self.until:
            head.append(self.until.strftime("%H:%M "))
            head.append(format_duration(self.duration))
        if project is not None:
            head.append(" [%s]" % project)
        print "".join(head)
        print self.body

