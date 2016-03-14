# coding: utf8


# TODO: rename in Planning?
class Body:
    def __init__(self):
        # Line number in the project file where the body starts
        self._lineno = None

        # Text lines for the project body
        self.lines = []

    def parse(self, lines):
        self._lineno = lines.lineno

        # Get everything until we reach the end of file
        while True:
            l = lines.next()
            # Stop at an empty line or at EOF
            if l is None: break
            self.lines.append(l)

    def print(self, file):
        """
        Write the body as a project body section to the given output file.

        Returns True if the body section was printed, False if there was
        nothing to print.
        """
        for line in self.lines:
            print(line, file=file)
        return True
