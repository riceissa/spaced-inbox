# spaced inbox

Spaced inbox implements a minimal [writing inbox](https://notes.andymatuschak.org/z5aJUJcSbxuQxzHr2YvaY4cX5TuvLQT7r27Dz) with support for spaced repetition. How does it work?

1. You write your notes in a plain text file. Two blank lines, or a line containing at least three equals signs (and nothing else) like `======`, are interpreted as the beginning of a new note.
2. You run `script.py --initial-import`. This imports your writing inbox into a database that manages the review schedule.
3. Every day, you run `script.py`, both to import new notes into the database and to review notes that are due. The "review" consists of a list of notes that are due on that day, along with line numbers that tell you where in the file they are located. You visit the location, edit/delete/do nothing, then tell `script.py` that you've reviewed the note. This is like pressing "Good" or "Again" in Anki, and will modify the review interval in a spaced manner.

That's it! There's no app or writing interface: you get to choose your favorite text editor, and write in whatever markup language you prefer. `script.py` does not modify your notes file in any way.

The spacing algorithm is a simplified version of the one for [Anki/SM2](https://gist.github.com/riceissa/1ead1b9881ffbb48793565ce69d7dbdd) with an initial interval of 50 days, so it goes 50 days, 50\*2.5 = 125 days, 125\*2.5 = 313 days, and so on.

## some helpful sql commands to poke around in the db

To find the notes that will be due first:

```sql
select last_reviewed_on, interval, date(last_reviewed_on, '+' || interval || ' day') as due_on from notes where due_on not null order by due_on asc limit 5;
```

See also the [review load visualizer](https://github.com/riceissa/spaced-inbox/blob/master/review_load.py).

## TODO

- there's a good chance I'll hate how interaction works (right now you have to manually go to the relevant line)
  - There's a way to _almost_ integrate interaction within standard text editors. Vim/emacs already support programs like grep, where it is possible to feed in a list of line numbers and be able to jump between them. This lets you _view_ the notes that are due and navigate between them. However, it does not give you a way to actually interact with that item (i.e. press "good" or "again") -- usually with grep/make you interact by _fixing something in the source file itself_, and by re-running grep/make, the error clears and it's removed from the list of errors. But with spaced inbox, you don't necessarily want to edit the note at all, in which case, you need some _other_ channel through which to tell the scheduler that you reviewed the note.

    With vim, maybe one possibility is to add commands like `:InboxGood` and `:InboxAgain`. Then what happens is that these commands re-import the inbox file (to correct any changes to line numbers), then uses the current line number in the text editor to identify which note the command is about. Then it does an update to the db where the interval/last review date changes. If the note is edited, it's not necessary to press good/again since the review schedule resets to 50 days. Then the command re-runs grepprg/makeprg to refresh the list of due items. (there's actually functions called getqflist and setqflist, which can programmatically alter the quickfix list without setting grepprg/makeprg.)

    Another idea (which doesn't solve the problem above) is for the python script to continuously monitor the inbox text file for changes, and to re-import every time the file is written (at least, while the review session is in progress).
- notes identity is very crude right now: we just check the sha1 hash, so any modification to a note will turn it into a note with different identity, which means the review schedule will reset. I think there's a decent chance this is actually ok: the notes you modify are the notes you are actually engaging with, so you actually want them around more frequently. (Unfortunately, I don't think I will find out if it's fine [anytime soon](https://wiki.issarice.com/wiki/Iteration_cadence_for_spaced_repetition_experiments).)

## License

CC0. See `LICENSE` for details.
