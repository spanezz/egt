Introduction
------------

I'm a freelance software designer/developer, maintaining various projects for
various customers. I'm also a Debian Developer and I'm involved in various
communities.

Because of how my brain works, and given the number of projects where I'm
active, I need to note down ideas popping up more or less at any time over
various fronts, to keep my brain free of clutter to be able to focus on the
task at hand.

I started keeping a file of random todo items and design notes together with
every project in my filesystem, which slowly evolved with some basic
hand-edited timekeeping.

At some point I ended up among the public of Lars Wirzenius' talk on [Getting
Things Done for Hackers](https://gtdfh.liw.fi/), and started having ideas for
automating some of my tasks:

* I standardized what structure there were in `.egt` files
* My notes files could be used as markers to locate where projects were in the
  filesystem, and quickly open a terminal to work on them (`egt work`)
* Since egt files are not committed in git repositories, I created a way to
  back them up (`egt backup`)
* To help with manual timekeeping, I created `egt annotate` to semi-automate
  some of the hourly calculations while within an editor

Things picked up from there, adding features as my needs evolved and as I
discovered useable structure in my way of keeping notes.


Work-Cycle
----------

I mostly use `egt work` to start working on a project: I use tabbed terminals,
so I get my notes in the first tab, and when creating new tabs I'm already in
the project directory. It's a small thing, but it reduces the energy required
to effectively start working, and that means a lot to me. 

I use `egt edit` to quickly dump notes on a project I'm not working on, to free
my brain from creative churn and either say on focus when I'm focused, or
reduce stress when I'm not.

I use `egt archive` to generate end of month reports for customers.

I use `egt grep` when I remember I implemented something useful and reuseable
in some project, but I don't remember which one.

And while I work, I constantly dump all sorts of thoughts in my notes. The free
and unstructured way of a text file does not require me to organise thoughts
before I jot them down, so I can do it without losing the main stream of
thoughts. I have not found to this day a better way to do it, and I find being
able to do this absolutely invaluable.
