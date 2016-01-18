import re


class Regexps(object):
    """
    Repository of precompiled regexps
    """
    event_range = re.compile(r"\s*--\s*")
    meta_head = re.compile(r"^\w.*:")
    log_date = re.compile("^(?:(?P<year>\d{4})|-+\s*(?P<date>.+?))\s*$")
    log_head = re.compile(r"^(?P<date>(?:\S| \d).*?):\s+(?P<start>\d+:\d+)-\s*(?P<end>\d+:\d+)?")
