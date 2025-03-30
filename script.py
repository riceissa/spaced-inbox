#!/usr/bin/env python3

import argparse
import shutil
import textwrap
import datetime
import re
import os
import os.path
import sys
import random
import sqlite3
from sqlite3 import Connection, Cursor
from io import TextIOWrapper
import hashlib
import subprocess
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
sys.stderr.reconfigure(encoding='utf-8')  # type: ignore

# This value sets the initial interval in days.
INITIAL_INTERVAL: int = 50

# TODO: one thing that smooth.sh did that the new-as-of-January-2023 version
# doesn't do is having different quotas for the different inbox text files. If
# I do a large import of a new "stream" like browser bookmarks or something,
# then the reviews will (after 50 days) probably get dominated by these browser
# bookmarks. There should be some way to be like "limit browser bookmarks to at
# most 1% of all reviews" or something.  For now this hasn't been a problem for
# me, but it is something I will probably want to handle at some point.
# I notice that I want to specify weights using different methods. For
# example, with something like browser bookmarks, i want to say "don't make
# this thing dominate the reviews". but i may also want to say something like
# "github projects ideas repo notes should get a bit of penalty because they
# tend to be boring".  A bit thing to keep in mind that some inbox files
# can contain WAY more notes than some others.

# TODO: i am realizing that i often purposely don't fix some typos on boring
# notes because i reason that if i *do* fix them then that will reset the
# review schedule to 50 days, which i don't want. maybe there should be some
# way to make trivial changes without affecting the review schedule.

DB_COLUMNS: list[str] = ['sha1sum', 'note_text', 'line_number_start', 'line_number_end',
              'ease_factor', 'interval', 'last_reviewed_on', 'interval_anchor',
              'created_on', 'reviewed_count', 'note_state']

def print_terminal(string: str, file=None) -> None:
    terminal_width = shutil.get_terminal_size().columns
    wrapped = textwrap.fill(string, width=min(80, terminal_width))
    print(wrapped, file=file)

@dataclass
class Note:
    sha1sum: str
    note_text: str
    line_number_start: int
    line_number_end: int
    ease_factor: int
    interval: int
    last_reviewed_on: datetime.date
    interval_anchor: datetime.date
    created_on: datetime.date
    reviewed_count: int
    note_state: str

    def __repr__(self) -> str:
        fragment = initial_fragment(self.note_text)
        string = "Note(L%s-%s interval=%s ease_factor=%s note_state=%s reviewed_count=%s created_on=%s last_reviewed_on=%s %s)" % (
                self.line_number_start,
                self.line_number_end,
                self.interval,
                self.ease_factor,
                self.note_state,
                self.reviewed_count,
                self.created_on,
                self.last_reviewed_on,
                fragment)
        return string

    def to_db_row(self):
        return (
            self.sha1sum,
            self.note_text,
            self.line_number_start,
            self.line_number_end,
            self.ease_factor,
            self.interval,
            self.last_reviewed_on.strftime("%Y-%m-%d"),
            self.interval_anchor.strftime("%Y-%m-%d"),
            self.created_on.strftime("%Y-%m-%d"),
            self.reviewed_count,
            self.note_state,
        )

INBOX_FILE: str = ""

config_file = "inbox_file.txt"
if Path(config_file).exists():
    with open(config_file, "r", encoding="utf-8") as f:
        for line in f:
            if INBOX_FILE:
                break
            if line.strip().startswith("#"):
                continue
            # Why do we have both the name and path? This simplifies the situation
            # if the inbox files get moved around (e.g. if you have two different
            # computers). As long as inbox_files.txt gives the right path for the
            # same inbox names, it doesn't matter that the inbox files keep moving
            # around; the database doesn't need to know where the inbox files are
            # located, so the database does not need to be updated each time files
            # move around.
            # 2025-03-29: note that i'm simplifying things back down to just one
            # file, so the format no longer has a name.
            INBOX_FILE = line.strip()

if not INBOX_FILE:
    print_terminal("Inbox file not found! Please create a file named "
          "inbox_file.txt containing a single line that gives "
          "the full filepath of where your inbox file is located.",
          file=sys.stderr)
    sys.exit()

def note_from_db_row(row) -> Note:
    return Note(
        sha1sum=row[0],
        note_text=row[1],
        line_number_start=row[2],
        line_number_end=row[3],
        ease_factor=row[4],
        interval=row[5],
        last_reviewed_on=yyyymmdd_to_date(row[6]),
        interval_anchor=yyyymmdd_to_date(row[7]),
        created_on=yyyymmdd_to_date(row[8]),
        reviewed_count=row[9],
        note_state=row[10],
    )

