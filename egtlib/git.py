# coding: utf8

import git
import os
import re
import logging

log = logging.getLogger(__name__)

re_gitsha = re.compile("^ - \[git:(?P<sha>[a-f0-9]{4,})\]\s+")


def collect_achievements(proj, entry):
    if not os.path.exists(os.path.join(proj.path, ".git")): return

    # Build a list of short shasums that we already added
    seen = []
    for line in entry.body:
        mo = re_gitsha.match(line)
        if mo: seen.append(mo.group("sha"))

    repo = git.Repo(proj.path)
    gitconfig = repo.config_reader()
    my_email = gitconfig.get_value("user", "email", "NOPE")
    abbrev_size = int(gitconfig.get_value("core", "abbrev", "7"))
    cutoff = entry.begin.timestamp()
    for c in repo.iter_commits():
        if c.author.email != my_email: continue
        if c.authored_date < cutoff: break
        if any(c.hexsha.startswith(x) for x in seen): continue

        entry.body.append(" - [git:{sha}] {desc}".format(
            sha=c.hexsha[:abbrev_size],
            desc=c.summary))
