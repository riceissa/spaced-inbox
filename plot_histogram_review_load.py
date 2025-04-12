#!/usr/bin/env python3

# This script displays a histogram of your future review load.

from pathlib import Path
import matplotlib.pyplot as plt
import datetime
import sqlite3
import sys


conn = sqlite3.connect(Path("~/.local/share/spaced-inbox/data.db").expanduser())
cur = conn.cursor()
data = cur.execute("select last_reviewed_on, interval, filepath from notes where interval >= 0")

filepaths = set()

due_ins = {}
for last_reviewed_on_str, interval, filepath in data:
    last_reviewed_on = datetime.datetime.strptime(last_reviewed_on_str, "%Y-%m-%d")
    due_on = last_reviewed_on + datetime.timedelta(days=interval)
    due_in = (due_on - datetime.datetime.today()).days
    due_ins[filepath] = due_ins.get(filepath, []) + [due_in]
    filepaths.add(filepath)

fig, axs = plt.subplots(1)

for filepath in filepaths:
    due_dict = {}
    for x in due_ins[filepath]:
        due_dict[x] = due_dict.get(x, 0) + 1
    xs = list(range(min(due_ins[filepath]), max(due_ins[filepath]) + 1))
    ys = []
    for x in xs:
        if x in due_dict:
            ys.append(due_dict[x])
        else:
            ys.append(0)
    axs.plot(xs, ys, label=filepath)


plt.xlabel("days in the future")
plt.ylabel("number of notes due for review on this day")
plt.legend(loc="upper right")
plt.show()
