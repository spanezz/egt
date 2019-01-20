import unittest
from .utils import ProjectTestMixin
from egtlib import Project
import io
import os
import datetime


class TestArchive(ProjectTestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.projectfile = os.path.join(self.workdir.name, ".egt")

    def archive(self, text, today=datetime.date(2019, 2, 1)):
        with open(self.projectfile, "wt") as fd:
            if isinstance(text, str):
                fd.write(text)
            else:
                for line in text:
                    print(line, file=fd)

        proj = Project(self.projectfile, statedir=self.workdir.name)
        proj.load()
        proj.meta.set("Name", "test")
        proj.meta.set("Archive-Dir", self.workdir.name)
        return proj, proj.archive(cutoff=today.replace(day=1))

    def to_text(self, proj, today=datetime.date(2019, 2, 1)):
        with io.StringIO() as fd:
            proj.print(fd, today=today)
            return fd.getvalue()

    def test_archive(self):
        proj, archives = self.archive([
            "2019",
            "01 january: 10:00-12:00",
            " - broken",
            "01 february: 10:00-11:00",
            " - fixed",
        ])

        self.assertEqual(len(archives), 1)
        arc = archives[0]
        self.assertEqual(arc.abspath, os.path.join(self.workdir.name, "201901-test.egt"))

        self.assertEqual(self.to_text(arc).splitlines(), [
            "Name: test",
            "Archive-Dir: " + self.workdir.name,
            "Archived: yes",
            "Total: 2h",
            "",
            "2019",
            "01 january: 10:00-12:00 2h",
            " - broken",
            "",
        ])

        self.assertEqual(self.to_text(proj).splitlines(), [
            "Name: test",
            "Archive-Dir: " + self.workdir.name,
            "",
            "2019",
            "01 february: 10:00-11:00 1h",
            " - fixed",
            "",
        ])

    def test_archive_multi(self):
        proj, archives = self.archive([
            "2018",
            "15 december: 9:00-13:00",
            " - worked",
            "2019",
            "01 january: 10:00-12:00",
            " - broken",
            "01 february: 10:00-11:00",
            " - fixed",
        ])

        self.assertEqual(len(archives), 2)

        arc = archives[0]
        self.assertEqual(arc.abspath, os.path.join(self.workdir.name, "201812-test.egt"))
        self.assertEqual(self.to_text(arc).splitlines(), [
            "Name: test",
            "Archive-Dir: " + self.workdir.name,
            "Archived: yes",
            "Total: 4h",
            "",
            "2018",
            "15 december: 9:00-13:00 4h",
            " - worked",
            "",
        ])

        arc = archives[1]
        self.assertEqual(arc.abspath, os.path.join(self.workdir.name, "201901-test.egt"))
        self.assertEqual(self.to_text(arc).splitlines(), [
            "Name: test",
            "Archive-Dir: " + self.workdir.name,
            "Archived: yes",
            "Total: 2h",
            "",
            "2019",
            "01 january: 10:00-12:00 2h",
            " - broken",
            "",
        ])

        self.assertEqual(self.to_text(proj).splitlines(), [
            "Name: test",
            "Archive-Dir: " + self.workdir.name,
            "",
            "2019",
            "01 february: 10:00-11:00 1h",
            " - fixed",
            "",
        ])

    def test_archive_tagged(self):
        proj, archives = self.archive([
            "2019",
            "01 january: 10:00-12:00 +tag1 +tag2",
            " - broken",
            "02 january: 10:00-11:00 +tag1",
            " - fixed",
            "03 january: 10:00-13:00",
            " - really fixed",
        ])

        self.assertEqual(len(archives), 1)
        arc = archives[0]
        self.assertEqual(arc.abspath, os.path.join(self.workdir.name, "201901-test.egt"))

        self.assertEqual(self.to_text(arc).splitlines(), [
            "Name: test",
            "Archive-Dir: " + self.workdir.name,
            "Archived: yes",
            "Total:",
            " *: 6h",
            " tag1: 3h",
            " tag2: 2h",
            "",
            "2019",
            "01 january: 10:00-12:00 2h +tag1 +tag2",
            " - broken",
            "02 january: 10:00-11:00 1h +tag1",
            " - fixed",
            "03 january: 10:00-13:00 3h",
            " - really fixed",
            "",
        ])

        self.assertEqual(self.to_text(proj).splitlines(), [
            "Name: test",
            "Archive-Dir: " + self.workdir.name,
            "",
            "2019",
            "",
        ])
