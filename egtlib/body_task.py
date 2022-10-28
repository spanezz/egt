from __future__ import annotations

import datetime
import re
import shlex
from typing import TYPE_CHECKING, Dict, List, Optional, TextIO, Union, cast

import taskw

from .body import BodyEntry, EmptyLine, Line, BulletListLine

if TYPE_CHECKING:
    from .body import Body


class Task(BodyEntry):
    """
    A TaskWarrior task
    """

    re_attribute = re.compile(r"^(?P<key>[^:]+):(?P<val>[^:]+)$")
    task_attributes = ["start", "due", "until", "wait", "scheduled", "priority"]

    def __init__(
            self,
            body: Body,
            id: Union[int, str],
            indent: str = "",
            text: Optional[str] = None,
            task=None) -> None:
        super().__init__(indent=indent)
        # Body object owning this Task
        self.body = body
        # Taskwarrior task dict (None means no mapping attempted yet)
        self.set_twtask(task)
        self.id: Optional[int]
        if isinstance(id, int):
            # Whether the task is new and needs to be created in TaskWarrior
            self.is_new = False
            # Task ID currently used in egt
            self.id = id
        else:
            self.is_new = not id.isdigit()
            self.id = int(id) if id else None

        if task is not None:
            self.desc = task["description"]
            self.tags = set(task["tags"]) if "tags" in task else set()
        elif text is not None:
            # Parse the text
            desc = []
            tags = set()
            attributes = {}
            for word in shlex.split(text):
                if word.startswith("+"):
                    tags.add(word[1:])
                else:
                    attr = self.re_attribute.match(word)
                    if attr is not None:
                        key, val = attr.groups()
                        if key in self.task_attributes:
                            attributes[key] = val
                        else:
                            desc.append(word)
                    else:
                        desc.append(word)

            # Rebuild the description
            self.desc = " ".join(shlex.quote(x) for x in desc)

            # Tags
            self.tags = tags
            self.attributes = attributes

            # TODO Not handling dependencies from egt yet
            self.depends: set[int] = set()
        else:
            raise ValueError("One of text or task must be provided")

        # If True, then we lost the mapping with TaskWarrior
        self.is_orphan = False

    def __eq__(self, other: object) -> bool:
        if not super().__eq__(other):
            return False
        o = cast(Task, other)
        return self.task == o.task and self.id == o.id and self.is_orphan == o.is_orphan

    def is_empty(self) -> bool:
        return False

    def get_date(self) -> Optional[datetime.date]:
        return None

    def get_content(self) -> str:
        res = []
        if self.is_orphan:
            res.append("- [orphan]")
        elif self.task and self.task["id"] == 0:
            res.append("-")
        elif self.id is None:
            res.append("t")
        else:
            res.append("t{}".format(self.id))
        if self.task:
            if self.task["status"] == "completed":
                return ""
            res.append("[{:%Y-%m-%d %H:%M} {}]".format(self.task["modified"], self.task["status"]))
        res.append(self.desc)
        bl = self.body.project.tags
        res.extend("+" + t for t in sorted(self.tags) if t not in bl)
        if self.depends:
            res.append("depends:" + ",".join(str(t) for t in sorted(self.depends)))
        return " ".join(res)

    def print(self, file: Optional[TextIO] = None) -> None:
        if (content := self.get_content()):
            print(self.indent + content, file=file)

    def create(self):
        """
        Create the task in TaskWarrior
        """
        if not self.is_new:
            return
        tags = self.body.project.tags | self.tags
        # the following lines are a workaround for https://github.com/ralphbean/taskw/issues/111
        self.body.tasks.tw._marshal = False
        newtask = self.body.tasks.tw.task_add(
            self.desc, project=self.body.project.name, tags=sorted(tags), **self.attributes)
        self.body.tasks.tw._marshal = True
        id, task = self.body.tasks.tw.get_task(uuid=newtask["id"])
        self.set_twtask(task)
        self.id = self.task["id"]
        self.is_new = False

    def resolve_task(self):
        """
        Resolve a task ID from a project file into a TaskWarrior task.

        Returns None if no mapping has been found.
        """
        # If it is new, nothing to do
        if self.is_new:
            return

        # Try to resolve id into UUID
        tasks = self.body.project.state.get("tasks")
        ids = None
        if tasks is not None:
            ids = tasks.get("ids", None)
            uuid = ids.get(str(self.id), None)
            if uuid is not None:
                id, task = self.body.tasks.tw.get_task(uuid=uuid)
                if task:
                    self.set_twtask(task)
                    self.id = task["id"] if task["id"] != 0 else None
                    self.desc = task["description"]
                    bl = self.body.project.tags
                    self.tags = set(t for t in task["tags"] if t not in bl) if "tags" in task else set()
                    return

        # Looking up by uuid failed, try looking up by description
        id, task = self.body.tasks.tw.get_task(description=self.desc)
        if task:
            self.set_twtask(task)
            return

        # Mapping to taskwarrior failed: mark this task as orphan, so
        # it can be indicated when serializing
        self.is_orphan = True

    def set_twtask(self, task) -> None:
        self.task = task
        self.depends = set()
        if task:
            if "depends" in task:
                depends_uuids = set(task["depends"])
                self.depends = set(self.body.tasks.tw.get_task(uuid=t)[0] for t in depends_uuids)


