#!/usr/bin/env python3
import sys
import os.path
from setuptools import setup

with open(os.path.join(os.path.dirname(sys.argv[0]), 'egt'), "rt") as fd:
    for line in fd:
        if line.startswith('VERSION ='):
            version = eval(line.split(' = ')[-1])

setup(
    name='egt',
    version=version,
    description="Enrico's Getting Things Done",
    # long_description=''
    author='Enrico Zini',
    author_email='enrico@enricozini.org',
    url='https://github.com/spanezz/egt',
    requires=["pyxdg", "taskw", "dateutil", "texttable", "git"],
    license="http://www.gnu.org/licenses/gpl-3.0.html",
    packages=['egtlib'],
    scripts=['egt'],
)
