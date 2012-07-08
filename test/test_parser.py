import unittest
import os
import os.path
from egtlib import egtparser

class TestAnnotator(unittest.TestCase):
    """
    Test scan results
    """
    def test_indent(self):
        sample = [
            "zero",
            " one",
            "  two",
            "",
            " one",
            " - three",
            "   three",
        ]
        self.assertEquals([x[0] for x in egtparser.annotate_with_indent_and_markers(sample)],
                          [0, 1, 2, 0, 1, 3, 3])

    def test_markers(self):
        sample = [
            "none",
            "",
            " - dash",
            " * star",
        ]
        self.assertEquals([x[1] for x in egtparser.annotate_with_indent_and_markers(sample)],
                          [None, ' ', '-', '*'])

    def test_manyfeatures(self):
        sample = [
            "foo",
            "  bar",
            " - foo",
            "   bar",
            "",
            "   baz",
            "",
            " - foo",
            "",
            "bar",
        ]
        sample = list(x[:2] for x in egtparser.annotate_with_indent_and_markers(sample))
        self.assertEquals(sample, [
            (0, None),
            (2, None),
            (3, '-'),
            (3, None),
            (3, ' '),
            (3, None),
            (0, ' '),
            (3, '-'),
            (0, ' '),
            (0, None),
        ])

