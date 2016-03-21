# egt project file format

## File naming

* `project_name/.egt`.
* `project_name.egt`: to have multiple project files in the same directory.
* `project_name/ore`: legacy, deprecated.


## Metadata

Any `Field: value` line at the start of the file is parsed as metadata. An
empty line ends the metadata section.

The exact format is the same as in email headers, so multiline values are
supported just as in email headers.

The metadata section can be missing.

Known metadata fields:

 * `Path: absolute path` (TODO: use os.path.expanduer)
   The path of the project work directory, if it's not the same as the log/todo file
 * `Abstract: true`
   If Abstract is set to true, it means that the project has no work directory,
   so no attempt is made, for example, to interact with git. This can be useful
   for things like personal planning, or shopping lists.
 * `Archived: true`
   A project that is considered closed and is not shown by default.
   Archived projects automatically get their end date appended to the project
   name.
 * `Name: name`
   The project name. The file or directory names are used as defaults, but can
   be overridden with this field if needed.
 * `Tags: name, name`
   Comma or space separated list of tags for this project.
 * `Editor: name`
   Editor to use for this project. Defaults to $EDITOR from the environment, if
   defined, or else 'vim'.
 * `Start-date: date`
   Official start date of the project. Default: the first log date.
 * `End-date: date`
   Official end date for the project. Default: the last log date.
 * `Lang: code`
   Language used for parsing dates. Only 'it' is supported at the moment.
   English is the default.
 * `Backup: list of paths, one per line`
   When running 'egt backup', also backup the files or directories listed here.
   Paths are relative to the project path.

Metadata fields only used in CV generation, which currently has a very
incomplete implementation:

 * `Issuer: text`
   For projects that are about obtaining some title or cerification, the
   freeform details of the issuer. Only used for 
 * `Description: text`
   Freeform description for the project.
 * `Group-title: text`
   Freeform title for the project, when considered together with all the
   archived projects with the same name.
 * `Title: text`
   Freeform title for the project.
 * `Homepage: url`
   URL to the project home page

## Project log

The log lists all work that has been done on the project.

The log starts with the first non-metadata line, and ends at the first empty
line.

Since the log cannot contain empty lines, in vim it can be skipped simply with
`}`.

The log can contain log *entries*, *time references*, and *annotate commands*.

### Log entries

A log entry represents something you have done, and is usually filled by
cutting and pasting done items from the rest of the project file.

Each log entry starts with a header line that gives the start and end time of
your work on the project, followed by freeform text lines indented by at least
one space.

The header line can be one of:

* `<date>:` the day in which work has been done. I use this for personal
  projects or projects where I do not need to bill by the hour.
* `<date>: <start time>-`, the date and time when I started to work on the
  project. There is no end time, so it means I'm still working on the project.
* `<date>: <start time>-<end-time>[ duration]`, the beginning and end times
  when I've been working on the project.

  Do not worry about `duration`: it is ignored by `egt`, and filled
  automatically by `egt annotate` for your convenience. Billing hours are
  computed exclusively based on start and end time.

The date can be anything you like, according to http://labix.org/python-dateutil/.
Use the "Lang" field in the project metadata to choose the language, if you want
to use day/month names that are not in English.

The times are in the format "hh:mm". The end time can be omitted for the entry
you are currently working on, and it will default to the current time.

If you use a partial date (like "june 28"), the missing bits (like the year)
are taken from the previous entry. You can use *time references* (see below) to
avoid repeating the same information like the year over and over again.

Examples:

```
june 28: 10:00-11:00
 - done something
 - done something else
june 29: 15:45-16:30
 - done something different
```

```
june 28:
 - done something
 - done something else
june 29:
 - done something different
```

```
june 28: 10:00-11:00
 - done something
 - done something else
june 29: 15:45-
 - done something different
 - still working on it
```

### Time references

You can provide a date on a line by itself, introduced by one or more dashes,
to serve as a default for the following log entries. A 4-digit year, without
dashes, also works.

Examples:

```
2012
june 28:
 - done something
 - done something else
june 29:
 - done something different
```

```
--june 2012
28: 10:00-11:00
 - done something
 - done something else
29: 15:45-16:30
 - done something different
```

```
--25 june 2012
thu: 10:00-11:00
- done something
- done something else
fri: 15:45-16:30
- done something different
```

<a name="log_annotate"></a>
### Annotate commands

If you use [`egt annotate`](annotate.md), you can conveniently create new log
entries by writing a special header line at the end of the log:

* `hh:mm` starts a new log entry for today, starting at the given time.
* `+` starts a new log entry for today, whole day, with no start and end times.

For example, if you run this through `egt annotate`:

``
2016
15 January: 14:00-17:00
 - done something
10:00
```

then it becomes (assuming that today is the 16th of March):

``
2016
15 January: 14:00-17:00 3h
 - done something
16 March: 10:00-
```

And if you run this through `egt annotate`:
``
2016
15 January:
 - done something
+
 - done something new
```

then it becomes (assuming that today is the 16th of March):

``
2016
15 January:
 - done something
16 March:
 - done something new
```

Also, at the end of a log entry you can add a `+` to have `egt` fill it with
git commits performed by you in that project during the time span of the log
entry. For example, if I run this through `egt annotate`:

```
16 March:
 - "+" on a line by itself creates a new day-only task entry
 +
```

then it becomes:

```
16 March:
 - "+" on a line by itself creates a new day-only task entry
 - [git:5a443bf] Look for git commits to add to log entries
 - [git:dfe5da2] Only add git entries when there is a + at the end of the open log entry
```

To create a new entry prefilled with git logs, you can either add a `+` line at
the end of the body, or as a shortcut add a `+` at the end of the command, like
`10:00+` or `++`. For example:

```
10:00
 +
+
 +
```

can be written more shortly as:

```
10:00+
++
```

## Project text

After the log you can type anything you like: planning, notes, useful
information, anything.

I normally do planning in the form of bulleted lists, and set vim's indent
level to 3 to quickly indent/deindent items:

```
 - document how project text works
    - document project text intention
    - document taskwarrior integration
```

When an item is done, I cut it from the text and paste it at the end of the
log.


<a name="body_taskwarrior"></a>
### TaskWarrior next actions

A line starting with `t` or `t<number>` where `<number>` is a number, is
interpreted as a TaskWarrior task, and `egt annotate` takes care of syncing
with Taskwarrior. This is how it works:

 * If a line with only `t` is found, a new task is added to TaskWarrior, as
   if the rest of the line had been passed to `task add proj:projectname`.
 * If a line with `t<number>` is found, its content is updated with the task
   status in TaskWarrior.
 * If a line with `t<number>` has been deleted or completed in TaskWarrior,
   `t<number>` is replaced with `- [status]`.
 * `egt` stores the task UUID for each task ID that is in the file, so that
   when TaskWarrior renumberse its tasks, `egt` can still keep the sync.

I use this to handle [next actions](http://zenhabits.net/why-whats-the-next-action-is-the-most-important-question/):
when I replace a ` - ` at the beginning of an item in my plans with a ` t `,
and save the file, then they become next actions tracked by TaskWarrior.

When I mark them as done in TaskWarrior, then they are rewritten as starting
with ` - ` again, and I can move them to the project log.
