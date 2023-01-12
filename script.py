#!/usr/bin/env python3

import argparse
import datetime
import re
import os
import os.path
import sys
import random
import sqlite3
import hashlib
import subprocess
from collections import namedtuple

sys.stdout.reconfigure(encoding='utf-8')

# This value sets the initial interval in days.
INITIAL_INTERVAL = 60

# TODO: make sure that the --initial-import flag works on a non-empty db. e.g.
# if i suddenly add all of my browser bookmarks as separate items in the inbox
# file and then import using --initial-import, will that screw things up, or
# will it work as expected? If I can get this to work, it will be very
# convenient as I can keep growing my inbox/adding more "streams" to it by
# bulk-adding followed by incremental updates.
# A related problem: if i do an initial import from one source, then do initial
# import from a different source, that might mean doubling up on some of the
# days (if the two imports are done close in time), so it basically doubles my
# workload for those days. it might be good to check in the db first to figure
# out which days in the next 300 days or whatever has the least amount of work,
# then start by putting notes in those days, and gradually work up to the days
# with more workload.

# TODO: i am realizing that i often purposely don't fix some typos on boring
# notes because i reason that if i *do* fix them then that will reset the
# review schedule to 50 days, which i don't want. maybe there should be some
# way to make trivial changes without affecting the review schedule.

DB_COLUMNS = ['sha1sum', 'note_text', 'line_number_start', 'line_number_end',
              'ease_factor', 'interval', 'last_reviewed_on', 'interval_anchor',
              'inbox_name', 'created_on', 'reviewed_count', 'note_state']
Note = namedtuple('Note', DB_COLUMNS)

INBOX_FILES = {}

