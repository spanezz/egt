# egt - Enrico's Getting Things Done

egt tracks [`.egt` text files](project.md) scattered in the file system, that
mark where your projects live and store project-specific information like
planning notes, ideas, activity logs.

I currently use egt to:

 * quickly find project directories, to open terminals in them, and back up the
   information they contain that is not stored in git and pushed remotely
 * draft TODO lists
 * compute work hours to bill customers
 * brainstorm, and turn brainstorming notes into plans
 * turn plans into [TaskWarrior](http://taskwarrior.org/) tasks
 * print reports of my activity


## Dependencies

```sh
apt install python3-dateutil python3-taskw python3-xdg python3-git
```

## Quickstart

1. enter a directory with one of your projects
2. create an empty file called `.egt`
3. run `egt scan`
4. run `egt list`, your project should appear

You can call projects by name to perform several actions on them:

* `egt edit name` opens an editor on the `.egt` file for the given project.
* `egt term name` opens a terminal in the project directory.
* `egt work name` opens a terminal in the project directory, with an editor
  opened on the `.egt` file. With most tabbed terminals, creating new tabs at
  this point should open shells with the project directory as current
  directories.

Once you have some entry in the `.egt` file log, you can have some statistics:

* `egt weekrpt`: prints a report on the last week of your activity
* `egt summary`: prints a summary of your activity

`egt` knows about `git`, so if your project directories are git checkouts, you
can use:

* `egt grep ...`: runs `git grep` on all project directories. Suppose you
  remember having written some useful utility function, but you do not remember
  on which project, this may help find it.
* `egt backup`: created a tarball with all `.git/config` and `.egt` files of
  all your projects, so that if things go wrong you can restore most of your
  projects from that tarball and remote git repositories.


## Reference documentation

See [Format of project files](project.md) for documentation of the format of
egt project files.

See [egt annotate](annotate.md) for details on the transformation done on
project files by egt annotate.


## vim integration

I currently have this code in `~/.vim/filetype.vim`, to mark `.egt` files as
being of `egt` file type:

```vim
if exists("did_load_filetypes")
  finish
endif

augroup filetypedetect
  " Recognise egt files
  au! BufNewFile,BufRead *.egt,.egt setf egt
augroup END
```

And I have this in `"~/.vim/after/ftplugin/egt.vim`, to make editing easier and
to run `egt annotate` to update log durations and sync with TaskWarrior each
time I save the file:

```vim
set ts=3
set sw=3
set expandtab
set si
function! EgtAnnotate()
    let l:cur_pos = getpos(".")
    :%!egt annotate --stdin %:p
    call setpos(".", l:cur_pos)
endfunction
autocmd BufWritePre,FileWritePre <buffer> :silent call EgtAnnotate()
```

See [egt annotate](annotate.md) for details on the transformation done by egt
annotate.

Note: you can do :au! in vim to deactivate save hooks if you don't want them
triggered.
