from __future__ import annotations

import logging
import os
import os.path
from collections.abc import Generator
from pathlib import Path

log = logging.getLogger(__name__)

# If one of these files is present, consider it as the start of a source tree
# and do not recurse into subdirs
LEAF_FILE_MARKERS = frozenset(
    (
        "manage.py",
        "configure.ac",
        "setup.py",
        "Rakefile",
        "meson.build",
    )
)


def is_script(fname: Path) -> bool:
    """
    Check if a file looks like a script
    """
    with fname.open() as fd:
        return fd.read(2) == "#!"


def scan(top: Path) -> Generator[Path, None, None]:
    """
    Generate the pathnames of all project files inside the given directory
    """
    # inodes already visited
    seen: set[int] = set()
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
                yield top / root / f
                if f == ".egt":
                    has_dot_egt = True
            elif f == "egt":
                has_egt = True
            elif f in LEAF_FILE_MARKERS:
                is_leaf = True

        # If 'egt' exists, there is no '.egt' and egt isn't a script, it is
        # good
        if has_egt and not has_dot_egt:
            fname = top / root / "egt"
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
