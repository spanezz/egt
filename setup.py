#!/usr/bin/env python

import sys
import os.path
from distutils.core import setup

for line in open(os.path.join(os.path.dirname(sys.argv[0]),'egt')):
    if line.startswith('VERSION='):
        version = eval(line.split('=')[-1])

setup(name='egt',
      version=version,
      description="Enrico's Getting Things Done script",
#      long_description=''
      author=['Enrico Zini'],
      author_email=['enrico@enricozini.org'],
      url='http://www.enricozini.org/sw/egt/',
      install_requires = [
          "cliapp", "pyxdg",
      ],
      license='GPL',
      platforms='any',
      packages=['egtlib'],
#     py_modules=[''],
      scripts=['egt'],
     )
