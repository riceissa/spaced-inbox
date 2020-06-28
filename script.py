#!/usr/bin/env python3

import argparse
import datetime
import re
import os.path
import sys
import sqlite3
import hashlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial_import", help="Uniformly distribute new notes between days 50-150 rather than having everything due on day 50", action="store_true")
    parser.add_argument("--no_review", help="Just import new notes, without printing due notes or going into the review interact loop", action="store_true")
    args = parser.parse_args()
    if not os.path.isfile("data.db"):
        with open("schema.sql", "r") as f:
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            c.executescript(f.read())
    else:
        conn = sqlite3.connect('data.db')
        c = conn.cursor()

    notes_db  = c.execute("""select sha1sum, note_text, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on from notes""").fetchall()
    print("Importing new notes... ", file=sys.stderr, end="")
    with open("/home/issa/projects/notes/inbox.txt", "r") as f:
        current_inbox = parse_inbox(f)

    update_notes_db(conn, notes_db, current_inbox, initial_import=args.initial_import)
    print("done.", file=sys.stderr)

    if not args.no_review:
        items = due_notes(notes_db)
        print_due_notes(items)
        if len(items) == 0:
            print("No items are due")
        else:
            interact_loop(items, conn)

def sha1sum(string):
    return hashlib.sha1(string.encode('utf-8')).hexdigest()


def parse_inbox(lines):
    """Parsing rules:
    - two or more blank lines in a row start a new note
    - a line with three or more equals signs and nothing else starts a new note

    """
    result = []
    note = ""
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
                note += line + "\n"
        elif state == "1 newline":
            if (not line) or re.match("===+$", line):
                state = "2+ newline"
            else:
                state = "text"
                note += "\n" + line + "\n"
        else:
            assert state == "2+ newline"
            if line and not re.match("===+$", line):
                state = "text"
                result.append((sha1sum(note.strip()), note, line_number_start, line_number - 1))
                line_number_start = line_number
                note = line + "\n"
            # else: state remains the same
    # We ended the loop above without adding the final note, so add it now
    result.append((sha1sum(note.strip()), note, line_number_start, line_number))
    return result


def print_lines(string):
    """Print a string with line numbers (for debugging parse_inbox)."""
    line_number = 0
    for line in string.split("\n"):
        line_number += 1
        print(line_number, line)


def update_notes_db(conn, notes_db, current_inbox, initial_import=False, context_based_identity=False):
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
    db_hashes = set([sha1sum for (sha1sum, _, _, _, _, _, _) in notes_db])
    note_number = 0
    inbox_size = len(current_inbox)
    for (sha1, note, line_number_start, line_number_end) in current_inbox:
        if sha1 in db_hashes:
            # The note content is not new, but the position in the file may
            # have changed, so update the line numbers
            c.execute("""update notes set line_number_start = ?, line_number_end = ? where sha1sum = ?""",
                      (line_number_start, line_number_end, sha1))
        else:
            note_number += 1
            if initial_import:
                interval = int(50 + min(1, 100/inbox_size) * note_number)
            else:
                interval = 50
            c.execute("""insert into notes
                         (sha1sum, note_text, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on)
                         values (?, ?, ?, ?, ?, ?, ?)""",
                      (sha1, note, line_number_start, line_number_end, 250, interval, datetime.date.today()))
    conn.commit()
    print("%s new notes found... " % (note_number,), file=sys.stderr, end="")


def due_notes(notes_db):
    items = []
    for (sha1sum, note_text, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on) in notes_db:
        due_date = datetime.datetime.strptime(last_reviewed_on, "%Y-%m-%d").date() + datetime.timedelta(days=interval)
        if datetime.date.today() > due_date:
            items.append((sha1sum, line_number_start, line_number_end, initial_fragment(note_text), ease_factor, interval, last_reviewed_on))
    return items

def print_due_notes(items):
    item_number = 0
    for (_, line_number_start, line_number_end, fragment, ease_factor, interval, _) in items:
        item_number += 1
        print("%s. L%s-%s [good: %s, again: %s] %s" % (item_number, line_number_start, line_number_end, human_friendly_time(int(interval * ease_factor/100)), human_friendly_time(int(interval * 0.90)), fragment))


def interact_loop(items, conn):
    while True:
        command = input("Enter a command (e.g. '1 good', '1 again', 'quit'): ")
        if command.strip() == "quit":
            break
        xs = command.strip().split()
        item_number = int(xs[0])
        (sha1sum, _, _, _, ease_factor, interval, _) = items[item_number-1]
        item_action = xs[1]
        if item_action == "good":
            c = conn.cursor()
            new_interval = int(interval * ease_factor/100)
            c.execute("update notes set interval = ?, last_reviewed_on = ? where sha1sum = ?",
                      (new_interval, datetime.date.today(), sha1sum))
            conn.commit()
            print("You will next see this note in " + human_friendly_time(new_interval), file=sys.stderr)
        if item_action == "again":
            c = conn.cursor()
            new_interval = int(interval * 0.90)
            c.execute("update notes set interval = ?, last_reviewed_on = ?, ease_factor = ? where sha1sum = ?",
                      (new_interval, datetime.date.today(), int(max(130, ease_factor - 20)), sha1sum))
            print("You will next see this note in " + human_friendly_time(new_interval), file=sys.stderr)
            conn.commit()



def initial_fragment(string, words=20):
    """Get the first `words` words from `string`, joining any linebreaks."""
    return " ".join(string.split()[:words])

def human_friendly_time(days):
    if not days:
        return days
    if days < 1:
        return str(round(days * 24 * 60, 2)) + " minutes"
    elif days < 30:
        return str(round(days, 2)) + " days"
    elif days < 365:
        return str(round(days / (365.25 / 12), 2)) + " months"
    else:
        return str(round(days / 365.25, 2)) + " years"


if __name__ == "__main__":
    main()
