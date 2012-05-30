from __future__ import absolute_import
import os.path
import subprocess

class Project(object):
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)

    def from_cp(self, cp):
        """
        Load information about this Project from a ConfigParser
        """
        secname = "dir %s" % self.path
        if not cp.has_section(secname):
            return

        if cp.has_option(secname, "name"):
            self.name = cp.get(secname, "name")

    def to_cp(self, cp):
        """
        Store information about this Project in a ConfigParser
        """
        secname = "dir %s" % self.path
        cp.add_section(secname)
        cp.set(secname, "name", self.name)

    def spawn_terminal(self, with_editor=False):
        with open("/dev/null", "rw+") as devnull:
            cmdline = [
                "x-terminal-emulator",
                "--working-directory=" + self.path
            ]
            if with_editor:
                cmdline.append("-e")
                cmdline.append("vim ore")
            p = subprocess.Popen(cmdline, stdin=devnull, stdout=devnull, stderr=devnull, cwd=self.path, close_fds=True)

