from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest import TestCase, mock

from egtlib import Project
from egtlib.config import Config
from egtlib.utils import contain_taskwarrior_noise


class ProjectTestMixin(TestCase):
    DEFAULT_META: dict[str, Any] | None = None
    DEFAULT_LOG: Sequence[str] | None = None
    DEFAULT_BODY: Sequence[str] | None = None

    def setUp(self) -> None:
        self.workdir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.taskrc = self.workdir / ".taskrc"
        with self.taskrc.open("w") as fd:
            print(f"data.location={self.workdir / 'tasks'}", file=fd)
        self.enterContext(mock.patch("egtlib.body_task.Tasks.get_taskrc_path", return_value=self.taskrc))

    def project(
        self,
        *,
        meta: dict[str, Any] | None = None,
        log: Sequence[str] | None = None,
        body: Sequence[str] | None = None,
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
        with contain_taskwarrior_noise():
            proj.body.tasks.force_load_tw(config_filename=self.taskrc)
        if load:
            proj.load()
        return proj
