from __future__ import absolute_import
import os
import os.path
import logging

log = logging.getLogger(__name__)

# If one of these files is present, consider it as the start of a source tree
# and do not recurse into subdirs
LEAF_FILE_MARKERS = frozenset((
    "manage.py", "configure.ac", "setup.py", "Rakefile"
))


def is_script(fname):
    """
    Check if a file looks like a script
    """
    with open(fname) as fd:
        if fd.readline().startswith("#!"):
            return True
    return False


def scan(top=os.path.expanduser("~")):
    """
    Generate the pathnames of all project files inside the given directory
    """
    for root, dirs, files in os.walk(top):
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
            elif f == "ore":
                # Legacy 'ore' files (TODO: remove once everyone migrated)
                yield os.path.join(top, root, f)
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
