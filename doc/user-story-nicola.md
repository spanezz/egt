Introduction
------------

I am active in several different environments.
Therefore, at any point in time I have a rather large number of ongoing projects (a term I use loosely here).
I use `egt` to keep track of the progress in these projects, take notes and plan next steps.

For this guide lets assume I do have 3 environments: private, work and an association I am a board-member of.
In these environments I have to following projects:

private:
  - a planned holiday
  - contact to my bank
  - taxes

work:
  - regular meetings with my manager
  - a dinner I promised to organise for my team
  - project A
  - project B

association:
  - the next board meeting
  - the code of conduct we are preparing


egt-Files
---------

The corresponding egt-files for the first project in each group, could look something like the examples below.
(Assuming today is the 2021-12-14.)

```
Name: p.holidays.journey

2021:
01 December:
  - Fixed date with partner: 2022-02-10 - 2022-02-14
  - searched for possible hotels
05 December:
  - discussed hotels with partner
  - booked The Nice Hotel
10 December:
  - booked train tickets

todo:
  t due:jan collect ideas for museums to visit
  - book museum tickets

Hotels
------
  https://thenicehotel.example.com (looks nice)
  https://shady.example.org (looks shady)
  ...
```


```
Name: w.manager

2021:
06. December:
  - Meeting:
    - holidays from 2021-12-21 - 2022-01-03 granted
    - discussed state of dinner
13 December:
  - Mail from manager: remaining meetings of this year cancelled

todo:
  t due:wed confirm meeting from 2022-01-03

Topics
------
  - State of projects
  - compliment from customer
  - duration of team meetings

```


```
Name: a.board.2022-01

2021:
01 December:
  - Mail to board members with survey for meeting date:
    https://survey.example.com/my-board-meeting
08 December:
  - Reminder to board members
    - please answer survey
    - please send me agenda items
14 December:
  - Meeting date fixed: 2022-01-20
  - Mail to board: meeting date

todo:
  t wait:jan due:2022-01-10 finalize agenda
  t wait:2022-01-10 due:2022-01-13 send inviation
  t wait:2022-01-21 due:2022-01-22 follow-up on meeting results

Agenda
-------
  - Code of Conduct
  - Holiday plans of board members
  - Financial Statement 2021
```

Notes:
  * I group projects by name, using `.` as a level-separator. This allows to apply filters like `project:w` in taskwarrior to limit the task list to work related tasks.
  * I have a todo-section after the log with next steps.
  * I rely on `egt`'s taskwarrior integration to keep track of individual todos and make heavy use of the `wait:` and `due:` dates.
  * I keep notes related to a project below the todo-section. (Until they grow big enough to put them into a separate file.)


Filesystem
----------

In the filesystem, the projects might be organised something like this:

```
~/private/finances/bank/projectlog.egt
~/private/finances/bank/receipts/...

~/private/finances/taxes/2020/projectlog.txt
~/private/finances/taxes/2020/...
~/private/finances/taxes/2021/projectlog.egt
~/private/finances/taxes/2021/...

~/private/holidays/journey/projectlog.egt
~/private/holidays/journey/tickets.pdf
~/private/holidays/journey/confirmation_hotel.pdf

~/work/projectA/projectlog.egt
~/work/projectA/...

~/work/projectB/projectlog.egt
~/work/projectB/...

~/work/projectlogs/manager.egt
~/work/projectlogs/dinner.egt

~/assoc/board/2022-01/projectlog.egt
~/assoc/board/2022-01/agenda.odt
~/assoc/board/2022-01/documents/...

~/assoc/code_of_conduct/projectlog.egt
~/assoc/code_of_conduct/draft.odt
```

Notes:
  * For most projects I create a separate project directory. This allows me to store additional files and quickly reach them with `egt term <project>`
    (I do not like hidden project files so I usually call the egt-files `projectlog.egt`.)
  * For small projects without further files, I keep generic folders usually called `projectlogs` as in the `work` part of the tree.
  * Once a project is completed, I rename the project file to `*.txt` as with 2020's taxes.
    (You might want to set `Archived: true` metadata instead.)



Work-Cylce
----------

To illustrate the way I work with this setup, let's look at project `w.manager`.
  * I am at work and taskwarrior informs me about the pending task number 14 'confirm meeting from 2022-01-03'.
    * I send an email to my manager asking to confirm the next meeting.
    * I modify the dates of task 14: `task 14 mo due:1w wait:1w`
    * I open `manager.egt`: `egt edit w.manager`  
      and add a note:  
      ```
      +
        - mail sent to manager: please confirm 2022-01-03
      ```
    * When I save and quit the file, `egt annotate` will turn the `+` into a proper date
  * The next day, I get a great feedback from a customer about Project A
    * I add an item in the topics section of `manger.egt`, so I remember to tell my manager about the feedback.
  * Another 3 days later my manager confirms the meeting
    * I open `manager.egt`
    * I immediately save the file and `egt annotate` will update the task number of my waiting task. The number changed due to other tasks being completed in the meantime. It's now task number 9.
    * In a separate terminal I run `task 9 done`
    * I save `manager.egt` again and let `egt annotate` pick up on the completed task.
    * I move the completed task into the log section, save the file and quit the editor
  * On 2022-01-03 I meet my manager.
    * I open `manger.egt`
    * I discuss the listed topics with my manager
    * and add new log-entries or tasks as appropriate.

