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
    re.compile(r"E741 ambiguous variable name 'l'")
)


def should_ignore(line):
    for r in re_ignores:
        if r.search(line):
            return True
    return False


basedir = os.path.dirname(__file__)
if not basedir:
    basedir = os.getcwd()
basedir = os.path.abspath(os.path.join(basedir, ".."))


def run_check(*args, **kw):
    kw["stdout"] = subprocess.PIPE
    kw["stderr"] = subprocess.PIPE

    extra_env = kw.pop("extra_env", None)
    if extra_env is not None:
        if "env" not in kw:
            kw["env"] = dict(os.environ)
        kw["env"].update(extra_env)

    p = subprocess.Popen(args, **kw)
    stdout, stderr = p.communicate()
    stdout = stdout.decode("utf-8")
    stderr = stderr.decode("utf-8")
    count = 0
    for l in stdout.split("\n"):
        if not l:
            continue
        if should_ignore(l):
            continue
        print("I:{}:{}".format(args[0], l))
        count += 1
    for l in stderr.split("\n"):
        if not l:
            continue
        if should_ignore(l):
            continue
        print("W:{}:{}".format(args[0], l))
        count += 1
    p.wait()
    return count


class TestLinters(unittest.TestCase):
    """ ensure that the tree is pep8 clean """

    def test_flake8_clean(self):
        self.assertEqual(run_check("flake8", basedir), 0)

    @unittest.skipIf("SKIP_MYPY" in os.environ, "SKIP_MYPY is set in the environment")
    def test_mypy_clean(self):
        stubs_dir = os.path.join(basedir, "stubs")
        self.assertEqual(run_check("mypy", basedir, "--no-error-summary", extra_env={"MYPYPATH": stubs_dir}), 0)
