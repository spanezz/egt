from __future__ import annotations

import logging
import os
from configparser import ConfigParser
from functools import cached_property
from typing import List, Optional, Tuple

import xdg

log = logging.getLogger(__name__)


class Config:
    """
    Egt configuration
    """
    def __init__(self, load: bool = False):
        self.config = ConfigParser(interpolation=None)  # we want '%' in formats to work directly
        self.config["config"] = {
            "date-format": "%d %B",
            "time-format": "%H:%M",
            "sync-tw-annotations": "True",
            "summary-columns": "name, tags, logs, hours, last",
        }
        if load:
            self.load()

    def load(self) -> None:
        """
        Load configuration from the user's home directory
        """
        # Look for a config file in the old and new locations
        old_cfg = os.path.expanduser("~/.egt.conf")
        new_cfg = os.path.join(xdg.XDG_CONFIG_HOME, "egt")

        # If the configuration exists only in the old location, move it to the
        # new one
        if os.path.isfile(new_cfg):
            if os.path.isfile(old_cfg):
                log.warn(
                    "Config file exists in old an new location.\n"
                    "%s used\n"
                    "%s will be ignored (remove to get rid of this message)\n",
                    new_cfg,
                    old_cfg,
                )
        elif os.path.isfile(old_cfg):
            os.rename(old_cfg, new_cfg)
            log.info("Config file %s moved to new location %s", old_cfg, new_cfg)

        self.config.read([new_cfg])

    @cached_property
    def summary_columns(self) -> list[str]:
        """
        Return the list of columns to show in summary
        """
        raw_cols = self.config.get("config", "summary-columns")
        return [x.strip().lower() for x in raw_cols.split(',')]

    @cached_property
    def backup_output(self) -> str | None:
        """
        Return the default backup file location.

        It may contain strftime escape sequences
        """
        return self.config.get("config", "backup-output", fallback=None)

    @cached_property
    def date_format(self) -> str:
        """
        Return the default date format for use in annotations
        """
        return self.config.get("config", "date-format")

    @cached_property
    def time_format(self) -> str:
        """
        Return the default time format for use in annotations
        """
        return self.config.get("config", "time-format")

    @cached_property
    def sync_tw_annotations(self) -> bool:
        """
        TODO: description missing
        """
        return self.config.getboolean("config", "sync-tw-annotations")

    @cached_property
    def autotag_rules(self) -> list[tuple[str, str]]:
        """
        Return a list of (tag, regexp) autotagging rules
        """
        if "autotag" not in self.config:
            return []
        autotags = self.config["autotag"]
        if autotags is None:
            return []

        return [(tag, regexp) for tag, regexp in autotags.items()]
