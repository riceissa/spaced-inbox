#!/usr/bin/env python3

import datetime
import sqlite3

import script

MAX_REVIEWS_PER_DAY = 5

conn = sqlite3.connect('data.db')
notes = [note for note in script.get_notes_from_db(conn) if note.interval >= 0]

def get_due_date(note):
    # actually maybe i should be using last_reviewed_on here instead; it's the
    # "natural" review date. if i repeatedly smooth the schedule, then some
    # notes might get prioritized in weird ways. using last_reviewed_on should
    # be more stable under multiple runs of the smoother algorithm.
    interval_anchor = datetime.datetime.strptime(note.interval_anchor, "%Y-%m-%d").date()
    return interval_anchor + datetime.timedelta(days=note.interval)

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
    if date < today:
        due_dates[today] += due_dates.get(date, [])
        due_dates[date] = []
    if len(due_dates.get(date, [])) > MAX_REVIEWS_PER_DAY:
        # Find the notes that have the most early due dates (according to the
        # original scheduling) and keep them, while pushing others further
        # back. TODO: Use the last_reviewed_on dates as tie breakers.
        lst = sorted(due_dates.get(date, []), key=lambda note: get_due_date(note))
        due_dates[date] = lst[:MAX_REVIEWS_PER_DAY]
        due_dates[date + datetime.timedelta(days=1)] = lst[MAX_REVIEWS_PER_DAY:]

    # TODO: break out of this loop if each later date has at most
    # MAX_REVIEWS_PER_DAY reviews due. that means there is nothing left to
    # smooth. actually, just break out if there's no dates further out.
    later_dates = [d for d in due_dates if d > date]
    if len(later_dates) == 0:
        break
    date = date + datetime.timedelta(days=1)


# cur = conn.cursor()
