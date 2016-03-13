# coding: utf8
from __future__ import absolute_import
import re
import datetime
from collections import OrderedDict
from .parse import Regexps, Lines
import logging
from collections import namedtuple

log = logging.getLogger(__name__)

class ProjectParser(Lines):
    def __init__(self, pathname, fd=None):
        super().__init__(pathname, fd)
        from .meta import Meta
        self.meta = Meta()
        from .log import Log
        self.log = Log()
        from .body import Body
        self.body = Body()

    def parse(self):
        first = self.peek()

        # Parse metadata
        # If it starts with a log, there is no metadata: stop
        # If the first line doesn't look like a header, stop
        if not Regexps.log_date.match(first) and not Regexps.log_head.match(first) and Regexps.meta_head.match(first):
            log.debug("%s:%d: parsing metadata", self.fname, self.lineno)
            self.meta.parse(self)

        self.skip_empty_lines()

        # Parse log entries
        if self.log.is_log_start(self.peek()):
            log.debug("%s:%d: parsing log", self.fname, self.lineno)
            self.log.parse(self, lang=self.meta.get("lang", None))

        self.skip_empty_lines()

        # Parse/store body
        log.debug("%s:%d: parsing body", self.fname, self.lineno)
        self.body.parse(self)
