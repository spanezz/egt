# coding: utf8

import re
import sys
import shlex
import taskw


class Line:
    """
    One line of text
    """
    def __init__(self, line):
        self.line = line

    def print(self, file):
        print(self.line, file=file)


class Task:
    """
    A TaskWarrior task
    """
    def __init__(self, body, id, indent="", text=None, task=None):
        # Body object owning this Task
        self.body = body
        # Indentation at the beginning of the lines
        self.indent = indent
        # Taskwarrior task dict (None means no mapping attempted yet)
        self.task = task
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
            for word in shlex.split(text):
                if word.startswith("+"):
                    tags.add(word[1:])
                else:
                    desc.append(word)

            # Rebuild the description
            self.desc = " ".join(shlex.quote(x) for x in desc)

            # Tags
            self.tags = tags
        else:
            raise ValueError("One of text or task must be provided")

        # If True, then we lost the mapping with TaskWarrior
        self.is_orphan = False

    def create(self):
        """
        Create the task in TaskWarrior
        """
        if not self.is_new: return
        tags = self.body.project.tags | self.tags
        self.task = self.body.tw.task_add(self.desc, project=self.body.project.name, tags=sorted(tags))
        self.id = self.task["id"]
        self.is_new = None

    def resolve_task(self):
        """
        Resolve a task ID from a project file into a TaskWarrior task.

        Returns None if no mapping has been found.
        """
        # If it is new, nothing to do
        if self.is_new: return

        # Try to resolve id into UUID
        tasks = self.body.project.state.get("tasks")
        ids = None
        if tasks is not None:
            ids = tasks.get("ids", None)
            uuid = ids.get(str(self.id), None)
            if uuid is not None:
                id, task = self.body.tw.get_task(uuid=uuid)
                if task:
                    self.task = task
                    self.id = task["id"] if task["id"] != 0 else None
                    self.desc = task["description"]
                    bl = self.body.project.tags
                    self.tags = set(t for t in task["tags"] if t not in bl) if "tags" in task else set()
                    return

        # Looking up by uuid failed, try looking up by description
        id, task = self.body.tw.get_task(description=self.desc)
        if task:
            self.task = task
            return

        # Mapping to taskwarrior failed: mark this task as orphan, so
        # it can be indicated when serializing
        self.is_orphan = True

    def print(self, file):
        res = []
        if self.is_orphan:
            res.append("- [orphan]")
        elif self.task["id"] == 0:
            res.append("-")
        else:
            res.append("t{}".format(self.id))
        if self.task:
            res.append("[{:%Y-%m-%d %H:%M} {}]".format(self.task["modified"], self.task["status"]))
        res.append(self.desc)
        bl = self.body.project.tags
        res.extend("+" + t for t in sorted(self.tags) if t not in bl)
        print(self.indent + " ".join(res), file=file)


class Body:
    re_task = re.compile(r"^(?P<indent>\s*)t(?P<id>\d*)\s+(?P<text>.+)$")

    def __init__(self, project):
        self.project = project

        # Line number in the project file where the body starts
        self._lineno = None

        # Text lines for the project body
        self.content = []

        # Just the Task entries, for easy access
        self.tasks = []

        # Taskwarrior interface, loaded lazily
        self._tw = None

    def force_load_tw(self, **kw):
        """
        Force lazy loading of TaskWarrior object, possibly with custom extra
        arguments.

        This is used in tests to instantiate TaskWarrior objects pointing to
        the test TaskWarrior configuration.
        """
        self._tw = taskw.TaskWarrior(marshal=True, **kw)

    @property
    def tw(self):
        if self._tw is None:
            self._tw = taskw.TaskWarrior(marshal=True)
        return self._tw

    def parse(self, lines):
        self._lineno = lines.lineno

        # Get everything until we reach the end of file
        while True:
            l = lines.next()
            # Stop at an empty line or at EOF
            if l is None: break
            mo = self.re_task.match(l)
            if mo is not None:
                task = Task(self, **mo.groupdict())
                self.content.append(task)
                self.tasks.append(task)
            else:
                self.content.append(Line(l))

    def sync_tasks(self):
        """
        Sync the tasks in the body with TaskWarrior
        """
        # Load task information from TaskWarrior, for tasks that are already in
        # TaskWarrior
        for t in self.tasks:
            t.resolve_task()

        # Iterate self.tasks creating new tasks in taskwarrior
        for t in self.tasks:
            if t.is_new:
                t.create()

        # Collect known task UUIDs
        known_uuids = set()
        for t in self.tasks:
            if t.task is None: continue
            known_uuids.add(str(t.task["uuid"]))

        # Add all the Taskwarrior tasks not present in self.tasks
        new = []
        for task in self.tw.filter_tasks({"project": self.project.name}):
            if task["id"] == 0 or str(task["uuid"]) in known_uuids: continue
            task = Task(self, task["id"], task=task)
            new.append(task)

        # If we created new content, prepend it to self.tasks and self.content
        if new:
            self.tasks[0:0] = new
            new.append(Line(""))
            self.content[0:0] = new

        # Rebuild state and save it
        ids = {}
        for t in self.tasks:
            if t.is_orphan: continue
            if t.id is None: continue
            ids[t.id] = str(t.task["uuid"])
        self.project.state.set("tasks", {"ids": ids})

    def print(self, file):
        """
        Write the body as a project body section to the given output file.

        Returns True if the body section was printed, False if there was
        nothing to print.
        """
        # Print the rest of the known contents
        for el in self.content:
            el.print(file=file)
        return True
