from __future__ import annotations

import re
from typing import Dict, List, Optional, TextIO

import taskw

from . import project
from .parse import Lines


class BodyEntry:
    """
    Base class for elements that compose a project body
    """

    def print(self, file: Optional[TextIO] = None) -> None:
        raise NotImplementedError("print has been called on raw BodyEntry object")


class Line(BodyEntry):
    """
    One line of text
    """

    def __init__(self, line: str):
        self.line = line

    def print(self, file: Optional[TextIO] = None) -> None:
        print(self.line, file=file)

    def __repr__(self):
        return "Line({})".format(repr(self.line))


class Body:
    """
    The text body of a Project file, as anything that follows the metadata and
    the log
    """

    re_task = re.compile(r"^(?P<indent>\s*)t(?P<id>\d*)\s+(?P<text>.+)$")

    def __init__(self, project: "project.Project"):
        from .body_task import Task

        self.project = project
        self.date_format = self.project.config.date_format

        # Line number in the project file where the body starts
        self._lineno: Optional[int] = None

        # Text lines for the project body
        self.content: List[BodyEntry] = []

        # Just the Task entries, for easy access
        self.tasks: List[Task] = []

        # Storage for handling annotations
        self._new_log: Dict[str, List[Line]] = {}
        self._known_annotations: List[List[str]] = []  # using list instead of tuple due to json constraints

        # Taskwarrior interface, loaded lazily
        self._tw: Optional[taskw.TaskWarrior] = None

    def force_load_tw(self, **kw):
        """
        Force lazy loading of TaskWarrior object, possibly with custom extra
        arguments.

        This is used in tests to instantiate TaskWarrior objects pointing to
        the test TaskWarrior configuration.
        """
        self._tw = taskw.TaskWarrior(marshal=True, **kw)

    @property
    def tw(self) -> taskw.TaskWarrior:
        if self._tw is None:
            self._tw = taskw.TaskWarrior(marshal=True)
        return self._tw

    def parse(self, lines: Lines) -> None:
        from .body_task import Task

        self._lineno = lines.lineno

        # Get everything until we reach the end of file
        for line in lines.rest():
            if (mo := self.re_task.match(line)):
                task = Task(self, **mo.groupdict())
                self.content.append(task)
                self.tasks.append(task)
            else:
                self.content.append(Line(line))

        # load known annotations from state file
        known_annotations = self.project.state.get("annotations")
        if known_annotations:
            self._known_annotations = known_annotations

    def new_log(self, date, line):
        try:
            self._new_log[date].append(line)
        except KeyError:
            self._new_log[date] = [line]

    def _sync_annotations(self, task) -> None:
        """
        Sync annotations between task and TaskWarrior
        """
        try:
            annotations = task["annotations"]
        except KeyError:
            return
        for annotation in annotations:
            entry = [str(task["uuid"]), annotation.entry.isoformat()]  # isoformat as used internally only
            if entry in self._known_annotations:
                continue
            self._known_annotations.append(entry)
            date = annotation.entry.date().strftime(self.date_format)
            line = Line("  - {desc}: {annot}".format(desc=task["description"], annot=annotation))
            self.new_log(date, line)

    def _sync_completed(self, task) -> None:
        """
        Add log line for completed tasks
        """
        if task["status"] == "completed":
            date = task["modified"].date().strftime(self.date_format)
            line = Line(
                "  - [completed] {desc}".format(
                    desc=task["description"],
                )
            )
            self.new_log(date, line)

    def sync_tasks(self, modify_state=True) -> None:
        """
        Sync the tasks in the body with TaskWarrior

        modify_state:
            run updates that will modify the state
              - create new tasks not present in taskwarrior yet
              - store updated uuids and annotations
            if true, the body must be written back to the project file

        """
        from .body_task import Task

        # Load task information from TaskWarrior, for tasks that are already in
        # TaskWarrior
        for t in self.tasks:
            t.resolve_task()

        if modify_state:
            # Iterate self.tasks creating new tasks in taskwarrior
            for t in self.tasks:
                if t.is_new:
                    t.create()

        # Load UUIDs of tasks known to have been completed or deleted
        try:
            old_uuids = set(self.project.state.get("tasks")["old_uuids"])
        except (TypeError, KeyError):
            old_uuids = set()

        # Collect known UUIDs (old tasks + tasks in project-file)
        known_uuids = old_uuids.copy()
        for t in self.tasks:
            if t.task is None:
                continue
            known_uuids.add(str(t.task["uuid"]))

        # Process all tasks known to taskwarrior
        new = []
        for tw_task in self.tw.filter_tasks({"project.is": self.project.name}):
            uuid = str(tw_task["uuid"])
            if self.project.config.sync_tw_annotations:
                self._sync_annotations(tw_task)
            # handle completed and deleted tasks
            if tw_task["id"] == 0 and uuid not in old_uuids:
                self._sync_completed(tw_task)
                old_uuids.add(uuid)
                continue
            # handle reactivated tasks
            if uuid in old_uuids and tw_task["id"] != 0:
                old_uuids.remove(uuid)
                known_uuids.remove(uuid)
            # skip tasks that exist in project-file already
            if uuid in known_uuids:
                continue
            # Add remaining Taskwarrior tasks to project-file
            task = Task(self, tw_task["id"], task=tw_task)
            new.append(task)

        # If we created new task-content, prepend it to self.tasks and self.content
        if new:
            self.tasks[0:0] = new
            self.content[0:0] = new + [Line("")]

        # If we created new log-content, prepend it to self.content
        if self._new_log:
            content = []
            for key, lines in sorted(self._new_log.items()):
                content.append(Line(key + ":"))
                content += lines
            content.append(Line(""))
            self.content[0:0] = content

        # Rebuild state and save it
        if modify_state:
            ids = {}
            for t in self.tasks:
                if t.is_orphan:
                    continue
                if t.id is None:
                    continue
                ids[t.id] = str(t.task["uuid"])
            self.project.state.set("tasks", {"ids": ids, "old_uuids": list(old_uuids)})
            self.project.state.set("annotations", self._known_annotations)

    def print(self, file: TextIO) -> bool:
        """
        Write the body as a project body section to the given output file.

        Returns True if the body section was printed, False if there was
        nothing to print.
        """
        # Print the rest of the known contents
        for el in self.content:
            el.print(file=file)
        return True
