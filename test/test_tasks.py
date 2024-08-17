from __future__ import annotations

import datetime
import io
import json
import os
import unittest

import taskw
from dateutil.tz import tzlocal

from .utils import ProjectTestMixin


class TestTasks(ProjectTestMixin, unittest.TestCase):
    DEFAULT_META = {
        "Name": "testprj",
        "Tags": "testtag1, testtag2",
    }

    DEFAULT_LOG = [
        "2016",
        "15 march: 9:30-",
        " - wrote more unit tests",
    ]

    def testCreateFromEgt(self):
        """
        Test creation of new taskwarrior tasks from a project file
        """
        proj = self.project(
            body=[
                "body line1",
                "t new parent task",
                "  t new taskwarrior task +tag",
                "body line3",
            ]
        )

        self.assertEqual(len(proj.body.content), 4)
        self.assertEqual(len(proj.body.tasks), 2)
        self.assertEqual(proj.body.tasks[0], proj.body.content[1])
        self.assertEqual(proj.body.tasks[1], proj.body.content[2])
        task = proj.body.tasks[1]
        self.assertEqual(task.indent, "  ")
        self.assertIsNone(task.task)
        self.assertTrue(task.is_new)
        self.assertIsNone(task.id)
        self.assertEqual(task.desc, "new taskwarrior task")
        self.assertEqual(task.tags, {"tag"})
        self.assertFalse(task.is_orphan)

        proj.body.tasks.sync_tasks()

        self.assertIsNotNone(task.task)
        self.assertFalse(task.is_new)
        self.assertIsNotNone(task.id)
        self.assertEqual(task.task["description"], "new taskwarrior task")
        self.assertEqual(task.task["tags"], ["tag", "testtag1", "testtag2"])
        self.assertEqual(task.task["project"], "testprj")

        with io.StringIO() as out:
            proj.body.print(out)
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 4)
        self.assertEqual(body_lines[0], "body line1")
        self.assertRegex(body_lines[1], r"^t\d+ \[[^]]+\] new parent task$")
        self.assertRegex(body_lines[2], r"^  t\d+ \[[^]]+\] new taskwarrior task \+tag$")
        self.assertEqual(body_lines[3], "body line3")

        with (self.workdir / "project-testprj.json").open("r") as fd:
            state = json.load(fd)
        tasks = state["tasks"]
        ids = tasks["ids"]
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[str(task.task["id"])], str(task.task["uuid"]))

    def testCreateFromEgtWithAttributes(self):
        """
        Test creation of new taskwarrior tasks with attributes from a project file
        """
        datedata = datetime.datetime(2031, 1, 2, 0, 0, tzinfo=tzlocal())
        test_attributes = [
            ("due", "2031-01-02", datedata),
            ("wait", "2031-01-02", datedata),
            ("start", "2031-01-02", datedata),
            ("until", "2031-01-02", datedata),
            ("scheduled", "2031-01-02", datedata),
            ("priority", "H", "H"),
            ("due", "2030-12-26+week", datedata),
        ]
        for key, value, data in test_attributes:
            attr = f"{key}:{value}"
            with self.subTest(config=attr):
                proj = self.project(
                    body=[
                        "body line1",
                        "t new test task " + attr,
                        "body line3",
                    ]
                )

                task = proj.body.tasks[0]
                self.assertIsNone(task.task)
                self.assertTrue(task.is_new)
                self.assertIsNone(task.id)
                self.assertEqual(task.desc, "new test task")
                self.assertEqual(task.attributes, {key: value})

                proj.body.tasks.sync_tasks()

                self.assertIsNotNone(task.task)
                self.assertFalse(task.is_new)
                self.assertIsNotNone(task.id)
                self.assertEqual(task.task["description"], "new test task")
                self.assertEqual(task.task[key], data)

    def testCreateFromTW(self):
        """
        Test import of new taskwarrior tasks in egt
        """

        tw = taskw.TaskWarrior(marshal=True, config_filename=self.taskrc)
        new_task = tw.task_add("new task", ["tag", "testtag1"], project="testprj")
        tw.task_add("new parent task", project="testprj", depends=[new_task["uuid"]])
        del tw

        proj = self.project(
            body=[
                "body line1",
                "body line2",
            ]
        )

        self.assertEqual(len(proj.body.content), 2)
        self.assertEqual(len(proj.body.tasks), 0)

        proj.body.tasks.sync_tasks()

        self.assertEqual(len(proj.body.content), 5)
        self.assertEqual(len(proj.body.tasks), 2)

        task = proj.body.tasks[0]
        self.assertIsNotNone(task.task)
        self.assertFalse(task.is_new)
        self.assertIsNotNone(task.id)
        self.assertEqual(task.task["description"], "new task")
        self.assertEqual(task.task["tags"], ["tag", "testtag1"])
        self.assertEqual(task.task["project"], "testprj")

        with io.StringIO() as out:
            proj.body.print(out)
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)

        self.assertRegex(body_lines[0], r"^t\d+ \[[^]]+\] new task \+tag$")
        self.assertRegex(body_lines[1], r"^t\d+ \[[^]]+\] new parent task depends:1$")
        self.assertEqual(body_lines[2], "")
        self.assertEqual(body_lines[3], "body line1")
        self.assertEqual(body_lines[4], "body line2")

        with (self.workdir / "project-testprj.json").open("r") as fd:
            state = json.load(fd)
        tasks = state["tasks"]
        ids = tasks["ids"]
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[str(task.task["id"])], str(task.task["uuid"]))

    def testSyncExisting(self):
        """
        Test handling of tasks present both in taskwarrior and in egt
        """

        tw = taskw.TaskWarrior(marshal=True, config_filename=self.taskrc)
        new_task = tw.task_add("task", ["tag", "testtag1"], project="testprj")
        del tw

        egt_id = new_task["id"] + 10

        # Add the task to egt's state using a different number than taskwarrior
        # has
        with (self.workdir / "project-testprj.json").open("w") as fd:
            json.dump(
                {
                    "tasks": {
                        "ids": {
                            egt_id: str(new_task["uuid"]),
                        }
                    }
                },
                fd,
                indent=1,
            )

        proj = self.project(
            body=[
                "body line1",
                f" t{egt_id} foo the bar",
                "body line3",
            ]
        )

        self.assertEqual(len(proj.body.content), 3)
        self.assertEqual(len(proj.body.tasks), 1)
        self.assertEqual(proj.body.tasks[0], proj.body.content[1])
        task = proj.body.tasks[0]
        self.assertEqual(task.indent, " ")
        self.assertIsNone(task.task)
        self.assertFalse(task.is_new)
        self.assertEqual(task.id, egt_id)
        self.assertEqual(task.desc, "foo the bar")
        self.assertEqual(task.tags, set())
        self.assertFalse(task.is_orphan)

        proj.body.tasks.sync_tasks()

        self.assertEqual(len(proj.body.tasks), 1)
        self.assertEqual(task, proj.body.tasks[0])

        self.assertIsNotNone(task.task)
        self.assertFalse(task.is_new)
        self.assertEqual(task.id, new_task["id"])
        self.assertEqual(task.task["description"], "task")
        self.assertEqual(task.task["tags"], ["tag", "testtag1"])
        self.assertEqual(task.task["project"], "testprj")

        with io.StringIO() as out:
            proj.body.print(out)
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 3)
        self.assertEqual(body_lines[0], "body line1")
        self.assertRegex(body_lines[1], r"^ t\d+ \[[^]]+\] task \+tag$")
        self.assertEqual(body_lines[2], "body line3")

        with (self.workdir / "project-testprj.json").open("r") as fd:
            state = json.load(fd)
        tasks = state["tasks"]
        ids = tasks["ids"]
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[str(task.task["id"])], str(task.task["uuid"]))

    def testSyncDone(self):
        """
        Test handling of tasks present both in taskwarrior and in egt, when a
        task is marked done on taskwarrior
        """

        tw = taskw.TaskWarrior(marshal=True, config_filename=self.taskrc)
        new_task = tw.task_add("task", ["tag", "testtag1"], project="testprj")

        egt_id = new_task["id"] + 10

        # Add the task to egt's state using a different number than taskwarrior
        # has
        with (self.workdir / "project-testprj.json").open("w") as fd:
            json.dump(
                {
                    "tasks": {
                        "ids": {
                            egt_id: str(new_task["uuid"]),
                        }
                    }
                },
                fd,
                indent=1,
            )

        # Mark the task as done
        tw.task_done(uuid=new_task["uuid"])
        del tw

        # Load the project and see
        proj = self.project(
            body=[
                "body line1",
                f" t{egt_id} foo the bar",
                "body line3",
            ]
        )

        self.assertEqual(len(proj.body.content), 3)
        self.assertEqual(len(proj.body.tasks), 1)
        self.assertEqual(proj.body.tasks[0], proj.body.content[1])
        task = proj.body.tasks[0]
        self.assertEqual(task.indent, " ")
        self.assertIsNone(task.task)
        self.assertFalse(task.is_new)
        self.assertEqual(task.id, egt_id)
        self.assertEqual(task.desc, "foo the bar")
        self.assertEqual(task.tags, set())
        self.assertFalse(task.is_orphan)

        proj.body.tasks.sync_tasks()

        self.assertEqual(len(proj.body.tasks), 1)
        self.assertEqual(task, proj.body.tasks[0])

        self.assertIsNotNone(task.task)
        self.assertFalse(task.is_new)
        self.assertIsNone(task.id)
        self.assertEqual(task.task["description"], "task")
        self.assertEqual(task.task["tags"], ["tag", "testtag1"])
        self.assertEqual(task.task["project"], "testprj")

        with io.StringIO() as out:
            proj.body.print(out)
            body_lines = out.getvalue().splitlines()

        self.assertEqual(len(body_lines), 5)
        self.assertRegex(body_lines[0], r"[0-9]{1,2} [A-z]*:")
        self.assertEqual(body_lines[1], "  - [completed] task")
        self.assertEqual(body_lines[2], "")
        self.assertEqual(body_lines[3], "body line1")
        self.assertEqual(body_lines[4], "body line3")

        with (self.workdir / "project-testprj.json").open("r") as fd:
            state = json.load(fd)
        tasks = state["tasks"]
        ids = tasks["ids"]
        self.assertEqual(len(ids), 0)
