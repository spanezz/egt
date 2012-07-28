import unittest
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


class TestParser(unittest.TestCase):
    def test_simple(self):
        sample = []
        parsed = egtparser.BodyParser(sample).parse_body()
        self.assertEquals(parsed, [])

    def test_spacers(self):
        sample = ["", "", ""]
        parsed = egtparser.BodyParser(sample).parse_body()
        self.assertEquals([x.TAG for x in parsed], ["spacer"])

    def test_freeform(self):
        sample = ["foo", "bar"]
        parsed = egtparser.BodyParser(sample).parse_body()
        self.assertEquals([x.TAG for x in parsed], ["freeform"])

    def test_nextactions(self):
        sample = [
            " - contextless",
            " - multiline",
            "   foo",
            "",
            "   bar",
            " - baz",
            "",
            "context:",
            " - foo",
            " - bar",
        ]
        parsed = egtparser.BodyParser(sample).parse_body()
        self.assertEquals([x.TAG for x in parsed], ["next-actions", "spacer", "next-actions"])

    def test_somedaymaybe(self):
        sample = [
            " * title",
            "someday, maybe",
            "",
            "someday, maybe"
        ]
        parsed = egtparser.BodyParser(sample).parse_body()
        self.assertEquals([x.TAG for x in parsed], ["someday-maybe"])

    def test_mixed(self):
        sample = [
            "Remember, remember, the 5th of November!",
            "context, context1:",
            " - foo",
            " - bar",
            "",
            "context:",
            " - foo",
            " - bar",
            " * title",
            "",
            "someday, maybe",
        ]
        parsed = egtparser.BodyParser(sample).parse_body()
        self.assertEquals([x.TAG for x in parsed], ["freeform", "next-actions", "spacer", "next-actions", "someday-maybe"])
        self.assertEquals(sorted(parsed[1].contexts), ["context", "context1"])