def get_notes_from_db(conn: Connection) -> list[Note]:
    c = conn.cursor()
    result = [note_from_db_row(row) for row in
            c.execute("select " + ", ".join(DB_COLUMNS) +
                      " from notes").fetchall()]
    return result


def main() -> None:
    # 2025-03-30: Here's the commandline flags i am currently thinking of:
    # ./script -n    => just print the line number of where to jump to
    #     (i.e. the note to be reviewed), to stdout (or print nothing or -1
    #     if there's no note to be reviewed). this will be like how the
    #     current elisp implementation works. different editors can call
    #     this script, parse the line number, then jump to that line in
    #     however way they want.
    # ./script --compile   => print all the due notes in a vim quickfix
    #     or emacs M-x compile like fashion, to stdout or stderr. Basically,
    #     the script acts like a "compiler" for your notes.
    # ./script   => just import notes without doing anything else, but
    #     print what happened. basically the way currently how --no-review
    #     works
    # we won't need an --external-program flag anymore because different
    # editors can write their own mini-plugins to work with the -n
    # option.
    # i'm also thinking of removing the interactive thing entirely,
    # rather than keeping it as like a ./script --interactive  flag.
    # because the whole point is to just always have your inbox file
    # open to jot down ideas. you're already in your editor. you don't
    # want to go and open another program to do your reviews. that's too
    # much friction.

    parser = argparse.ArgumentParser()
    # The following flag is useful if you just want to import new notes as a
    # cronjob or something, and don't want to get trapped in the interact loop.
    parser.add_argument("-c", "--compile",
                        help=("compiler mode"),
                        action="store_true")
    parser.add_argument("-n", "--number",
                        help=("just print the line number to jump to"),
                        action="store_true")
    args = parser.parse_args()
    if args.compile and args.number:
        print_terminal("You cannot use both --compile/-c and --number/-n simultaneously, as they both change how the output is printed. Please pick one or the other.", file=sys.stderr)
        sys.exit()
    if not os.path.isfile("data.db"):
        with open("schema.sql", "r", encoding="utf-8") as f:
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            c.executescript(f.read())
    else:
        conn = sqlite3.connect('data.db')

    if args.number:
        notes_from_db = reload_db(conn, log_level=0)
        note: Note | None = pick_note_to_review(notes_from_db, log_level=0)
        if note:
            print(note.line_number_start)
        else:
            print(-1)
    elif args.compile:
        pass
    else:
        interact_loop(conn)


def reload_db(conn: Connection, log_level=1) -> list[Note]:
    cur = conn.cursor()
    fetched = cur.execute("""
        select {cols} from notes
        """.format(cols=", ".join(DB_COLUMNS),)
    ).fetchall()
    notes_db = [note_from_db_row(row) for row in fetched]
    if log_level > 0:
        print("Importing new notes from {}... ".format(INBOX_FILE),
              file=sys.stderr, end="")
    with open(INBOX_FILE, "r", encoding="utf-8") as f:
        current_inbox = parse_inbox(f)
    update_notes_db(conn, notes_db, current_inbox, log_level)
    if log_level > 0:
        print("done.", file=sys.stderr)

    # After we update the db using the current inbox, we must query the db
    # again since the due dates for some of the notes may have changed (e.g.
    # some notes may have been deleted). This fixes a bug where if a note is
    # due, then I edit it and type 'quit' and then re-run the script, the note
    # is still due.
    combined_notes_db = get_notes_from_db(conn)
    return combined_notes_db


def clear_screen() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')


def parse_inbox(lines: TextIOWrapper) -> list[tuple[str, str, int, int]]:
    """Parsing rules:
    - two or more blank lines in a row start a new note
    - a line with three or more equals signs and nothing else starts a new note

    """
    result = []
    note_text = ""
    state = "text"
    # This is a finite state machine with three states (text, 1 newline, 2+
    # newline) and three actions (text, blank, ===+).
    line_number = 0
    line_number_start = 1
    for raw_line in lines:
        line = raw_line.strip()
        line_number += 1
        if state == "text":
            if not line:
                state = "1 newline"
            elif re.match("===+$", line):
                state = "2+ newline"
            else:
                # state remains the same
                note_text += line + "\n"
        elif state == "1 newline":
            if (not line) or re.match("===+$", line):
                state = "2+ newline"
            else:
                state = "text"
                note_text += "\n" + line + "\n"
        else:
            assert state == "2+ newline"
            if line and not re.match("===+$", line):
                state = "text"
                result.append((sha1sum(note_text.strip()), note_text,
                               line_number_start, line_number - 1))
                line_number_start = line_number
                note_text = line + "\n"
            # else: state remains the same
    # We ended the loop above without adding the final note, so add it now
    result.append((sha1sum(note_text.strip()), note_text,
                   line_number_start, line_number))
    return result


