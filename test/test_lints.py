#!/usr/bin/python

import os
import subprocess
import unittest
import re


re_ignores = (
    # pyflakes is too stupid to understand normal __init__.py usage
    re.compile(r"/__init__.py:.+imported but unused"),
    # these pylint warnings insult my sense of good taste
    re.compile(r"E501 line too long"),
    re.compile(r"E701 multiple statements on one line \(colon\)"),
    re.compile(r"E265 block comment should start with"),
    re.compile(r"egtlib/texttable.py:"),
)


def should_ignore(line):
    for r in re_ignores:
        if r.search(line):
            return True
    return False


basedir = os.path.dirname(__file__)
if not basedir: basedir = os.getcwd()
basedir = os.path.abspath(os.path.join(basedir, ".."))


def run_check(*args):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = stdout.decode("utf-8")
    stderr = stderr.decode("utf-8")
    count = 0
    for l in stdout.split("\n"):
        if not l: continue
        if should_ignore(l): continue
        print("I:{}:{}".format(args[0], l))
        count += 1
    for l in stderr.split("\n"):
        if not l: continue
        if should_ignore(l): continue
        print("W:{}:{}".format(args[0], l))
        count += 1
    p.wait()
    return count


#class TestPyflakesClean(unittest.TestCase):
#    """ ensure that the tree is pyflakes clean """
#
#    def test_pyflakes_clean(self):
#        self.assertEqual(run_check("pyflakes", basedir), 0)


class TestPep8Clean(unittest.TestCase):
    """ ensure that the tree is pep8 clean """

    def test_pep8_clean(self):
        self.assertEqual(run_check("pycodestyle", basedir), 0)
