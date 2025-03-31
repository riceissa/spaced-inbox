#!/usr/bin/env python3

# Script to import an old database (pre-March 2025) to the new database
# schema.

import sys
import sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')  # type: ignore

DB_PATH: Path = Path("~/.local/share/spaced-inbox/data.db").expanduser()
backup_path = DB_PATH.parent / 'data-migrate_20250330.db.bak'
DB_PATH.rename(backup_path)

conn_old = sqlite3.connect(str(backup_path))
c_old = conn_old.cursor()

conn_new = sqlite3.connect(str(DB_PATH))
c_new = conn_new.cursor()
with open("schema.sql", "r", encoding="utf-8") as f:
    c_new.executescript(f.read())

fetched = c_old.execute("""
        select sha1sum, note_text, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on, interval_anchor, inbox_name, created_on, reviewed_count, note_state from notes
        """).fetchall()

for row in fetched:
    old_sha1sum = row[0]
    old_note_text = row[1]
    old_line_number_start = row[2]
    old_line_number_end = row[3]
    old_ease_factor = row[4]
    old_interval = row[5]
    old_last_reviewed_on = row[6]
    old_interval_anchor = row[7]  # not used
    old_inbox_name = row[8]  # not used
    old_created_on = row[9]
    old_reviewed_count = row[10]
    old_note_state = row[11]

    new_note_state = "normal" if old_note_state == "just created" else old_note_state
    c_new.execute("""
        insert into notes (sha1sum, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on, created_on, reviewed_count, note_state, filepath, note_text) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (old_sha1sum, old_line_number_start, old_line_number_end, old_ease_factor, old_interval, old_last_reviewed_on, old_created_on, old_reviewed_count, new_note_state, None, old_note_text))

conn_new.commit()
