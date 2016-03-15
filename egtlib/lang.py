# coding: utf-8
from __future__ import absolute_import
import dateutil.parser


class ItalianParserInfo(dateutil.parser.parserinfo):
    WEEKDAYS = [
        ("Lun", "Lunedì"),
        ("Mar", "Martedì"),
        ("Mer", "Mercoledì"),
        ("Gio", "Giovedì"),
        ("Ven", "Venerdì"),
        ("Sab", "Sabato"),
        ("Dom", "Domenica"),
    ]
    MONTHS = [
        ("Gen", "Gennaio"),
        ("Feb", "Febbraio"),
        ("Mar", "Marzo"),
        ("Apr", "Aprile"),
        ("Mag", "Maggio"),
        ("Giu", "Giugno"),
        ("Lug", "Luglio"),
        ("Ago", "Agosto"),
        ("Set", "Settembre"),
        ("Ott", "Ottobre"),
        ("Nov", "Novembre"),
        ("Dic", "Dicembre"),
    ]

    def __init__(self, dayfirst=True, yearfirst=False):
        # for german dates, set ``dayfirst`` by default
        super(ItalianParserInfo, self).__init__(dayfirst=dayfirst, yearfirst=yearfirst)

by_lang = dict(
    en=dateutil.parser.parserinfo,
    it=ItalianParserInfo,
)


def get_parserinfo(lang):
    res = by_lang.get(lang, None)
    if res is not None:
        return res()
    return dateutil.parser.parserinfo()
