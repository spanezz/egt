# coding: utf8

from collections import OrderedDict
import re

class Meta:
    """
    Metadata about a project.

    This is the first section of the project file, and can be omitted.
    """

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

    def parse(self, lines):
        """
        Parse a metadata section from a Lines object
        """
        ## Parse raw lines

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

        ## Extract well known values

        # Tags
        f = self._raw.get("tags", None)
        if f is not None:
            self.tags.update(re.split("[ ,\t]+", f))
