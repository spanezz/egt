# User-visible feature changes in new egt versions

## New in version UNRELEASED

* Implemented `egt next` to show the first line of body from .egt files, sorted
  by .egt file age
* Implemented `egt list --age` to show the age alongside project paths
* Added options to sort `egt summary` by name, number of tasks or last
  update
* Moved config to XDG dir
* Added config options for date-format and columns in `egt summary`
* Adjusted project filter to allow wildcards
* Modified and extended TaskWarrior syncing
* Extended `egt archive` to allow exporting into a single file

## New in version 0.4

 - basic taskwarrior integration
    - start a line with ' t ' to turn it into a taskwarrior task
    - tasks are tracked by uuid, using ~/.local/share/egt/ accessory files
    - taskwarrior changes are reflected in task line when `egt annotate` is run
 - more robust annotate behaviour
    - parse errors go in header instead of breaking the file syntax
    - tested various cases of opening an empty file or a file with notes in it,
      without breaking it
 - logs make sure to have the right year at the beginning, also when running
   archive
 - logs add a year at the end if the current year has changed since the last
   log entry
 - metadata fields cleaned up, better support for multiline fields, support for
   adding fields from code, fixing archive losing "Archived: yes" header
 - dropped unused dbus buffy integration
 - egt archive --remove-old
 - egt archive --output
 - tagged log entries: append `+tag1 +tag2` in the log header to tag the entry
 - computes time with tagged log entries
 - if Total: is present in the metadata header, it is annotated with computed
   aggregated durations of log entries

## New in version 0.3

 - log entries can omit start-end times, and will be considered whole-day
   entries
 - `+` annotate command in log header creates day entries
 - `+` annotate command in log body autofills the body with git commits