class Tasks:
    """
    Handle tasks in a Project Body
    """
    def __init__(self, body: Body):
        self.body = body

        self.date_format = self.body.project.config.date_format

        # Just the Task entries, for easy access
        self.tasks: List[Task] = []

        # Storage for handling annotations
        self._new_log: Dict[str, List[Line]] = {}
        self._known_annotations: List[List[str]] = []  # using list instead of tuple due to json constraints

        # Taskwarrior interface, loaded lazily
        self._tw: Optional[taskw.TaskWarrior] = None

    def __getitem__(self, index: int) -> Task:
        return self.tasks.__getitem__(index)

    def __len__(self) -> int:
        return self.tasks.__len__()

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

    def create_task(self, **kw) -> Task:
        """
        Create a Task
        """
        task = Task(self.body, **kw)
        self.tasks.append(task)
        return task

    def post_parse_hook(self) -> None:
        """
        Function called after the body is parsed
        """
        # load known annotations from state file
        known_annotations = self.body.project.state.get("annotations")
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
            line = BulletListLine(
                indent="  ",
                bullet="- ",
                text="{task['description']}: {annotation}")
            self.new_log(date, line)

    def _sync_completed(self, task) -> None:
        """
        Add log line for completed tasks
        """
        if task["status"] == "completed":
            date = task["modified"].date().strftime(self.date_format)
            line = BulletListLine(
                indent="  ",
                bullet="- ",
                text=f"[completed] {task['description']}")
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
            old_uuids = set(self.body.project.state.get("tasks")["old_uuids"])
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
        for tw_task in self.tw.filter_tasks({"project.is": self.body.project.name}):
            uuid = str(tw_task["uuid"])
            if self.body.project.config.sync_tw_annotations:
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
            task = Task(self.body, tw_task["id"], task=tw_task)
            new.append(task)

        # If we created new task-content, prepend it to self.tasks and self.content
        if new:
            self.tasks[0:0] = new
            self.body.content[0:0] = new + [EmptyLine(indent="")]

        # If we created new log-content, prepend it to self.content
        if self._new_log:
            content: List[BodyEntry] = []
            for key, lines in sorted(self._new_log.items()):
                content.append(Line(indent="", text=key + ":"))
                content += lines
            content.append(EmptyLine(indent=""))
            self.body.content[0:0] = content

        # Rebuild state and save it
        if modify_state:
            ids = {}
            for t in self.tasks:
                if t.is_orphan:
                    continue
                if t.id is None:
                    continue
                ids[t.id] = str(t.task["uuid"])
            self.body.project.state.set("tasks", {"ids": ids, "old_uuids": list(old_uuids)})
            self.body.project.state.set("annotations", self._known_annotations)
