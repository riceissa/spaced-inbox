#!/usr/bin/env python3

import datetime
import sqlite3
import sys

import script



MAX_REVIEWS_PER_DAY = 5
if __name__ == "__main__":
    DB_FILE = sys.argv[1]

conn = sqlite3.connect(DB_FILE)
notes = [note for note in script.get_notes_from_db(conn) if note.interval >= 0]

def get_due_date(note):
    # We use last_reviewed_on here instead of interval_anchor; it's the
    # "natural" review date. If I repeatedly smooth the schedule, then some
    # notes might get prioritized in weird ways we were to use interval_anchor.
    # Using last_reviewed_on should be more stable under multiple runs of the
    # smoother algorithm.
    last_reviewed_on = datetime.datetime.strptime(note.last_reviewed_on, "%Y-%m-%d").date()
    return last_reviewed_on + datetime.timedelta(days=note.interval)

due_dates = {}
for note in notes:
    due_on = get_due_date(note)
    if due_on in due_dates:
        due_dates[due_on] += [note]
    else:
        due_dates[due_on] = [note]

today = datetime.date.today()
all_dates = sorted(list(due_dates.keys()))


# Now we move notes around so there aren't more than five notes due on any day
date = all_dates[0]
while True:
    next_date = date + datetime.timedelta(days=1)
    if date < today:
        due_dates[today] += due_dates.get(date, [])
        due_dates[date] = []
    if len(due_dates.get(date, [])) > MAX_REVIEWS_PER_DAY:
        # Find the notes that have the most early due dates (according to the
        # original scheduling) and keep them, while pushing others further
        # back. TODO: Use the last_reviewed_on dates as tie breakers.
        lst = sorted(due_dates.get(date, []), key=lambda note: get_due_date(note))
        due_dates[date] = lst[:MAX_REVIEWS_PER_DAY]
        if next_date not in due_dates:
            due_dates[next_date] = []
        due_dates[next_date] += lst[MAX_REVIEWS_PER_DAY:]

    # TODO: break out of this loop if each later date has at most
    # MAX_REVIEWS_PER_DAY reviews due. that means there is nothing left to
    # smooth. actually, just break out if there's no dates further out.
    # This is guaranteed to terminate since there are a finite number of notes.
    later_dates = [d for d in due_dates if d > date]
    if len(later_dates) == 0:
        break
    date = next_date


cur = conn.cursor()
for date in due_dates:
    for note in due_dates[date]:
        cur.execute("""
                update notes set interval_anchor = ?
                where sha1sum = ?
        """,
        (date, note.sha1sum))
conn.commit()
