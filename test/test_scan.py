import unittest
import os
import os.path
from egtlib import scan

basedir = os.path.dirname(__file__)
if not basedir:
    basedir = os.getcwd()
basedir = os.path.abspath(os.path.join(basedir, ".."))
testdir = os.path.join(basedir, "test")


class TestScan(unittest.TestCase):
    """
    Test scan results
    """

    def test_scan(self):
        res = sorted([x[len(testdir) + 10:] for x in scan(os.path.join(testdir, "testdata"))])
        self.assertEqual(res, [
            "bar/ore",
            "baz/egt",
            "foo/.egt",
            "gnu/.egt",
            "onedir/foo.egt",
            "onedir/wibble.egt",
            "onedir/wobble.egt",
        ])
