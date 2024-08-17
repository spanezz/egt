from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, cast

try:
    import coloredlogs

    HAS_COLOREDLOGS = True
except ModuleNotFoundError:
    HAS_COLOREDLOGS = False


def _get_first_docstring_line(obj: Any) -> str | None:
    try:
        return cast(str, obj.__doc__.split("\n")[1].strip())
    except (AttributeError, IndexError):
        return None


class Fail(BaseException):
    """
    Failure that causes the program to exit with an error message.

    No stack trace is printed.
    """


class Command:
    """
    Base class for actions run from command line
    """

    NAME: str | None = None

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.setup_logging()

    @classmethod
    def command_name(cls) -> str:
        if cls.NAME is not None:
            return cls.NAME
        else:
            return cls.__name__.lower()

    def setup_logging(self) -> None:
        FORMAT = "%(asctime)-15s %(levelname)s %(name)s %(message)s"
        if self.args.debug:
            level = logging.DEBUG
        elif self.args.verbose:
            level = logging.INFO
        else:
            level = logging.WARN

        if HAS_COLOREDLOGS:
            coloredlogs.install(level=level, fmt=FORMAT)
        else:
            logging.basicConfig(level=level, stream=sys.stderr, format=FORMAT)

    @classmethod
    def add_subparser(cls, subparsers: argparse._SubParsersAction[Any]) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            cls.command_name(),
            help=_get_first_docstring_line(cls),
        )
        parser.set_defaults(command=cls)
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="verbose output",
        ),
        parser.add_argument(
            "--debug",
            action="store_true",
            help="debugging output",
        ),
        return cast(argparse.ArgumentParser, parser)
