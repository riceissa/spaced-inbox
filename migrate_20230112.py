#!/usr/bin/env python3

# Script to import an old database (pre-January 2023) to the new database
# schema.

import pdb

import sqlite3
import datetime
import os
import os.path
import sys
from math import log, ceil
from collections import namedtuple

Note = namedtuple('Note', ['sha1sum', 'note_text', 'line_number_start', 'line_number_end', 'ease_factor', 'interval', 'last_reviewed_on', 'interval_anchor', 'inbox_name'])

sys.stdout.reconfigure(encoding='utf-8')

conn_old = sqlite3.connect('data-2023-01-12.db.bak')
c_old = conn_old.cursor()

conn_new = sqlite3.connect('data_new.db')
c_new = conn_new.cursor()
with open("schema.sql", "r", encoding="utf-8") as f:
    c_new.executescript(f.read())

fetched = c_old.execute("""
        select sha1sum, note_text, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on, interval_anchor, inbox_name from notes
        """).fetchall()

for row_ in fetched:
    row = Note(*row_)
    # pdb.set_trace()
    # Guess using the interval; we find the smallest k such that
    # interval/2.5^k < 50.  Just solve for k.
    if row.interval == 60 or row.interval == 50:
        reviewed_count = 0
    elif row.interval > 0:
        reviewed_count = max(0, ceil(log(row.interval/50)/log(2.5)))
    else:
        reviewed_count = 0

    note_state = "just created" if reviewed_count == 0 else "meh"

    c_new.execute("""
            insert into notes (sha1sum, note_text, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on, interval_anchor, inbox_name, created_on, reviewed_count, note_state) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row.sha1sum, row.note_text, row.line_number_start,
             row.line_number_end, row.ease_factor, row.interval,
             row.last_reviewed_on, row.interval_anchor,
             row.inbox_name,
             row.last_reviewed_on, # we can't find this info so just give up and use the last reviewed date
             reviewed_count,
             note_state
             ))

conn_new.commit()
