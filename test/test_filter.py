import unittest
from egtlib.egt import ProjectFilter
from egtlib.project import Project


class TestFilter(unittest.TestCase):
    """
    Test ProjectFilter
    """

    def test_name(self):
        f = ProjectFilter(["foo", "bar"])

        p = Project(name="foo")
        self.assertTrue(f.matches(p))

        p = Project(name="bar")
        self.assertTrue(f.matches(p))

        p = Project(name="baz")
        self.assertFalse(f.matches(p))

    def test_tags(self):
        f = ProjectFilter(["+foo", "-bar"])

        p = Project(name="foo", tags={"foo"})
        self.assertTrue(f.matches(p))

        p = Project(name="foo", tags={"baz"})
        self.assertFalse(f.matches(p))

        p = Project(name="foo", tags={"foo", "baz"})
        self.assertTrue(f.matches(p))

        p = Project(name="foo", tags={"bar", "baz"})
        self.assertFalse(f.matches(p))

        p = Project(name="foo", tags={"foo", "bar"})
        self.assertFalse(f.matches(p))
