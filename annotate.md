# Egt annotate

`egt annotate` reads a [project file](project.md) on standard input, makes some
changes to it, then writes it back on standard output.

This can be used as a [hook in vim](http://www.enricozini.org/blog/2016/debian/postprocessing-files-saved-by-vim/)
(or another editor that allows it) to have egt do some work for you every time
you save the file.

The trasformations that it performs are:

 * it computes and appends log durations to log entries
 * it runs [annotate commands](project.md#annotate_commands) inside log entries
 * it runs [annotate commands](project.md#annotate_commands) at the end of the log
 * it synchronizes the [taskwarrior lines](project.md#body_taskwarrior) with
   TaskWarrior.
