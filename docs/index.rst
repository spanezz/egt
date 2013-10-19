
Egt
================================

.. .. image:: logo.png
..   :name: logo

.. sidebar:: Links

 - `Source code <http://anonscm.debian.org/gitweb/?p=users/enrico/egt.git>`_
.. - `Bug tracker <>`_
.. - `Website <>`_

Egt is a tool to manage todo-list-and-log files scattered around the home directory.



Features
--------

* bash completion
* backup
* cal --          Compute calendar of next actions
* edit --         Open a terminal in a project directory, and edit the project file.
* grep --         Run 'git grep' on all project .git dirs
* list --         List known projects.
* print-log --    Output the log for one or more projects
* scan --         Update the list of known project files, by scanning everything below the home directory.
* serve --        Start a web server for reports
* summary
* term --         Open a terminal in a project directory.
* weekrpt --      Compute weekly reports
* when --         Show next-action lists that intersect the given context set
* work --         Open a terminal in a project directory, and edit the project



Installation
------------

Egt requires Python, Cliapp, Pyxdg, jinja2. It runs on Linux (and might run on other OSes).

Clone git repository, then build a Debian package:
    dpkg-buildpackage -us -uc

Install the egt_<version>_all.deb and python-egtlib_<version>_all.deb packages.

.. Use your distribution packages for security and stability; if your distribution does not have the dependencies you need, try virtualenv.


Usage
-----

* :doc:`manpage`
* :doc:`code`
* :doc:`fileformat`

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
