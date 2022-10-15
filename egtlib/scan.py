from __future__ import annotations

import logging
import os
import os.path
from typing import Generator, Set

log = logging.getLogger(__name__)

# If one of these files is present, consider it as the start of a source tree
# and do not recurse into subdirs
LEAF_FILE_MARKERS = frozenset((
    "manage.py", "configure.ac", "setup.py", "Rakefile"
))


def is_script(fname: str) -> bool:
    """
    Check if a file looks like a script
    """
    with open(fname) as fd:
        if fd.readline().startswith("#!"):
            return True
    return False


def scan(top: str) -> Generator[str, None, None]:
    """
    Generate the pathnames of all project files inside the given directory
    """
    # inodes already visited
    seen: Set[int] = set()
    for root, dirs, files in os.walk(top, followlinks=True):
        # Since we follow links, prevent loops by remembering which inodes we
        # visited
        st = os.stat(root)
        if st.st_ino in seen:
            dirs[:] = []
            continue
        else:
            seen.add(st.st_ino)

        #
        # Check files
        #

        is_leaf = False
        has_dot_egt = False
        has_egt = False
        for f in files:
            if f.endswith(".egt"):
                # All .egt files are good
                yield os.path.join(top, root, f)
                if f == ".egt":
                    has_dot_egt = True
            elif f == "egt":
                has_egt = True
            elif f in LEAF_FILE_MARKERS:
                is_leaf = True

        # If 'egt' exists, there is no '.egt' and egt isn't a script, it is
        # good
        if has_egt and not has_dot_egt:
            fname = os.path.join(top, root, 'egt')
            if not is_script(fname):
                yield fname
            else:
                log.debug("scan: skipping script: %s", fname)

        #
        # Perform pruning of subdirs
        #
        if is_leaf:
            log.debug("scan: prune dir %s", root)
            dirs[:] = []
        else:
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".")]
