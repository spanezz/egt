# User-visible feature changes in new egt versions

## New in version 0.4

 - basic taskwarrior integration
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

## New in version 0.3

 - log entries can omit start-end times, and will be considered whole-day
   entries
 - `+` annotate command in log header creates day entries
 - `+` annotate command in log body autofills the body with git commits