def _print_lines(string: str) -> None:
    """Print a string with line numbers (for debugging parse_inbox)."""
    line_number = 0
    for line in string.split("\n"):
        line_number += 1
        print(line_number, line)


def update_notes_db(conn: Connection, notes_db: list[Note], current_inbox: list[tuple[str, str, int, int]], log_level=1) -> None:
    """
    Add new notes to db.
    Remove notes from db if they no longer exist in the notes file?
    """
    c = conn.cursor()
    db_hashes = {note.sha1sum: note for note in notes_db}
    note_number = 0
    inbox_size = len(current_inbox)
    for (sha1sum, note_text, line_number_start,
         line_number_end) in current_inbox:
        if sha1sum in db_hashes and db_hashes[sha1sum].interval >= 0:
            # The note content is not new, but the position in the file may
            # have changed, so update the line numbers
            c.execute("""update notes set line_number_start = ?,
                                          line_number_end = ?
                         where sha1sum = ?""",
                      (line_number_start, line_number_end, sha1sum))
        elif sha1sum in db_hashes:
            # The note content is not new but the same note content was
            # previously added and then soft-deleted from the db, so we want to
            # reset the review schedule.
            c.execute("""update notes set line_number_start = ?,
                                          line_number_end = ?,
                                          ease_factor = ?,
                                          interval = ?,
                                          last_reviewed_on = ?,
                                          interval_anchor = ?,
                                          reviewed_count = ?,
                                          note_state = ?
                         where sha1sum = ?""",
                      (line_number_start, line_number_end, 300, INITIAL_INTERVAL,
                       datetime.date.today().strftime("%Y-%m-%d"),
                       datetime.date.today().strftime("%Y-%m-%d"),
                       None, 0, "normal", sha1sum))
        else:
            # The note content is new.
            note_number += 1
            interval_anchor = datetime.date.today()
            try:
                c.execute("insert into notes (%s) values (%s)"
                          % (", ".join(DB_COLUMNS),
                             ", ".join(["?"]*len(DB_COLUMNS))),
                          Note(sha1sum, note_text, line_number_start,
                               line_number_end, ease_factor=300, interval=INITIAL_INTERVAL,
                               last_reviewed_on=datetime.date.today(),
                               interval_anchor=interval_anchor,
                               created_on=datetime.date.today(),
                               reviewed_count=0,
                               note_state="normal").to_db_row())
            except sqlite3.IntegrityError:
                print("Duplicate note text found! Please remove all duplicates and then re-import.", note_text, file=sys.stderr)
                sys.exit()
    conn.commit()
    if log_level > 0:
        print("%s new notes found... " % (note_number,), file=sys.stderr, end="")

    # Soft-delete any notes that no longer exist in the current inbox
    inbox_hashes = set(sha1sum for (sha1sum, _, _, _) in current_inbox)
    delete_count = 0
    for note in notes_db:
        if note.sha1sum not in inbox_hashes and note.interval >= 0:
            delete_count += 1
            c.execute("update notes set interval = -1 where sha1sum = ?",
                      (note.sha1sum,))
    conn.commit()
    if log_level > 0:
        print("%s notes were soft-deleted... " % (delete_count,), file=sys.stderr,
              end="")


def due_notes(notes_db: list[Note]) -> list[Note]:
    result = []
    for note in notes_db:
        if note.interval < 0:
            # This note was soft-deleted, so don't include in reviews
            continue
        due_date = (note.interval_anchor +
                    datetime.timedelta(days=note.interval))
        if datetime.date.today() >= due_date:
            result.append(note)
    return result

