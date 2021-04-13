#!/usr/bin/env python3

import datetime
import sqlite3
import sys

from script import DB_COLUMNS, Note


if __name__ == "__main__":
    DB_FILE = sys.argv[1]
    INBOX_NAME = sys.argv[2]
    MAX_REVIEWS_PER_DAY = int(sys.argv[3])

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()
fetched = cur.execute("""
    select {cols} from notes
    where
        inbox_name = '{inbox_name}' and
        interval >= 0
    """.format(
        cols=", ".join(DB_COLUMNS),
        inbox_name=INBOX_NAME
    )
).fetchall()
notes = [Note(*row) for row in fetched]

def get_due_date(note):
    # We use last_reviewed_on here instead of interval_anchor; it's the
    # "natural" review date. If we repeatedly smooth the schedule, then some
    # notes might get prioritized in weird ways were we to use interval_anchor.
    # Using last_reviewed_on should be more stable under multiple runs of the
    # smoother algorithm.
    last_reviewed_on = datetime.datetime.strptime(note.last_reviewed_on, "%Y-%m-%d").date()
    return last_reviewed_on + datetime.timedelta(days=note.interval)

due_dates = {}
for note in notes:
    due_on = get_due_date(note)
    due_dates[due_on] = due_dates.get(due_on, []) + [note]

today = datetime.date.today()
all_dates = sorted(list(due_dates.keys()))


# Now we move notes around so there aren't more than MAX_REVIEWS_PER_DAY notes due on any day
date = all_dates[0]
while True:
    next_date = date + datetime.timedelta(days=1)
    if date < today:
        due_dates[today] = due_dates.get(today, []) + due_dates.get(date, [])
        due_dates[date] = []
    if len(due_dates.get(date, [])) > MAX_REVIEWS_PER_DAY:
        # Find the notes that have the most early due dates (according to the
        # original scheduling) and keep them, while pushing others further
        # back.
        lst = sorted(due_dates.get(date, []), key=lambda note: get_due_date(note))
        due_dates[date] = lst[:MAX_REVIEWS_PER_DAY]
        if next_date not in due_dates:
            due_dates[next_date] = []
        due_dates[next_date] += lst[MAX_REVIEWS_PER_DAY:]

    # Break out of the loop if there are no dates further out. This is
    # guaranteed to terminate since there are a finite number of notes.
    if not any(d > date for d in due_dates):
        break
    date = next_date


cur = conn.cursor()
for date in due_dates:
    for note in due_dates[date]:
        cur.execute("""
                update notes set interval_anchor = ?
                where sha1sum = ?
        """,
        # We want to make the note due on date, so subtract the interval from
        # it, so that when we add back the interval we get date
        (date - datetime.timedelta(days=note.interval), note.sha1sum))
conn.commit()
