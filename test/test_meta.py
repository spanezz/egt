import unittest
from egtlib.meta import Meta
from egtlib.parse import Lines
import io

TEST_META1 = (
    "Field: value\n"
    "lowercase: value1  \n"
    "UPPERCASE:  value2 \n"
    "multiline: \n"
    "  foobar\n"
    "   baz\n"
    "tags:  a,  b,  c \n"
    "\n"
    "2019\n"
)

TEST_META_SHORT = (
    "Name: test\n"
)


class TestMeta(unittest.TestCase):
    def test_parse(self):
        lines = Lines("test/.egt", io.StringIO(TEST_META1))
        meta = Meta()
        meta.parse(lines)

        self.assertEqual(meta._lineno, 0)
        self.assertEqual(meta._raw, {
            "field": "value",
            "lowercase": "value1",
            "uppercase": "value2",
            "multiline": "foobar\n baz",
            "tags": "a,  b,  c",
        })
        self.assertEqual(meta.tags, {"a", "b", "c"})
        self.assertEqual(lines.peek(), "2019")

    def test_get(self):
        meta = Meta()
        meta.parse(Lines("test/.egt", io.StringIO(TEST_META1)))
        self.assertEqual(meta.get("field"), "value")
        self.assertEqual(meta.get("lowercase"), "value1")
        self.assertEqual(meta.get("uppercase"), "value2")
        self.assertEqual(meta.get("multiline"), "foobar\n baz")
        self.assertEqual(meta.get("tags"), {"a", "b", "c"})

    def test_set(self):
        meta = Meta()
        meta.parse(Lines("test/.egt", io.StringIO(TEST_META_SHORT)))

        meta.set("Foo", "bar")
        self.assertEqual(meta.get("foo"), "bar")

        meta.set("Multiline", "line1\nline2\n")
        self.assertEqual(meta.get("multiline"), "line1\nline2\n")

        out = io.StringIO()
        meta.print(out)
        self.assertEqual(out.getvalue().splitlines(), [
            "Name: test",
            "Foo: bar",
            "Multiline:",
            " line1",
            " line2",
        ])

        out.seek(0)
        meta = Meta()
        meta.parse(Lines("test/.egt", out))
        self.assertEqual(meta.get("name"), "test")
        self.assertEqual(meta.get("foo"), "bar")
        self.assertEqual(meta.get("multiline"), "line1\nline2")

    def test_print(self):
        meta = Meta()
        meta.parse(Lines("test/.egt", io.StringIO(TEST_META1)))
        out = io.StringIO()
        meta.print(out)
        self.assertEqual(out.getvalue().splitlines(), [
            "Field: value",
            "Lowercase: value1",
            "Uppercase: value2",
            "Multiline:",
            " foobar",
            "  baz",
            "Tags: a,  b,  c",
        ])
