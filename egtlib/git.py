from __future__ import annotations

import logging
import os
import re

import git

from . import project
from .log import Entry

log = logging.getLogger(__name__)

re_gitsha = re.compile(r"^\s+- \[git:(?P<sha>[a-f0-9]{4,})\]\s+")


def collect_achievements(proj: "project.Project", entry: Entry):
    """
    Add to a log Entry one line for each commit that happened during the entry
    time span
    """
    if not os.path.exists(os.path.join(proj.path, ".git")):
        return

    # Build a list of short shasums that we already added
    seen = []
    for line in entry.body:
        mo = re_gitsha.match(line)
        if mo:
            seen.append(mo.group("sha"))

    repo = git.Repo(proj.path)
    gitconfig = repo.config_reader()
    my_email = gitconfig.get_value("user", "email", "NOPE")
    abbrev_size = int(gitconfig.get_value("core", "abbrev", "7"))
    cutoff = entry.begin.timestamp()
    new_lines = []
    for c in repo.iter_commits():
        if c.author.email != my_email:
            continue
        if c.authored_date < cutoff:
            break
        # Break at the point where things are already known in the log, to
        # avoid readding old entries that have been manually deleted
        if any(c.hexsha.startswith(x) for x in seen):
            break

        new_lines.append(" - [git:{sha}] {desc}".format(
            sha=c.hexsha[:abbrev_size],
            desc=c.summary))
    entry.body.extend(new_lines[::-1])
