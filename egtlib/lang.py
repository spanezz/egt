from typing import Optional, Dict, Type
from contextlib import contextmanager
import dateutil.parser
import logging

log = logging.getLogger(__name__)


class Locale:
    """
    Set the current locale, doing nothing if it is already set
    """
    def __init__(self):
        self.current_locale: Optional[str] = None
        self.cached_parserinfo: Dict[str, Type[dateutil.parser.parserinfo]] = {}

    def set(self, lang: Optional[str]) -> None:
        if self.current_locale == lang:
            return

        import locale
        if lang is None:
            try:
                locale.resetlocale()
                self.current_locale = None
            except locale.Error as e:
                log.warn("Cannot reset locale to the default: %s", e)
        else:
            try:
                locname = locale.normalize(lang + ".UTF-8")
                locale.setlocale(locale.LC_ALL, locname)
                self.current_locale = lang
            except locale.Error as e:
                log.warn("Cannot set locale %s: %s", locname, e)

    @contextmanager
    def temp_set(self, lang: str):
        cur = self.current_locale
        self.set(lang)
        yield
        if cur is not None:
            self.set(cur)

    def get_parserinfo(self, lang: Optional[str]) -> dateutil.parser.parserinfo:
        if lang is None:
            return dateutil.parser.parserinfo()

        res = self.cached_parserinfo.get(lang, None)
        if res is not None:
            return res()

        with self.temp_set(lang):
            import locale

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
                    (locale.nl_langinfo(locale.ABMON_1),  locale.nl_langinfo(locale.MON_1)),
                    (locale.nl_langinfo(locale.ABMON_2),  locale.nl_langinfo(locale.MON_2)),
                    (locale.nl_langinfo(locale.ABMON_3),  locale.nl_langinfo(locale.MON_3)),
                    (locale.nl_langinfo(locale.ABMON_4),  locale.nl_langinfo(locale.MON_4)),
                    (locale.nl_langinfo(locale.ABMON_5),  locale.nl_langinfo(locale.MON_5)),
                    (locale.nl_langinfo(locale.ABMON_6),  locale.nl_langinfo(locale.MON_6)),
                    (locale.nl_langinfo(locale.ABMON_7),  locale.nl_langinfo(locale.MON_7)),
                    (locale.nl_langinfo(locale.ABMON_8),  locale.nl_langinfo(locale.MON_8)),
                    (locale.nl_langinfo(locale.ABMON_9),  locale.nl_langinfo(locale.MON_9)),
                    (locale.nl_langinfo(locale.ABMON_10), locale.nl_langinfo(locale.MON_10)),
                    (locale.nl_langinfo(locale.ABMON_11), locale.nl_langinfo(locale.MON_11)),
                    (locale.nl_langinfo(locale.ABMON_12), locale.nl_langinfo(locale.MON_12)),
                ]

                def __init__(self, dayfirst=True, yearfirst=False):
                    # for non-us dates, set ``dayfirst`` by default
                    super().__init__(dayfirst=dayfirst, yearfirst=yearfirst)

        self.cached_parserinfo[lang] = ParserInfo
        return ParserInfo()


locale = Locale()


def get_parserinfo(lang: Optional[str]) -> dateutil.parser.parserinfo:
    return locale.get_parserinfo(lang)


def set_locale(lang: Optional[str]) -> None:
    return locale.set(lang)
