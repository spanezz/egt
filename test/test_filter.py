import unittest
from egtlib.egt import ProjectFilter
from egtlib.project import Project

class TestFilter(unittest.TestCase):
    """
    Test ProjectFilter
    """

    def test_name(self):
        f = ProjectFilter(["foo", "bar"])

        p = Project("/foo/.egt", load=False)
        self.assertTrue(f.matches(p))

        p = Project("/bar/.egt", load=False)
        self.assertTrue(f.matches(p))

        p = Project("/baz/.egt", load=False)
        self.assertFalse(f.matches(p))

    def test_tags(self):
        f = ProjectFilter(["+foo", "-bar"])

        p = Project("/foo/.egt", load=False)
        p.tags = { "foo" }
        self.assertTrue(f.matches(p))

        p = Project("/foo/.egt", load=False)
        p.tags = { "baz" }
        self.assertFalse(f.matches(p))

        p = Project("/foo/.egt", load=False)
        p.tags = { "foo", "baz" }
        self.assertTrue(f.matches(p))

        p = Project("/foo/.egt", load=False)
        p.tags = { "bar", "baz" }
        self.assertFalse(f.matches(p))

        p = Project("/foo/.egt", load=False)
        p.tags = { "foo", "bar" }
        self.assertFalse(f.matches(p))