def get_recent_unreviewed_note(notes_db: list[Note]) -> Note | None:
    """Randomly select a note that was created in the last 50-100 days and has
    not yet been reviewed yet."""
    candidates = []
    for note in notes_db:
        # FIXME: I suspect using days_since_created here actually causes a
        # problem, where even if a note has been reviewed, it will still keep
        # showing up in reviews. So I need to add a check for when the note was
        # last reviewed as well, I think.
        # 2025-03-30: Actually, I was mistaken in there being a bug here. The
        # only time a note has the "normal" state is when it has just been
        # created. So as soon as the note gets reviewed, it will no longer have
        # that state, so it will never be picked here. HOWEVER, I'm planning to
        # store the responses "in bound" inside the inbox.txt file itself,
        # which means notes CAN have a "normal" state now even though they've
        # been reviewed. So it WILL become a bug soon.
        days_since_created = (datetime.date.today() - note.created_on).days
        if (note.interval > 0 and note.note_state == "normal" and
            days_since_created >= INITIAL_INTERVAL and days_since_created <= 2*INITIAL_INTERVAL):
            candidates.append(note)
    if not candidates:
        return None
    return random.choice(candidates)

def get_exciting_note(notes_db: list[Note]) -> Note | None:
    candidates = []
    weights = []
    for note in notes_db:
        days_since_reviewed = (datetime.date.today() - note.last_reviewed_on).days
        days_overdue = days_since_reviewed - INITIAL_INTERVAL * 2.5**note.reviewed_count
        if note.interval > 0 and note.note_state == "exciting" and days_overdue > 0:
            candidates.append(note)
            # We allow any exciting and overdue note to be selected, but weight
            # the probabilities so that the ones that are more overdue are more
            # likely to be selected.
            # TODO: I need to learn more about what sensible weights for this
            # are.
            weights.append(days_overdue**2)

    if not candidates:
        return None
    return random.choices(candidates, weights, k=1)[0]

# TODO: I only deal with "normal" and "exciting" notes specially. But
# there's support for more reactions to notes during review. Eventually, I'd
# like to incorporate these other reactions into the review algo as well.

def get_all_other_note(notes_db: list[Note]) -> Note | None:
    candidates = []
    weights = []
    for note in notes_db:
        days_since_reviewed = (datetime.date.today() - note.last_reviewed_on).days
        days_overdue = days_since_reviewed - INITIAL_INTERVAL * 2.5**note.reviewed_count
        if note.interval > 0 and note.note_state not in ["exciting"] and days_overdue > 0:
            candidates.append(note)
            # TODO: I need to learn more about what sensible weights for this
            # are.  For example, maybe if a note has a longer interval then
            # it can be further delayed because it's already been so long
            # since you last saw the note.  So the weight should possibly
            # containt some percentage of the interval.
            weights.append(days_overdue**2)
    if not candidates:
        return None
    return random.choices(candidates, weights, k=1)[0]

def pick_note_to_review(notes: list[Note], log_level=1) -> Note | None:
    note: Note | None = None
    rand = random.random()
    if log_level > 0:
        print("random number =", rand, file=sys.stderr)
    if rand < 0.5:
        if log_level > 0:
            print("Attempting to choose a recent unreviewed note...",
                  end="", file=sys.stderr)
        note = get_recent_unreviewed_note(notes)
        if note is None:
            if log_level > 0:
                print("failed.", file=sys.stderr)
        else:
            if log_level > 0:
                print("success.", file=sys.stderr)
    if note is None and rand < 0.7:
        if log_level > 0:
            print("Attempting to choose an exciting note...", end="",
                  file=sys.stderr)
        note = get_exciting_note(notes)
        if note is None:
            if log_level > 0:
                print("failed.", file=sys.stderr)
        else:
            if log_level > 0:
                print("success.", file=sys.stderr)
    if note is None:
        if log_level > 0:
            print("Attempting to choose some other note...", end="",
                  file=sys.stderr)
        note = get_all_other_note(notes)
        if note is None:
            if log_level > 0:
                print("failed.", file=sys.stderr)
        else:
            if log_level > 0:
                print("success.", file=sys.stderr)
    return note

def calc_stats(notes: list[Note]) -> tuple[int, int]:
    num_notes = 0
    num_due_notes = 0
    note: Note | None
    for note in notes:
        if note.interval > 0:
            num_notes += 1
            days_since_reviewed = (datetime.date.today() - note.last_reviewed_on).days
            days_overdue = days_since_reviewed - INITIAL_INTERVAL * 2.5**note.reviewed_count
            if days_overdue > 0:
                num_due_notes += 1
    return (num_notes, num_due_notes)

