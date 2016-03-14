# coding: utf8
import re
import sys
import taskw
import subprocess
import shlex
import logging

log = logging.getLogger(__name__)


class Taskwarrior:
    """
    Next actions, delegated to TaskWarrior
    """
    re_line = re.compile(r"^(?P<indent>\s*)t(?P<id>\d*)\s+(?P<body>.+)$")
    re_created_id = re.compile(r"^Created task (?P<id>\d+)\.$")

    def __init__(self, project):
        self.project = project

        # Line number in the project file where the taskwarrior lines start
        self._lineno = None

        # Taskwarrior lines
        self._lines = []

        # Taskwarrior interface, loaded lazily
        self._tw = None

    @property
    def tw(self):
        if self._tw is None:
            self._tw = taskw.TaskWarrior(marshal=True)
        return self._tw

    def parse(self, lines):
        """
        Parse a metadata section from a Lines object
        """
        # Parse raw lines
        self._lineno = lines.lineno

        # Get everything until we reach an empty line
        while True:
            l = lines.next()
            # Stop at an empty line or at EOF
            if not l: break
            self._lines.append(l)

    def _task_to_line(self, task):
        res = ["t{}".format(task["id"])]
        res.append("[{:%Y-%m-%d %H:%M} {}]".format(task["modified"], task["status"]))
        res.append(task["description"])
        if "tags" in task:
            bl = self.project.tags
            res.extend("+" + t for t in task["tags"] if t not in bl)
        return " ".join(res)

    def _sync_line(self, indent, id, body):
        """
        Returns a line build by syncing the information from a parsed next
        action line with Taskwarrior.

         - If ID is unset, create a new task in taskwarrior using body
         - If ID is set, reload the body from taskwarrior

        Returns None if the line should be deleted.
        """
        if not id:
            desc = []
            tags = self.project.tags
            for word in shlex.split(body):
                if word.startswith("+"):
                    tags.add(word[1:])
                else:
                    desc.append(word)

            task = self.tw.task_add(" ".join(desc), project=self.project.name, tags=sorted(tags))
            id = task["id"]
        else:
            new_id, task = self.tw.get_task(id=int(id))
            if new_id is None:
                log.warn("taskwarrior #%d does not exist", int(id))
                return None, None
            if task["status"] == "deleted":
                return None, None
            id = new_id

        if task["project"] != self.project.name:
            log.warn("taskwarrior #%d has project %s instead of %s", task["id"], task["project"], self.project.name)
            return None, None
        return id, indent + self._task_to_line(task)

    def sync_with_taskwarrior(self):
        """
        Sync next actions lines with Taskwarrior.
        """
        seen = set()
        new_lines = []
        for line in self._lines:
            mo = self.re_line.match(line)
            # Skip lines that we do not recognize
            if not mo:
                # Lines we do not recognize, we leave as is
                new_lines.append(line)
            else:
                id, new_line = self._sync_line(**mo.groupdict())
                if id is None:
                    # Lines with IDs that taskwarrior does not know about, we
                    # remove
                    continue
                else:
                    new_lines.append(new_line)
                    seen.add(id)

        for task in self.tw.filter_tasks({"project": "egt"}):
            if task["id"] in seen: continue
            if task["status"] == "deleted": continue
            new_lines.append(self._task_to_line(task))

        self._lines = new_lines

    def print(self, out):
        """
        Write the next actions as a project next actions section to the given
        output file.

        Returns True if the next actions section was printed, False if there
        was nothing to print.
        """
        if not self._lines: return False
        for line in self._lines:
            print(line, file=out)
        return True

    @classmethod
    def is_start_line(cls, line):
        """
        Check if the line looks like the start of a taskwarrior block
        """
        return cls.re_line.match(line)
