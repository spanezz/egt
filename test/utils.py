from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence
from unittest import TestCase

from egtlib import Project
from egtlib.config import Config


class ProjectTestMixin(TestCase):
    DEFAULT_META: Optional[dict[str, Any]] = None
    DEFAULT_LOG: Optional[Sequence[str]] = None
    DEFAULT_BODY: Optional[Sequence[str]] = None

    def setUp(self):
        self.workdir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.taskrc = self.workdir / ".taskrc"
        with self.taskrc.open("w") as fd:
            print(f"data.location={self.workdir / 'tasks'}", file=fd)

    def project(
        self,
        *,
        meta: Optional[dict[str, Any]] = None,
        log: Optional[Sequence[str]] = None,
        body: Optional[Sequence[str]] = None,
        load: bool = True,
    ) -> Project:
        if meta is None:
            meta = self.DEFAULT_META
        if log is None:
            log = self.DEFAULT_LOG
        if body is None:
            body = self.DEFAULT_BODY

        path = self.workdir / ".egt"
        with path.open("w") as fd:
            if meta:
                for k, v in meta.items():
                    print(f"{k}: {v}", file=fd)
                print(file=fd)

            if log:
                for line in log:
                    print(line, file=fd)
                print(file=fd)

            if body:
                for line in body:
                    print(line, file=fd)

        proj = Project(path, statedir=self.workdir, config=Config())
        proj.body.tasks.force_load_tw(config_filename=self.taskrc)
        if load:
            proj.load()
        return proj
