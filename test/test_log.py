from __future__ import annotations

import datetime
import io
import os
import unittest
from typing import cast

from egtlib import Project
from egtlib.config import Config
from egtlib.log import Entry, EntryBase, Timebase, Command

from .utils import ProjectTestMixin


class TestLog(ProjectTestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.projectfile = os.path.join(self.workdir.name, ".egt")

    def write_project(self, log_lines, lang=None):
        with open(self.projectfile, "wt") as fd:
            print("Name: testprj", file=fd)
            if lang is not None:
                print("Lang: {}".format(lang), file=fd)
            print("Tags: testtag1, testtag2", file=fd)
            print(file=fd)
            for line in log_lines:
                print(line, file=fd)
            print(file=fd)
            print("hypothetic plans", file=fd)

    def testEmpty(self):
        with open(self.projectfile, "wt") as fd:
            print("Name: testprj", file=fd)
            print("", file=fd)
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.load()
        self.assertEqual(len(proj.log._entries), 0)

        out = io.StringIO()
        proj.log.print(file=out, today=datetime.date(2018, 6, 1))
        self.assertEqual(out.getvalue(), "2018\n")

    def testWritePartial(self):
        self.write_project(
            [
                "2015",
                "15 march: 9:00-12:00",
                " - tested things",
                "16 march:",
                " - implemented day logs",
            ]
        )
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.load()
        proj.log._entries.pop(0)
        self.assertEqual(len(proj.log._entries), 2)

        out = io.StringIO()
        proj.log.print(file=out, today=datetime.date(2015, 6, 1))
        self.assertEqual(
            out.getvalue(),
            "2015\n" "15 march: 9:00-12:00 3h\n" " - tested things\n" "16 march:\n" " - implemented day logs\n",
        )

    def testWriteNewYear(self):
        # TODO: mock year as 2016
        self.write_project(
            [
                "2015",
                "15 march: 9:00-12:00",
                " - tested things",
            ]
        )
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.load()
        self.assertEqual(len(proj.log._entries), 2)

        out = io.StringIO()
        proj.log.print(file=out, today=datetime.date(2016, 6, 1))
        self.assertEqual(out.getvalue(), "2015\n" "15 march: 9:00-12:00 3h\n" " - tested things\n" "2016\n")

    def assertEntryIsTimebase(self, entry: EntryBase) -> Timebase:
        self.assertIsInstance(entry, Timebase)
        return cast(Timebase, entry)

    def assertEntryIsEntry(self, entry: EntryBase) -> Entry:
        self.assertIsInstance(entry, Entry)
        return cast(Entry, entry)

    def assertEntryIsCommand(self, entry: EntryBase) -> Command:
        self.assertIsInstance(entry, Command)
        return cast(Command, entry)

    def testParse(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        self.write_project(
            [
                "2015",
                "15 march: 9:00-12:00",
                " - tested things",
                "16 march:",
                " - implemented day logs",
            ]
        )
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.body.tasks.force_load_tw(config_filename=self.taskrc)
        proj.load()

        self.assertEqual(len(proj.log._entries), 3)

        e0 = self.assertEntryIsTimebase(proj.log._entries[0])
        self.assertEqual(e0.dt, datetime.datetime(2015, 1, 1))

        e1 = self.assertEntryIsEntry(proj.log._entries[1])
        e2 = self.assertEntryIsEntry(proj.log._entries[2])

        self.assertEqual(e1.begin, datetime.datetime(2015, 3, 15, 9))
        self.assertEqual(e1.until, datetime.datetime(2015, 3, 15, 12))
        self.assertEqual(e1.head, "15 march: 9:00-12:00")
        self.assertEqual(e1.body, [" - tested things"])
        self.assertEqual(e1.fullday, False)

        self.assertEqual(e2.begin, datetime.datetime(2015, 3, 16, 0))
        self.assertEqual(e2.until, datetime.datetime(2015, 3, 17, 0))
        self.assertEqual(e2.head, "16 march:")
        self.assertEqual(e2.body, [" - implemented day logs"])
        self.assertEqual(e2.fullday, True)

        with io.StringIO() as out:
            proj.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 march: 9:00-12:00 3h")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], "16 march:")
        self.assertEqual(body_lines[4], " - implemented day logs")

    def testParseNewRequest(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        self.write_project(
            [
                "2015",
                "15 march: 9:00-12:00",
                " - tested things",
                "8:00",
                " - new entry",
                "+",
                " - new day entry",
            ]
        )
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.body.tasks.force_load_tw(config_filename=self.taskrc)
        proj.load()

        self.assertEqual(len(proj.log._entries), 4)
        e0 = self.assertEntryIsTimebase(proj.log._entries[0])
        e1 = self.assertEntryIsEntry(proj.log._entries[1])
        e2 = self.assertEntryIsCommand(proj.log._entries[2])
        e3 = self.assertEntryIsCommand(proj.log._entries[3])

        self.assertEqual(e0.dt, datetime.datetime(2015, 1, 1))

        self.assertEqual(e1.begin, datetime.datetime(2015, 3, 15, 9))
        self.assertEqual(e1.until, datetime.datetime(2015, 3, 15, 12))
        self.assertEqual(e1.head, "15 march: 9:00-12:00")
        self.assertEqual(e1.body, [" - tested things"])

        self.assertEqual(e2.start, datetime.time(8, 0))
        self.assertEqual(e2.head, "8:00")
        self.assertEqual(e2.body, [" - new entry"])

        self.assertEqual(e3.start, None)
        self.assertEqual(e3.head, "+")
        self.assertEqual(e3.body, [" - new day entry"])

        proj.log.sync()

        self.assertEqual(len(proj.log._entries), 4)
        f0 = self.assertEntryIsTimebase(proj.log._entries[0])
        f1 = self.assertEntryIsEntry(proj.log._entries[1])
        f2 = self.assertEntryIsEntry(proj.log._entries[2])
        f3 = self.assertEntryIsEntry(proj.log._entries[3])

        self.assertEqual(f0.dt, datetime.datetime(2015, 1, 1))

        self.assertEqual(f1.begin, datetime.datetime(2015, 3, 15, 9))
        self.assertEqual(f1.until, datetime.datetime(2015, 3, 15, 12))
        self.assertEqual(f1.head, "15 march: 9:00-12:00")
        self.assertEqual(f1.body, [" - tested things"])

        new_entry_dt2 = datetime.datetime.combine(datetime.datetime.today(), datetime.time(8, 0, 0))
        self.assertEqual(f2.begin, new_entry_dt2)
        self.assertEqual(f2.until, None)
        self.assertEqual(f2.head, new_entry_dt2.strftime("%d %B: %H:%M-"))
        self.assertEqual(f2.body, [" - new entry"])
        self.assertEqual(f2.fullday, False)

        new_entry_dt3 = datetime.datetime.combine(datetime.datetime.today(), datetime.time(0))
        self.assertEqual(f3.begin, new_entry_dt3)
        self.assertEqual(f3.until, new_entry_dt3 + datetime.timedelta(days=1))
        self.assertEqual(f3.head, new_entry_dt3.strftime("%d %B:"))
        self.assertEqual(f3.body, [" - new day entry"])
        self.assertEqual(f3.fullday, True)

        with io.StringIO() as out:
            proj.log.print(out)
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 7)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 march: 9:00-12:00 3h")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], new_entry_dt2.strftime("%d %B: %H:%M-"))
        self.assertEqual(body_lines[4], " - new entry")
        self.assertEqual(body_lines[5], new_entry_dt3.strftime("%d %B:"))
        self.assertEqual(body_lines[6], " - new day entry")

    def testParseItalian(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        self.write_project(
            [
                "2015",
                "15 marzo: 9:00-12:00",
                " - tested things",
                "16 marzo:",
                " - implemented day logs",
            ],
            lang="it",
        )
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.body.tasks.force_load_tw(config_filename=self.taskrc)
        proj.load()

        self.assertEqual(len(proj.log._entries), 3)

        e0 = self.assertEntryIsTimebase(proj.log._entries[0])
        e1 = self.assertEntryIsEntry(proj.log._entries[1])
        e2 = self.assertEntryIsEntry(proj.log._entries[2])

        self.assertEqual(e0.dt, datetime.datetime(2015, 1, 1))

        self.assertEqual(e1.begin, datetime.datetime(2015, 3, 15, 9))
        self.assertEqual(e1.until, datetime.datetime(2015, 3, 15, 12))
        self.assertEqual(e1.head, "15 marzo: 9:00-12:00")
        self.assertEqual(e1.body, [" - tested things"])
        self.assertEqual(e1.fullday, False)

        self.assertEqual(e2.begin, datetime.datetime(2015, 3, 16, 0))
        self.assertEqual(e2.until, datetime.datetime(2015, 3, 17, 0))
        self.assertEqual(e2.head, "16 marzo:")
        self.assertEqual(e2.body, [" - implemented day logs"])
        self.assertEqual(e2.fullday, True)

        with io.StringIO() as out:
            proj.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 marzo: 9:00-12:00 3h")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], "16 marzo:")
        self.assertEqual(body_lines[4], " - implemented day logs")

    def testParseFrench(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        self.write_project(
            [
                "2015",
                "15 mars: 9:00-12:00",
                " - tested things",
                "16 mars:",
                " - implemented day logs",
            ],
            lang="fr",
        )
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.body.tasks.force_load_tw(config_filename=self.taskrc)
        proj.load()

        self.assertEqual(len(proj.log._entries), 3)

        e0 = self.assertEntryIsTimebase(proj.log._entries[0])
        e1 = self.assertEntryIsEntry(proj.log._entries[1])
        e2 = self.assertEntryIsEntry(proj.log._entries[2])

        self.assertEqual(e0.dt, datetime.datetime(2015, 1, 1))

        self.assertEqual(e1.begin, datetime.datetime(2015, 3, 15, 9))
        self.assertEqual(e1.until, datetime.datetime(2015, 3, 15, 12))
        self.assertEqual(e1.head, "15 mars: 9:00-12:00")
        self.assertEqual(e1.body, [" - tested things"])
        self.assertEqual(e1.fullday, False)

        self.assertEqual(e2.begin, datetime.datetime(2015, 3, 16, 0))
        self.assertEqual(e2.until, datetime.datetime(2015, 3, 17, 0))
        self.assertEqual(e2.head, "16 mars:")
        self.assertEqual(e2.body, [" - implemented day logs"])
        self.assertEqual(e2.fullday, True)

        with io.StringIO() as out:
            proj.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 mars: 9:00-12:00 3h")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], "16 mars:")
        self.assertEqual(body_lines[4], " - implemented day logs")

    def test_mixed_langs(self):
        lines = [
            "2015",
            "9:00-",
            " - tested things",
            "+",
            " - implemented day logs",
        ]
        self.write_project(lines + ["15 march:", " - localized"])
        proj_default = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj_default.load()

        e = self.assertEntryIsEntry(proj_default.log._entries[3])
        self.assertEqual(e.begin, datetime.datetime(2015, 3, 15, 0, 0, 0))

        self.write_project(lines + ["15 marzo:", " - localized"], lang="it")
        proj_it = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj_it.load()
        e = self.assertEntryIsEntry(proj_default.log._entries[3])
        self.assertEqual(e.begin, datetime.datetime(2015, 3, 15, 0, 0, 0))

        self.write_project(lines + ["15 mars:", " - localized"], lang="fr")
        proj_fr = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj_fr.load()
        e = self.assertEntryIsEntry(proj_default.log._entries[3])
        self.assertEqual(e.begin, datetime.datetime(2015, 3, 15, 0, 0, 0))

        self.write_project(lines + ["15 march:", " - localized"])
        proj_default1 = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj_default1.load()
        e = self.assertEntryIsEntry(proj_default.log._entries[3])
        self.assertEqual(e.begin, datetime.datetime(2015, 3, 15, 0, 0, 0))

        proj_default.log.sync(today=datetime.date(2016, 6, 1))
        proj_it.log.sync(today=datetime.date(2016, 6, 1))
        proj_fr.log.sync(today=datetime.date(2016, 6, 1))

        with io.StringIO() as out:
            proj_default.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()
            self.assertEqual(
                body_lines,
                [
                    "2015",
                    "01 June: 09:00-",
                    " - tested things",
                    "01 June:",
                    " - implemented day logs",
                    "15 march:",
                    " - localized",
                ],
            )

        with io.StringIO() as out:
            proj_it.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()
            self.assertEqual(
                body_lines,
                [
                    "2015",
                    "01 giugno: 09:00-",
                    " - tested things",
                    "01 giugno:",
                    " - implemented day logs",
                    "15 marzo:",
                    " - localized",
                ],
            )

        with io.StringIO() as out:
            proj_fr.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()
            self.assertEqual(
                body_lines,
                [
                    "2015",
                    "01 juin: 09:00-",
                    " - tested things",
                    "01 juin:",
                    " - implemented day logs",
                    "15 mars:",
                    " - localized",
                ],
            )

    def testTags(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        self.write_project(
            [
                "2015",
                "15 march: 9:00-12:00 3h +tag1 +tag2",
                " - tested things",
                "16 march: +tag2",
                " - implemented day logs",
            ]
        )
        proj = Project(self.projectfile, statedir=self.workdir.name, config=Config())
        proj.load()

        e1 = self.assertEntryIsEntry(proj.log._entries[1])
        e2 = self.assertEntryIsEntry(proj.log._entries[2])
        self.assertEqual(e1.tags, ["tag1", "tag2"])
        self.assertEqual(e2.tags, ["tag2"])

        with io.StringIO() as out:
            proj.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 march: 9:00-12:00 3h +tag1 +tag2")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], "16 march: +tag2")
        self.assertEqual(body_lines[4], " - implemented day logs")

        e1.tags.append("tag3")

        with io.StringIO() as out:
            proj.log.print(out, today=datetime.date(2015, 6, 1))
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertEqual(body_lines[0], "2015")
        self.assertEqual(body_lines[1], "15 march: 9:00-12:00 3h +tag1 +tag2 +tag3")
        self.assertEqual(body_lines[2], " - tested things")
        self.assertEqual(body_lines[3], "16 march: +tag2")
        self.assertEqual(body_lines[4], " - implemented day logs")
