import unittest
from pathlib import Path
from egtlib import scan

testdir = Path(__file__).parent


class TestScan(unittest.TestCase):
    """
    Test scan results
    """

    def test_scan(self):
        testdata = testdir / "testdata"
        res = sorted(x.relative_to(testdata) for x in scan(testdata))
        self.assertEqual(
            res,
            [
                Path("baz/egt"),
                Path("foo/.egt"),
                Path("gnu/.egt"),
                Path("onedir/foo.egt"),
                Path("onedir/wibble.egt"),
                Path("onedir/wobble.egt"),
            ],
        )
