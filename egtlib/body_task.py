from __future__ import annotations

import re
import shlex
from typing import TYPE_CHECKING, Optional, Union

# import taskw

from .body import BodyEntry

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
            body: "Body",
            id: Union[int, str],
            indent: str = "",
            text: Optional[str] = None,
            task=None) -> None:
        # Body object owning this Task
        self.body = body
        # Indentation at the beginning of the lines
        self.indent = indent
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

    def create(self):
        """
        Create the task in TaskWarrior
        """
        if not self.is_new:
            return
        tags = self.body.project.tags | self.tags
        # the following lines are a workaround for https://github.com/ralphbean/taskw/issues/111
        self.body.tw._marshal = False
        newtask = self.body.tw.task_add(self.desc, project=self.body.project.name, tags=sorted(tags), **self.attributes)
        self.body.tw._marshal = True
        id, task = self.body.tw.get_task(uuid=newtask["id"])
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
                id, task = self.body.tw.get_task(uuid=uuid)
                if task:
                    self.set_twtask(task)
                    self.id = task["id"] if task["id"] != 0 else None
                    self.desc = task["description"]
                    bl = self.body.project.tags
                    self.tags = set(t for t in task["tags"] if t not in bl) if "tags" in task else set()
                    return

        # Looking up by uuid failed, try looking up by description
        id, task = self.body.tw.get_task(description=self.desc)
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
                self.depends = set(self.body.tw.get_task(uuid=t)[0] for t in depends_uuids)

    def print(self, file):
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
                return
            res.append("[{:%Y-%m-%d %H:%M} {}]".format(self.task["modified"], self.task["status"]))
        res.append(self.desc)
        bl = self.body.project.tags
        res.extend("+" + t for t in sorted(self.tags) if t not in bl)
        if self.depends:
            res.append("depends:" + ",".join(str(t) for t in sorted(self.depends)))
        print(self.indent + " ".join(res), file=file)
