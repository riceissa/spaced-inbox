#!/usr/bin/env python3

import re
import sqlite3
import hashlib


# conn = sqlite3.connect('data.db')
# c = conn.cursor()


def parse_inbox(string):
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
    for line in string:
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
                result.append((note, line_number_start, line_number - 1))
                line_number_start = line_number
                note = line + "\n"
            # else: state remains the same
    if state != "2+ newline":
        # We ended the loop above without two newlines, so process what we have
        result.append((note, line_number_start, line_number))
    return result



    # return a list of tuples (sha1, fragment, line_number_start, line_number_end)


def print_lines(string):
    line_number = 0
    for line in string.split("\n"):
        line_number += 1
        print(line_number, line)

def update_notes_db(note_tuples, context_based_identity=True):
    """

    Add new notes to db.
    Remove notes from db if they no longer exist in the notes file.

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
    # for (sha1, fragment, line_number_start, line_number_end) in note_tuples:
    #     add to sqlite db
    pass


def print_due_notes():
    # for note in [query from sqlite db]:
    #     a
    pass


def initial_fragment(string, words=20):
    """Get the first `words` words from `string`, joining any linebreaks."""
    pass