def record_review_load(num_notes: int, num_due_notes: int) -> None:
    if not os.path.isfile("review-load.csv"):
        with open("review-load.csv", "w", encoding="utf-8") as review_load_file:
            review_load_file.write("timestamp,num_notes,num_due_notes\n")
    with open("review-load.csv", "a", encoding="utf-8") as review_load_file:
        review_load_file.write("%s,%s,%s\n" % (datetime.datetime.now().isoformat(), num_notes, num_due_notes))

def interact_loop(conn: Connection) -> None:
    no_review = False
    external_program = ""
    while True:
        # clear_screen()
        notes_from_db = reload_db(conn)
        num_notes, num_due_notes = calc_stats(notes_from_db)
        print("Number of notes:", num_notes)
        print("Number of notes that are due:", num_due_notes)
        record_review_load(num_notes, num_due_notes)

        note: Note | None = pick_note_to_review(notes_from_db)

        if note is None:
            print("No notes are due")
            break
        else:
            print(note)
            if external_program == "emacs":
                loc = note.line_number_start
                elisp = ("""
                    (with-current-buffer
                        (window-buffer (selected-window))
                      (find-file "%s")
                      (goto-line %s)
                      (recenter-top-bottom 0))
                """ % (
                    # since the db only stores the inbox name, we must look up
                    # the filepath from INBOX_FILES
                    INBOX_FILE.replace("\\", r"\\\\"),
                    loc
                )).replace("\n", " ").strip()
                emacsclient = "emacsclient"
                if os.name == "nt":
                    # Python on Windows is dumb and can't detect gitbash
                    # aliases so we have to get the full path of the executable
                    emacsclient = "C:/Program Files/Emacs/emacs-29.4/bin/emacsclientw"
                p = subprocess.Popen([emacsclient, "-e", elisp], stdout=subprocess.PIPE)


        command = input("Enter a command ('[e]xciting', '[i]nteresting', '[m]eh', '[c]ringe', '[t]axing', '[y]eah', '[l]ol', '[r]eroll', '[q]uit'): ")
        if not re.match(r"e|i|m|c|t|y|l|r|q", command):
            print("Not a valid command", file=sys.stderr)
            continue
        if command.strip() in ["r", "refresh", "reroll"]:
            continue
        if command.strip() in ["q", "quit"]:
            break

        command_to_state = {
                'e': "exciting",
                'i': "interesting",
                'm': "meh",
                'c': "cringe",
                't': "taxing",
                'y': "yeah",
                'l': "lol",
                }
        c = conn.cursor()
        new_interval = good_interval(note.interval, note.ease_factor)
        c.execute("""update notes set interval = ?,
                                      last_reviewed_on = ?,
                                      interval_anchor = ?,
                                      reviewed_count = ?,
                                      note_state = ?
                     where sha1sum = ?""",
                  (new_interval, datetime.date.today().strftime("%Y-%m-%d"), datetime.date.today().strftime("%Y-%m-%d"), note.reviewed_count + 1, command_to_state[command.strip()], note.sha1sum))
        conn.commit()
        print("You will next see this note in " +
              human_friendly_time(new_interval), file=sys.stderr)


def sha1sum(string: str) -> str:
    return hashlib.sha1(string.encode('utf-8')).hexdigest()


def initial_fragment(string: str, words: int = 20) -> str:
    """Get the first `words` words from `string`, joining any linebreaks."""
    return " ".join(string.split()[:words])


def good_interval(interval: int, ease_factor: int) -> int:
    return int(interval * ease_factor/100)


def again_interval(interval: int) -> int:
    return int(interval * 0.90)


def human_friendly_time(days: float) -> str:
    if days < 0:
        return "-" + human_friendly_time(abs(days))
    elif days * 24 * 60 < 1:
        return str(round(days * 24 * 60 * 60, 2)) + " seconds"
    elif days * 24 < 1:
        return str(round(days * 24 * 60, 2)) + " minutes"
    elif days < 1:
        return str(round(days * 24, 2)) + " hours"
    elif days < 30:
        return str(round(days, 2)) + " days"
    elif days < 365:
        return str(round(days / (365.25 / 12), 2)) + " months"
    else:
        return str(round(days / 365.25, 2)) + " years"

def yyyymmdd_to_date(string: str) -> datetime.date:
    return datetime.datetime.strptime(string, "%Y-%m-%d").date()




if __name__ == "__main__":
    main()
