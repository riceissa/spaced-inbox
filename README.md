# Spaced inbox

Have you ever had a physical notebook, a text file on your computer, or a blog
in which you write your thoughts, but where you never look back on what you
wrote?  Where after you write your thoughts, the next day you just keep on
writing more unrelated thoughts without building on the previous days'
thoughts?  Spaced inbox helps you with that problem by periodically showing you
old notes you've written, gently reminding you to build on your previous
thoughts.

When I use the spaced inbox, it feels like I am having conversations with all
the versions of myself: past, present, and future. I read stuff written by my
past self and respond to it, so that my future self can see it. I can leave
messages for my future self. But also what I write now is for my present self,
clarifying my own thoughts.

Spaced inbox implements a minimal [writing inbox](https://notes.andymatuschak.org/z5aJUJcSbxuQxzHr2YvaY4cX5TuvLQT7r27Dz) with support for spaced repetition. How does it work?

1. You write your notes in a plain text file. Two blank lines, or a line
   containing at least three equals signs (and nothing else) like `======`, are
   interpreted as the beginning of a new note.
2. You create a file called `inbox_files.txt` (see
   [example](https://github.com/riceissa/spaced-inbox/blob/master/inbox_files.txt-example))
   to tell the program where to find your notes file. (The first column of
   `inbox_files.txt` is a short name you can give to your inbox file.)
3. You run `script.py`. This imports your writing inbox into a database that
   manages the review schedule.
4. Every day, you run `script.py`, both to import new notes into the database
   and to review notes that are due. The "review" consists of a single note
   that is due on that day, along with line numbers that tell you where in the
   file the note is located. You visit the location using your text editor,
   edit/delete/do nothing, then tell `script.py` that you've reviewed the note.
   This is like pressing "Good" or "Again" in Anki, and will modify the review
   interval in a spaced manner. You can keep running `script.py` to get more
   notes to review, if you feel like it. There _is_ a concept of "dueness" so
   eventually you will run out of notes to review, but you should not feel
   obligated to keep reviewing. The spacing algorithm is designed so that even
   if you stop reviewing for a long time, or you only review a couple notes per
   day, you will still get the notes that feel most exciting to you (unlike in
   Anki where the oldest cards dominate the review).

That's it! There's no app or writing interface: you get to choose your favorite
text editor, and write in whatever markup language you prefer. `script.py` does
not modify your notes file in any way.

The spacing algorithm that determines which notes are "due" is a simplified
version of the one for
[Anki/SM2](https://gist.github.com/riceissa/1ead1b9881ffbb48793565ce69d7dbdd)
with an initial interval of 50 days, so it goes 50 days, 50\*2.5 = 125 days,
125\*2.5 = 313 days, and so on. However, among the "due" cards, there is more
logic to pick ones that should feel the most exciting to you, rather than
randomly picking among them or just showing you the card that is most overdue.

## Quick start

```bash
git clone https://github.com/riceissa/spaced-inbox.git
cd spaced-inbox
mkdir -p ~/.config/spaced-inbox/
cp config.txt-example ~/.config/spaced-inbox/config.txt
$EDITOR ~/.config/spaced-inbox/config.txt  # Follow directions in the file
./spaced_inbox.py --help
./spaced_inbox.py
./spaced_inbox.py -r
./spaced_inbox.py -c
```

The recommended way to use the script is from inside of a text editor using the
`-r` flag. Many editors support parsing the output of the `-r` flag, allowing
you to jump to the note that is due for review. I've added short guides for
[Emacs](#using-the-script-from-within-emacs) and
[Vim](#using-the-script-from-within-vim) and
[Notepad++](#using-the-script-from-within-notepad) so that you have an idea of how it works.
Basically any text editor/IDE that allows you to compile programs from within the
editor will work with spaced inbox (whimsically, you can think of the
spaced inbox program as a "compiler for your thoughts").
I plan to eventually create a GUI program so that you don't need to set
everything up.

## Warning

The spaced inbox program in this repo is a _research project_ designed
specifically for myself. Eventually I do want to convert it into something that
is easy to learn and use, but at the moment this is not the intention. In
particular, updates to the code may make the program incompatible with older
versions of the database, the interface or spacing algorithm can change at any
time, and things are not documented very well in general.

Nonetheless, I do want to help people use the program. So if you are stuck
about how to use it or have a question about something, please open a
[discussion
topic](https://github.com/riceissa/spaced-inbox/discussions/new/choose) (or an
[issue](https://github.com/riceissa/spaced-inbox/issues/new) for bug reports).

## Why not just use Anki?

(Note as of 2023-01-12: I've significantly changed the note-selection algorithm
during reviews, so I think using Anki would give a significantly different and
worse-in-my-opinion experience. That's the most important reason to not use
Anki, in my opinion. But I'll leave the text below, which were my old reasons
for not using Anki.)

There are two senses in which one might "use Anki":

1. Add notes directly to Anki using the Anki interface, and review using Anki:
   I think it's pretty important to reduce friction for capturing thoughts. So
   this rules out adding notes directly to Anki for me. I could look into
   figuring out how to quickly and comfortably add new notes to Anki, but I've
   been wary of going down the rabbit hole of customizing Anki.
2. Have a plain text file in which to add notes, but periodically collect these
   notes and add them to Anki using a script, then thereafter review using
   Anki: I could have done this instead, but (a) I didn't think of doing this
   when I started, (b) it would have taken longer to implement the inbox, since
   I would have had to read Anki documentation about its database structure
   (whereas with my current implementation, I could just roll my own database
   schema), (c) when it comes time to edit any notes, I would be stuck
   editing them in the Anki's interface rather than my preferred text editor,
   and (d) something I like to do is to scroll up in the inbox file to see some
   of my recent thoughts (especially when picking things to write about on my
   [wiki](https://wiki.issarice.com/)). I could do this in Anki using the
   browse window, but I would have to click on each note instead of just
   scrolling. Again, it's not something that is impossible to do using Anki,
   but would doing it via Anki would add more friction.

(Thanks to TheCedarPrince for prompting me with the questions that led to these
thoughts.)

## Using the script from within Emacs

Add the following to your `~/.emacs.d/init.el` or `~/.emacs` file:

```elisp
(defun spaced-inbox--navigate-from-string (input-string)
  (if (string-match "^\\(.*\\):\\([0-9]+\\):[0-9]+\\(?::.*\\)?$" input-string)
      (let ((filename (string-trim (match-string 1 input-string)))
            (line-number (string-to-number (match-string 2 input-string))))
        (message "Navigating to %s:%d..." filename line-number)
        (with-current-buffer (window-buffer (selected-window))
          (find-file filename)
          (goto-line line-number)
          (recenter-top-bottom 0))
        t)
    (progn
      (message "Was not able to navigate to %s line %d" filename line-number)
      nil)))

(defun roll ()
  (interactive)
  (let* ((spaced-inbox-executable "/path/to/spaced_inbox.py")
         (flags "-r")
         (spaced-inbox-command (concat spaced-inbox-executable " " flags)))
    (if (not (file-executable-p spaced-inbox-executable))
        (message "Could not find the executable %s. Please make sure to provide the full path to the executable." spaced-inbox-executable)
        (let* ((output (string-trim (shell-command-to-string spaced-inbox-command))))
          (if (string-empty-p output)
              (message "Spaced inbox script produced no output.")
              (spaced-inbox--navigate-from-string output))))))
```

Make sure to replace `/path/to/spaced_inbox.py` with the actual path to the script. You may even need to prefix the command with
`python3` or `py.exe`.  To debug the executable location, I recommend doing
`M-x compile`, deleting the default `make -k `, and then entering whatever
spaced inbox command you want to try out.  In fact, if you want, you can just
do `M-x compile` and then `spaced_inbox.py -r` or `spaced_inbox.py -c` to
interact with the script, in just the way that you would interact with any
other compiler from within Emacs. Think of the spaced inbox script as a
compiler for your notes; instead of giving your a list of errors in your code,
it shows you a list of notes that perhaps you should look back on.

Restart Emacs. Now you should be able to just do `M-x roll` to do a
single review. Of course, you can map this command to any key combination you
want.

### Alternative way in Emacs using the compile feature (not recommended)

```elisp
;; (setq compilation-auto-jump-to-first-error t)

(defun roll ()
  (interactive)
  (compile "py.exe C:\\Users\\Issa\\projects\\spaced-inbox\\spaced_inbox.py -r")
  (sleep-for 1)
  ;; Unfortunately the following command doesn't work when run as part
  ;; of a function because the compile command above runs async so the
  ;; "*compilation*" window doesn't exist yet by the time the
  ;; delete-window function gets called... Hence why we need to insert
  ;; a sleep above to make sure the window exists. I can't believe the
  ;; Emacs people didn't make it easy to just do a thing when the
  ;; compile finishes; the only way to do this is to add a hook, which
  ;; as far as I can tell can only be done globally, so now it runs
  ;; for all compiles, not just within this function!
  (next-error)
  (delete-window (other-window-for-scrolling))
  (recenter-top-bottom 0))
```


## Using the script from within Vim

Put the following in your vimrc:

```vim
command! Roll call s:ExecuteRoll()
function! s:ExecuteRoll()
  let l:mp = &makeprg
  set makeprg=/path/to/spaced_inbox.py\ -r
  silent! make
  let &makeprg = l:mp
  silent! cfirst
  normal! zt
endfunction
```

Now you can just call `:Roll` to do a review. This works from any file. You can
remap `:Roll` to any keybinding to make it easier to do reviews.

## Using the script from within Notepad++

In the menu bar, go to Plugins -> Plugins Admin. In the search bar, search for
"nppexec". Click the checkbox next to NppExec, then click on the Install button
(which is located in the top right of the Plugins Admin window). After it is installed,
close the Plugins Admin window (you may need to restart Notepad++, I don't remember).

Now in the menu bar, go to Plugins -> NppExec -> Execute NppExec Script... . In the
commands text field, enter:

```
NPP_SAVE
NPP_CONSOLE 1
py.exe C:\location\to\spaced-inbox\directory\spaced_inbox.py -r
NPP_MENUCOMMAND Plugins|NppExec|Go to next error
```

(For `py.exe`, you may need to use something like `python3` instead. The executable
name is whatever you use in cmd to launch Python.)

I don't quite remember how to do this on a fresh install, but somehow you either click
the Save... button or you choose something in the dropdown that says `<temporary script>`
to save the commands typed above as a named script. You can name it something like
"spaced-inbox". Then when you press OK, it will run the commands typed above; a split window
should appear at the bottom of the screen showing the output of `spaced_inbox.py`.

Now in the menu go to Plugins -> NppExec -> Console Output Filters... . In the HighLight tab,
in the first of the HighLight mask lines, check the check box, then in the text field enter
the following:

```
%ABSFILE%:%LINE%:%CHAR%:*
```

(This tells NppExec for the pattern to look out for in the output of `spaced_inbox.py`.)

In the Filter tab, check the box at the top that says "Enable Console Output Filter". Then
press OK at the bottom of the window to close the window.

Now in the menu go to Plugins -> NppExec -> Execute NppExec Script... . The commands text
the we entered previously should still be there. Click the OK button to rerun the commands.
In the output split window at the bottom, you should see the output of `spaced_inbox.py`, in
particular a line that has a filename with a line number, column number, and some text from
your note. (This will only be visible if you have notes that are due, so only after you've used
the spaced inbox script for at least 50 days.) Now if you double click on this line, Notepad++
should jump you to the note (it may have already jumped there, since our commands list above
includes the line `NPP_MENUCOMMAND Plugins|NppExec|Go to next error`).
This jumping is only possible because we added the filter pattern
above.

Our final task is to automate the running and the jumping so that your review session has a nice
cadence.

In the menu, go to Plugins -> NppExec -> Advanced Options... . In the Menu item section at the bottom
left, in the Associated script dropdown, select spaced-inbox.  This should enter the text spaced-inbox
in the Item name text field right above. Click the Add/Modify button. This will add "spaced-inbox :: spaced-inbox"
to the Menu items * section at the top left. Make sure the checkbox that says "Place to the Macros submenu" is
checked. Now click OK at the bottom of the window. Possibly after restarting Notepad++, you should
now be able to run the spaced inbox script from the menu by going to Macro -> spaced-inbox. Don't worry,
we will make this even simpler.

Now in the menu, go to Settings -> Shortcut Mapper... .  Go to the Plugin commands tab. In the
Filter textbox at the bottom, type spaced-inbox; as you type, the list of commands will be filtered
and you should be left with just the spaced-inbox command. Now double click on the spaced-inbox command.
A Shortcut window will pop up. Choose a shortcut that you want to use for running the spaced inbox
command. For example, to do Ctrl+P as your shortcut, check the box that says CTRL, then pick P from
the dropdown. Then click OK. There might be a warning that says something like "CONFLICT FOUND!" -- in this
case, you can either pick a different shortcut, or you can remove the built-in shortcut (e.g. Ctrl+P in
Notepad++ by default prints the file, which is not very useful, so you may choose to remove the printing
shortcut). To remove a shortcut, note where the conflict is: when your cursor is on the spaced-inbox
command, there should be a text window near the bottom that says something like
"Main menu  |  22   Print...  ( Ctrl+P )" -- this is saying that the Print command from the Main menu
tab is conflicting with the new spaced inbox shortcut. So go to the Main menu tab in this Shortcut
mapper window, and in the Filter box at the bottom type "Print", then click on the Print command once,
then click on the Clear button at the bottom. This will remove the shortcut to the Print command,
and the Print command row should stop being red. You can now close the Shortcut mapper window.

Now you should be able to just type Ctrl+P (or whatever shortcut you chose), which will run the
spaced inbox command and will automatically jump to the note. It was a lot of work to get to
this point, but now doing reviews becomes trivial.

If you do not like having the script output in the split window at the bottom, you can press F6
to open the command window to edit the spaced-inbox commands list, and add this line at the bottom:

```
NPP_MENUCOMMAND Plugins|NppExec|Show NppExec Console
```

Then press OK. ("Show NppExec Console" sounds like it's telling NppExec to _show_ the
console split window, but actually that menu item acts more like a toggle so it's telling
NppExec to _hide_ it, since we assume it was just showing after running the commands above.)

## some helpful sql commands to poke around in the db

To find the notes that will be due first:

```sql
select last_reviewed_on, interval, date(last_reviewed_on, '+' || interval || ' day') as due_on from notes where due_on not null order by due_on desc;
```

See also the [review load visualizer](https://github.com/riceissa/spaced-inbox/blob/master/review_load.py).

## TODO

- there's a good chance I'll hate how interaction works (right now you have to manually go to the relevant line)
  - There's a way to _almost_ integrate interaction within standard text editors. Vim/emacs already support programs like grep, where it is possible to feed in a list of line numbers and be able to jump between them. This lets you _view_ the notes that are due and navigate between them. However, it does not give you a way to actually interact with that item (i.e. press "good" or "again") -- usually with grep/make you interact by _fixing something in the source file itself_, and by re-running grep/make, the error clears and it's removed from the list of errors. But with spaced inbox, you don't necessarily want to edit the note at all, in which case, you need some _other_ channel through which to tell the scheduler that you reviewed the note.

    With vim, maybe one possibility is to add commands like `:InboxGood` and `:InboxAgain`. Then what happens is that these commands re-import the inbox file (to correct any changes to line numbers), then uses the current line number in the text editor to identify which note the command is about. Then it does an update to the db where the interval/last review date changes. If the note is edited, it's not necessary to press good/again since the review schedule resets to 50 days. Then the command re-runs grepprg/makeprg to refresh the list of due items. (there's actually functions called getqflist and setqflist, which can programmatically alter the quickfix list without setting grepprg/makeprg.)

    Another idea (which doesn't solve the problem above) is for the python script to continuously monitor the inbox text file for changes, and to re-import every time the file is written (at least, while the review session is in progress).

    UPDATE: `script.py` now supports the `--external-program` flag, so you can run like
    `./script --external-program emacs`; the cursor in emacs will now jump to
    the line for the last note that is printed on the command line, so you no
    longer need to manually type in line numbers with `M-g g`. (This has now been removed; see below.)

    UPDATE(2025-04-08): i ended up going back to the original idea i had here, which is to exploit
    vim/emacs's builtin compilation processes. my solution to the interactivity problem described
    above is to just allow the reactions (good, again, etc) "in-bound", i.e. in the inbox text file
    itself. this lets you actually see your own past reactions as you're reviewing, which i think is
    probably a good thing.

- notes identity is very crude right now: we just check the sha1 hash, so any modification to a note will turn it into a note with different identity, which means the review schedule will reset. I think there's a decent chance this is actually ok: the notes you modify are the notes you are actually engaging with, so you actually want them around more frequently. (Unfortunately, I don't think I will find out if it's fine [anytime soon](https://wiki.issarice.com/wiki/Iteration_cadence_for_spaced_repetition_experiments).)

  UPDATE: i think this turned out to work pretty well.

## License

CC0. See `LICENSE` for details.
