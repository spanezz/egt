# coding: utf8

from collections import OrderedDict
import re
import sys


class Meta:
    """
    Metadata about a project.

    This is the first section of the project file, and can be omitted.
    """
    re_meta_head = re.compile(r"^\w.*:")

    def __init__(self):
        # Original lines
        self._lines = []

        # Line number in the project file where the metadata start
        self._lineno = None

        # Dict mapping lowercase field names to their string values
        self._raw = {}

        # Set of tags for the project
        self.tags = set()

    def get(self, name, *args):
        """
        Get a metadata element by name, optionally with a default.
        """
        if hasattr(self, name):
            return getattr(self, name)
        return self._raw.get(name, *args)

    def set(self, name, value):
        """
        Set the value of a metadata element
        """
        self._raw[name.lower()] = value

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

        # Parse fields in the same way as email headers
        import email
        for k, v in email.message_from_string("\n".join(self._lines)).items():
            self._raw[k.lower()] = v.strip()

        # Extract well known values

        # Tags
        f = self._raw.get("tags", None)
        if f is not None:
            self.tags.update(re.split("[ ,\t]+", f))

    def print(self, file=sys.stdout):
        """
        Write the metadata as a project metadata section to the given output
        file.

        Returns True if the metadata section was printed, False if there was
        nothing to print.
        """
        # So far, Meta is read only, so we only need to print self._lines
        if not self._lines: return False
        for line in self._lines:
            print(line, file=file)
        return True

    @classmethod
    def is_start_line(cls, line):
        return cls.re_meta_head.match(line)
