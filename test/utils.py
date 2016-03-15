# coding: utf8

import tempfile
import os


class ProjectTestMixin:
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.taskrc = os.path.join(self.workdir.name, ".taskrc")
        with open(self.taskrc, "wt") as fd:
            print("data.location={}".format(os.path.join(self.workdir.name, "tasks")), file=fd)

    def tearDown(self):
        self.workdir.cleanup()