with open("inbox_files.txt", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip().startswith("#"):
            continue
        # Why do we have both the name and path? This simplifies the situation
        # if the inbox files get moved around (e.g. if you have two different
        # computers). As long as inbox_files.txt gives the right path for the
        # same inbox names, it doesn't matter that the inbox files keep moving
        # around; the database doesn't need to know where the inbox files are
        # located, so the database does not need to be updated each time files
        # move around.
        name, path = line.strip().split("\t")
        INBOX_FILES[name] = path


def get_notes_from_db(conn):
    c = conn.cursor()
    return [Note(*row) for row in
            c.execute("select " + ", ".join(DB_COLUMNS) +
                      " from notes").fetchall()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-import",
                        help=("Uniformly distribute new notes between "
                              "days 50-150 rather than having everything "
                              "due on day 50"),
                        action="store_true")
    # The following flag is useful if you just want to import new notes as a
    # cronjob or something, and don't want to get trapped in the interact loop.
    parser.add_argument("--no-review",
                        help=("Just import new notes, without "
                              "printing due notes or going into "
                              "the review interact loop"),
                        action="store_true")
    parser.add_argument("--external-program",
                        help=("External program that can be used to do the "
                              "reviews. Currently only emacs is supported (to use "
                              "emacs, keep your inbox file as the current buffer, "
                              "then run this script with this argument)."),
                        action="store")
    args = parser.parse_args()
    if not os.path.isfile("data.db"):
        with open("schema.sql", "r", encoding="utf-8") as f:
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            c.executescript(f.read())
    else:
        conn = sqlite3.connect('data.db')

    interact_loop(conn, args.no_review, args.initial_import, args.external_program)


def reload_db(conn, initial_import):
    for inbox_name in INBOX_FILES:
        inbox_path = INBOX_FILES[inbox_name]
        cur = conn.cursor()
        fetched = cur.execute("""
            select {cols} from notes
            where
                inbox_name = '{inbox_name}'
            """.format(
                cols=", ".join(DB_COLUMNS),
                inbox_name=inbox_name
            )
        ).fetchall()
        notes_db = [Note(*row) for row in fetched]
        print("Importing new notes from {}... ".format(inbox_path),
              file=sys.stderr, end="")
        with open(inbox_path, "r", encoding="utf-8") as f:
            current_inbox = parse_inbox(f)
        update_notes_db(conn, inbox_name, notes_db, current_inbox,
                        initial_import=initial_import)
        print("done.", file=sys.stderr)

    # After we update the db using the current inbox, we must query the db
    # again since the due dates for some of the notes may have changed (e.g.
    # some notes may have been deleted). This fixes a bug where if a note is
    # due, then I edit it and type 'quit' and then re-run the script, the note
    # is still due.
    combined_notes_db = get_notes_from_db(conn)
    return combined_notes_db


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def parse_inbox(lines):
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


def _print_lines(string):
    """Print a string with line numbers (for debugging parse_inbox)."""
    line_number = 0
    for line in string.split("\n"):
        line_number += 1
        print(line_number, line)


def update_notes_db(conn, inbox_name, notes_db, current_inbox,
                    initial_import=False, context_based_identity=False):
    """
    Add new notes to db.
    Remove notes from db if they no longer exist in the notes file?

    If initial_import is true, then import as if a large number of notes are
    being added at once (such as the first time a notes file is imported). This
    tries to even out the review load so that you don't have like 100 notes to
    review on the 50th day (the default initial interval after importing).
    Specifically, distribute the cards uniformly between days 50 and 150. e.g.
    if you have 300 cards, then this will mean 3 cards per day on days 50-150
    from the day you import (assuming you don't import any more cards in that
    time period), rather than suddenly getting 300 cards on day 50.

    If context_based_identity is true, then identify notes using the
    surrounding context, even if the hashes do not match. For example, if the
    notes file used to have the hash sequence 1111, 2222, 3333, but now it has
    the hash sequence 1111, 4444, 3333, using context_based_identity would say
    the note with hash 2222 was modified to the note with hash 4444 (i.e. they
    are the same note, but the content changed), whereas without
    context_based_identity, these would be seen as different notes (i.e. the
    note with hash 2222 was removed, and the note with hash 4444 was added,
    coincidentally in the same spot in the file). This makes a difference when
    scheduling the note review."""
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
                                          inbox_name = ?,
                                          reviewed_count = ?,
                                          note_state = ?
                         where sha1sum = ?""",
                      (line_number_start, line_number_end, 300, INITIAL_INTERVAL,
                       datetime.date.today(), datetime.date.today(),
                       inbox_name, 0, "just created", sha1sum))
        else:
            # The note content is new.
            note_number += 1
            interval_anchor = datetime.date.today()
            if initial_import:
                interval_extra_offset = int(min(1, 100/inbox_size) * note_number)
                interval_anchor += datetime.timedelta(days=interval_extra_offset)
            try:
                c.execute("insert into notes (%s) values (%s)"
                          % (", ".join(DB_COLUMNS),
                             ", ".join(["?"]*len(DB_COLUMNS))),
                          Note(sha1sum, note_text, line_number_start,
                               line_number_end, ease_factor=300, interval=INITIAL_INTERVAL,
                               last_reviewed_on=datetime.date.today(),
                               interval_anchor=interval_anchor,
                               inbox_name=inbox_name,
                               created_on=datetime.date.today(),
                               reviewed_count=0,
                               note_state="just created"))
            except sqlite3.IntegrityError:
                print("Duplicate note text found! Please remove all duplicates and then re-import.", inbox_name, note_text, file=sys.stderr)
                sys.exit()
    conn.commit()
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
    print("%s notes were soft-deleted... " % (delete_count,), file=sys.stderr,
          end="")


def due_notes(notes_db):
    result = []
    for note in notes_db:
        if note.interval < 0:
            # This note was soft-deleted, so don't include in reviews
            continue
        due_date = (yyyymmdd_to_date(note.interval_anchor) +
                    datetime.timedelta(days=note.interval))
        if datetime.date.today() >= due_date:
            result.append(note)
    return result

def get_recent_unreviewed_note(notes_db):
    """Randomly select a note that was created in the last 50-100 days and has
    not yet been reviewed yet."""
    candidates = []
    for note in notes_db:
        days_since_created = (datetime.date.today() - yyyymmdd_to_date(note.created_on)).days
        if (note.interval > 0 and note.note_state == "just created" and
            days_since_created >= 50 and days_since_created <= 100):
            candidates.append(note)
    if not candidates:
        return None
    return random.choice(candidates)

def get_exciting_note(notes_db):
    candidates = []
    weights = []
    for note in notes_db:
        days_since_reviewed = (datetime.date.today() - yyyymmdd_to_date(note.last_reviewed_on)).days
        days_overdue = days_since_reviewed - 50 * 2.5**note.reviewed_count
        if note.interval > 0 and note.note_state == "exciting" and days_overdue > 0:
            candidates.append(note)
            # We allow any exciting and overdue note to be selected, but weight
            # the probabilities so that the ones that are more overdue are more
            # likely to be selected.
            weights.append(days_overdue**2)

    if not candidates:
        return None
    return random.choices(candidates, weights, k=1)[0]

def get_all_other_note(notes_db):
    candidates = []
    weights = []
    for note in notes_db:
        days_since_reviewed = (datetime.date.today() - yyyymmdd_to_date(note.last_reviewed_on)).days
        days_overdue = days_since_reviewed - 50 * 2.5**note.reviewed_count
        if note.interval > 0 and note.note_state not in ["just created", "exciting"] and days_overdue > 0:
            candidates.append(note)
            weights.append(days_overdue**2)
    if not candidates:
        return None
    return random.choices(candidates, weights, k=1)[0]

def print_due_notes(notes):
    n = len(notes)
    for i, note in enumerate(notes):
        if i == n-1:
            # The motivation here is the following: it's way simpler
            # to review items using the printed output rather than
            # having to change windows to the text editor, manually
            # type the line, then review it there. If no editing needs
            # to take place, it's better to see more of the final note
            # so that you can just do "n good".
            print("===================================================")
            fragment = initial_fragment(note.note_text, 120)
        else:
            fragment = initial_fragment(note.note_text)
        print("%s. %s L%s-%s [good: %s, again: %s] %s"
              % (i+1, note.inbox_name,
                 note.line_number_start, note.line_number_end,
                 human_friendly_time(good_interval(note.interval,
                                                   note.ease_factor)),
                 human_friendly_time(again_interval(note.interval)),
                 fragment))


def interact_loop(conn, no_review, initial_import, external_program):
    while True:
        clear_screen()
        notes_db = reload_db(conn, initial_import)
        if no_review:
            break

        # Pick a note to review
        note = None
        rand = random.random()
        print("random number =", rand, file=sys.stderr)
        if rand < 0.5:
            print("Attempting to choose a recent unreviewed note...", end="", file=sys.stderr)
            note = get_recent_unreviewed_note(notes_db)
            if note is None:
                print("failed.", file=sys.stderr)
            else:
                print("success.", file=sys.stderr)
        if note is None and rand < 0.7:
            print("Attempting to choose an exciting note...", end="", file=sys.stderr)
            note = get_exciting_note(notes_db)
            if note is None:
                print("failed.", file=sys.stderr)
            else:
                print("success.", file=sys.stderr)
        if note is None:
            print("Attempting to choose some other note...", end="", file=sys.stderr)
            note = get_all_other_note(notes_db)
            if note is None:
                print("failed.", file=sys.stderr)
            else:
                print("success.", file=sys.stderr)

        if note is None:
            print("No notes are due")
            break
        else:
            # print_due_notes(notes)
            print(note_repr(note))
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
                    INBOX_FILES[note.inbox_name].replace("\\", r"\\\\"),
                    loc
                )).replace("\n", " ").strip()
                emacsclient = "emacsclient"
                if os.name == "nt":
                    # Python on Windows is dumb and can't detect gitbash
                    # aliases so we have to get the full path of the executable
                    emacsclient = "C:/Program Files/Emacs/x86_64/bin/emacsclientw"
                p = subprocess.Popen([emacsclient, "-e", elisp], stdout=subprocess.PIPE)


        # "lg" stands for "last good" -- it automatically fills in the note
        # number for the last note displayed and does a "good" on it
        command = input("Enter a command ('[e]xciting', '[m]eh', '[c]ringe', '[t]axing', '[r]efresh', '[q]uit'): ")
        # FIXME: actually this still allows bad input like "1 goodish" so fix
        # that
        if not re.match(r"e|m|c|t|r|q", command):
            print("Not a valid command", file=sys.stderr)
            continue
        if command.strip() in ["r", "refresh"]:
            continue
        if command.strip() in ["q", "quit"]:
            break

        # FIXME: this doesn't currently prevent people from reviewing a card
        # multiple times in the same session, which would just keep bumping the
        # card more and more. I think if a card has already been reviewed in a
        # session, we should say something like "This card was already
        # reviewed".
        command_to_state = {
                'e': "exciting",
                'm': "meh",
                'c': "cringe",
                't': "taxing",
                }
        c = conn.cursor()
        new_interval = good_interval(note.interval, note.ease_factor)
        c.execute("""update notes set interval = ?,
                                      last_reviewed_on = ?,
                                      interval_anchor = ?,
                                      reviewed_count = ?,
                                      note_state = ?
                     where sha1sum = ?""",
                  (new_interval, datetime.date.today(), datetime.date.today(), note.reviewed_count + 1, command_to_state[command.strip()], note.sha1sum))
        conn.commit()
        print("You will next see this note in " +
              human_friendly_time(new_interval), file=sys.stderr)


def sha1sum(string):
    return hashlib.sha1(string.encode('utf-8')).hexdigest()


def initial_fragment(string, words=20):
    """Get the first `words` words from `string`, joining any linebreaks."""
    return " ".join(string.split()[:words])


def good_interval(interval, ease_factor):
    return int(interval * ease_factor/100)


def again_interval(interval):
    return int(interval * 0.90)


def human_friendly_time(days):
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

def yyyymmdd_to_date(string):
    return datetime.datetime.strptime(string, "%Y-%m-%d").date()


def note_repr(note):
    fragment = initial_fragment(note.note_text)
    string = "Note(%s L%s-%s interval=%s ease_factor=%s note_state=%s reviewed_count=%s created_on=%s last_reviewed_on=%s %s)" % (note.inbox_name,
            note.line_number_start,
            note.line_number_end,
            note.interval,
            note.ease_factor,
            note.note_state,
            note.reviewed_count,
            note.created_on,
            note.last_reviewed_on,
            fragment)
    return string


if __name__ == "__main__":
    main()
