#!/usr/bin/env python
# coding: utf-8

import sys
import os
import os.path
from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES

for line in open(os.path.join(os.path.dirname(sys.argv[0]),'egt')):
    if line.startswith('VERSION='):
        version = eval(line.split('=')[-1])

# Datafile handling code borrowed from python-django-extensions by Bas van
# Oostveen

# Tell distutils to put the data_files in platform-specific installation
# locations. See here for an explanation:
# http://groups.google.com/group/comp.lang.python/browse_thread/thread/35ec7b2fed36eaec/2105ee4d9e8042cb
for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']

def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join) in a
    platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

def is_data(fname):
    return not (fname.endswith(".py") or fname.endswith(".pyc") or fname.startswith("."))

# Collect data files
data_files = []
for dirpath, dirnames, filenames in os.walk("egtlib"):
    # Ignore dirnames that start with '.'
    if os.path.basename(dirpath).startswith("."):
        continue
    if filenames:
        data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames if is_data(f)]])

setup(name='egt',
      version=version,
      description="Enrico's Getting Things Done script",
#      long_description=''
      author=['Enrico Zini'],
      author_email=['enrico@enricozini.org'],
      url='http://www.enricozini.org/sw/egt/',
      #install_requires = [
      #    "cliapp", "pyxdg",
      #],
      license='GPL',
      platforms='any',
      packages=['egtlib'],
#     py_modules=[''],
      scripts=['egt'],
      data_files=data_files,
     )
