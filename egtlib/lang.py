from __future__ import annotations

import contextlib
import locale
import logging
from collections.abc import Iterator
from typing import Generator

import dateutil.parser

log = logging.getLogger(__name__)


@contextlib.contextmanager
def set_locale(lang: str | None) -> Generator[None, None, None]:
    if lang is None:
        locname = ""
    else:
        locname = locale.normalize(lang + ".UTF-8")
    orig = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, locname)
        yield
    finally:
        locale.setlocale(locale.LC_ALL, orig)


class Locale:
    """
    Set the current locale, doing nothing if it is already set
    """

    def __init__(self) -> None:
        self.cached_parserinfo: dict[str, type[dateutil.parser.parserinfo]] = {}

    def get_parserinfo(self, lang: str | None) -> dateutil.parser.parserinfo:
        if lang is None:
            return dateutil.parser.parserinfo()

        res = self.cached_parserinfo.get(lang, None)
        if res is not None:
            return res()

        with set_locale(lang):

            class ParserInfo(dateutil.parser.parserinfo):
                WEEKDAYS = [
                    (locale.nl_langinfo(locale.ABDAY_2), locale.nl_langinfo(locale.DAY_2)),
                    (locale.nl_langinfo(locale.ABDAY_3), locale.nl_langinfo(locale.DAY_3)),
                    (locale.nl_langinfo(locale.ABDAY_4), locale.nl_langinfo(locale.DAY_4)),
                    (locale.nl_langinfo(locale.ABDAY_5), locale.nl_langinfo(locale.DAY_5)),
                    (locale.nl_langinfo(locale.ABDAY_6), locale.nl_langinfo(locale.DAY_6)),
                    (locale.nl_langinfo(locale.ABDAY_7), locale.nl_langinfo(locale.DAY_7)),
                    (locale.nl_langinfo(locale.ABDAY_1), locale.nl_langinfo(locale.DAY_1)),
                ]
                MONTHS = [
                    (locale.nl_langinfo(locale.ABMON_1), locale.nl_langinfo(locale.MON_1)),
                    (locale.nl_langinfo(locale.ABMON_2), locale.nl_langinfo(locale.MON_2)),
                    (locale.nl_langinfo(locale.ABMON_3), locale.nl_langinfo(locale.MON_3)),
                    (locale.nl_langinfo(locale.ABMON_4), locale.nl_langinfo(locale.MON_4)),
                    (locale.nl_langinfo(locale.ABMON_5), locale.nl_langinfo(locale.MON_5)),
                    (locale.nl_langinfo(locale.ABMON_6), locale.nl_langinfo(locale.MON_6)),
                    (locale.nl_langinfo(locale.ABMON_7), locale.nl_langinfo(locale.MON_7)),
                    (locale.nl_langinfo(locale.ABMON_8), locale.nl_langinfo(locale.MON_8)),
                    (locale.nl_langinfo(locale.ABMON_9), locale.nl_langinfo(locale.MON_9)),
                    (locale.nl_langinfo(locale.ABMON_10), locale.nl_langinfo(locale.MON_10)),
                    (locale.nl_langinfo(locale.ABMON_11), locale.nl_langinfo(locale.MON_11)),
                    (locale.nl_langinfo(locale.ABMON_12), locale.nl_langinfo(locale.MON_12)),
                ]

                def __init__(self, dayfirst: bool = True, yearfirst: bool = False) -> None:
                    # for non-us dates, set ``dayfirst`` by default
                    super().__init__(dayfirst=dayfirst, yearfirst=yearfirst)

        self.cached_parserinfo[lang] = ParserInfo
        return ParserInfo()


locale_cache = Locale()


def get_parserinfo(lang: str | None) -> dateutil.parser.parserinfo:
    return locale_cache.get_parserinfo(lang)
