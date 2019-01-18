from typing import Optional, TextIO, List
from collections import OrderedDict
from .parse import Lines
import re
import sys
import inspect


class Meta:
    """
    Metadata about a project.

    This is the first section of the project file, and can be omitted.
    """
    re_meta_head = re.compile(r"^\w.*:")

    def __init__(self):
        # Line number in the project file where the metadata start
        self._lineno: Optional[int] = None

        # Dict mapping lowercase field names to their string values
        self._raw = OrderedDict()

        # Set of tags for the project
        self.tags = set()

    def get(self, name: str, *args) -> str:
        """
        Get a metadata element by name, optionally with a default.
        """
        if hasattr(self, name):
            return getattr(self, name)
        return self._raw.get(name, *args)

    def set(self, name: str, value: str) -> None:
        """
        Set the value of a metadata element
        """
        self._raw[name.lower()] = value

    def unset(self, name: str) -> None:
        """
        Unset the value of a metadata element, if it exists, otherwise does
        nothing
        """
        self._raw.pop(name.lower(), None)

    def parse(self, lines: Lines) -> None:
        """
        Parse a metadata section from a Lines object
        """
        # Parse raw lines
        self._lineno = lines.lineno

        # Get everything until we reach an empty line
        meta_lines: List[str] = []
        while True:
            # Stop at an empty line or at EOF
            if not lines.peek():
                lines.skip_empty_lines()
                break
            meta_lines.append(lines.next())

        # Parse fields in the same way as email headers
        import email
        for k, v in email.message_from_string("\n".join(meta_lines)).items():
            if v is None:
                continue
            self._raw[k.lower()] = inspect.cleandoc(str(v))

        # Extract well known values

        # Tags
        f = self._raw.get("tags", None)
        if f is not None:
            self.tags.update(re.split(r"[ ,\t]+", f))

    def print(self, file: TextIO = sys.stdout) -> bool:
        """
        Write the metadata as a project metadata section to the given output
        file.

        Returns True if the metadata section was printed, False if there was
        nothing to print.
        """
        res = False
        for name, value in self._raw.items():
            res = True
            if "\n" in value:
                print("{}:".format(name.title()), file=file)
                for line in value.splitlines():
                    print(" " + line, file=file)
            else:
                print("{}: {}".format(name.title(), value.strip()), file=file)
        return res

    @classmethod
    def is_start_line(cls, line: str) -> bool:
        return bool(cls.re_meta_head.match(line))
