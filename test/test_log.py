# coding: utf8
import unittest
from .utils import ProjectTestMixin
from egtlib import Project
import io
import os
import datetime


class TestLog(ProjectTestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.projectfile = os.path.join(self.workdir.name, ".egt")

    def write_project(self, log_lines):
        with open(self.projectfile, "wt") as fd:
            print("Name: testprj", file=fd)
            print("Tags: testtag1, testtag2", file=fd)
            print(file=fd)
            for l in log_lines:
                print(l, file=fd)
            print(file=fd)
            print("hypothetic plans", file=fd)

    def testParse(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        self.write_project([
            "2015",
            "15 march: 9:00-12:00",
            " - tested things",
            "16 march:",
            " - implemented day logs",
        ])
        proj = Project(self.projectfile, statedir=self.workdir.name)
        proj.body.force_load_tw(config_filename=self.taskrc)
        proj.load()

        from egtlib.log import Timebase, Entry

        self.assertEqual(len(proj.log), 3)
        self.assertIsInstance(proj.log[0], Timebase)
        self.assertIsInstance(proj.log[1], Entry)
        self.assertIsInstance(proj.log[2], Entry)
        self.assertEqual(proj.log[0].dt, datetime.datetime(2015, 1, 1))

        entry = proj.log[1]
        self.assertEqual(entry.begin, datetime.datetime(2015, 3, 15, 9))
        self.assertEqual(entry.until, datetime.datetime(2015, 3, 15, 12))
        self.assertEqual(entry.head, "15 march: 9:00-12:00")
        self.assertEqual(entry.body, [" - tested things"])
        self.assertEqual(entry.fullday, False)

        entry = proj.log[2]
        self.assertEqual(entry.begin, datetime.datetime(2015, 3, 16, 0))
        self.assertEqual(entry.until, datetime.datetime(2015, 3, 17, 0))
        self.assertEqual(entry.head, "16 march:")
        self.assertEqual(entry.body, [" - implemented day logs"])
        self.assertEqual(entry.fullday, True)

        with io.StringIO() as out:
            proj.log.print(out)
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 March: 09:00-12:00 3h")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], "16 March:")
        self.assertEqual(body_lines[4], " - implemented day logs")

    def testParseNewRequest(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        self.write_project([
            "2015",
            "15 march: 9:00-12:00",
            " - tested things",
            "8:00",
            "+",
        ])
        proj = Project(self.projectfile, statedir=self.workdir.name)
        proj.body.force_load_tw(config_filename=self.taskrc)
        proj.load()

        from egtlib.log import Timebase, Entry

        self.assertEqual(len(proj.log), 4)
        self.assertIsInstance(proj.log[0], Timebase)
        self.assertIsInstance(proj.log[1], Entry)
        self.assertIsInstance(proj.log[2], Entry)
        self.assertIsInstance(proj.log[3], Entry)
        self.assertEqual(proj.log[0].dt, datetime.datetime(2015, 1, 1))

        self.assertEqual(proj.log[1].begin, datetime.datetime(2015, 3, 15, 9))
        self.assertEqual(proj.log[1].until, datetime.datetime(2015, 3, 15, 12))
        self.assertEqual(proj.log[1].head, "15 march: 9:00-12:00")
        self.assertEqual(proj.log[1].body, [" - tested things"])

        new_entry_dt2 = datetime.datetime.combine(datetime.datetime.today(), datetime.time(8, 0, 0))
        self.assertEqual(proj.log[2].begin, new_entry_dt2)
        self.assertEqual(proj.log[2].until, None)
        self.assertEqual(proj.log[2].head, new_entry_dt2.strftime("%d %B: %H:%M-"))
        self.assertEqual(proj.log[2].body, [])
        self.assertEqual(proj.log[2].fullday, False)

        new_entry_dt3 = datetime.datetime.combine(datetime.datetime.today(), datetime.time(0))
        self.assertEqual(proj.log[3].begin, new_entry_dt3)
        self.assertEqual(proj.log[3].until, new_entry_dt3 + datetime.timedelta(days=1))
        self.assertEqual(proj.log[3].head, new_entry_dt3.strftime("%d %B:"))
        self.assertEqual(proj.log[3].body, [])
        self.assertEqual(proj.log[3].fullday, True)

        with io.StringIO() as out:
            proj.log.print(out)
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 March: 09:00-12:00 3h")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], new_entry_dt2.strftime("%d %B: %H:%M-"))
        self.assertEqual(body_lines[4], new_entry_dt3.strftime("%d %B:"))
