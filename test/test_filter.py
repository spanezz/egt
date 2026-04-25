import unittest
from pathlib import Path

from egtlib.egt import ProjectFilter
from egtlib.config import Config
from egtlib.project import Project


def mock_project(
    abspath: Path,
    path: Path | None = None,
    tags: set[str] | None = None,
    config: Config | None = None,
) -> Project:
    """
    Create a mock version of a project.

    This does not necessarily correspond to a file on disk, but data is
    provided explictily.
    """
    p = Project(abspath, config=config if config is not None else Config())
    if path is not None:
        p.path = path
    if tags is not None:
        p.tags = tags
    return p


class TestFilter(unittest.TestCase):
    """
    Test ProjectFilter
    """

    def test_name(self) -> None:
        f = ProjectFilter(["foo", "bar"])

        p = mock_project(Path("foo/.egt"))
        self.assertTrue(f.matches(p))

        p = mock_project(Path("bar/.egt"))
        self.assertTrue(f.matches(p))

        p = mock_project(Path("baz/.egt"))
        self.assertFalse(f.matches(p))

    def test_tags(self) -> None:
        f = ProjectFilter(["+foo", "-bar"])

        p = mock_project(Path("test/.egt"), tags={"foo"})
        self.assertTrue(f.matches(p))

        p = mock_project(Path("test/.egt"), tags={"baz"})
        self.assertFalse(f.matches(p))

        p = mock_project(Path("test/.egt"), tags={"foo", "baz"})
        self.assertTrue(f.matches(p))

        p = mock_project(Path("test/.egt"), tags={"bar", "baz"})
        self.assertFalse(f.matches(p))

        p = mock_project(Path("test/.egt"), tags={"foo", "bar"})
        self.assertFalse(f.matches(p))
