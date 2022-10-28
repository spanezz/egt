from __future__ import annotations

import unittest

from .utils import ProjectTestMixin


class TestBody(ProjectTestMixin, unittest.TestCase):
    DEFAULT_META = {
        "Name": "testprj",
        "Tags": "testtag1, testtag2",
    }

    DEFAULT_LOG = [
        "2016",
        "15 march: 9:30-",
        " - wrote more unit tests",
    ]

    def test_empty(self):
        proj = self.project(
            body=[]
        )
        self.assertEqual(proj.body.content, [])
