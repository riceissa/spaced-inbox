#!/usr/bin/env python3

# This script displays a histogram of your future review load.

import matplotlib.pyplot as plt
import datetime
import sqlite3
import sys


conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()
data = cur.execute("select interval_anchor, interval, filepath from notes where interval >= 0")

filepaths = set()

due_ins = {}
for interval_anchor_, interval, filepath in data:
    interval_anchor = datetime.datetime.strptime(interval_anchor_, "%Y-%m-%d")
    due_on = interval_anchor + datetime.timedelta(days=interval)
    due_in = (due_on - datetime.datetime.today()).days
    due_ins[filepath] = due_ins.get(filepath, []) + [due_in]
    filepaths.add(filepath)

fig, axs = plt.subplots(1)

for fp in filepaths:
    due_dict = {}
    for x in due_ins[fp]:
        due_dict[x] = due_dict.get(x, 0) + 1
    xs = list(range(min(due_ins[fp]), max(due_ins[fp]) + 1))
    ys = []
    for x in xs:
        if x in due_dict:
            ys.append(due_dict[x])
        else:
            ys.append(0)
    axs.plot(xs, ys, label=fp)


plt.xlabel("days in the future")
plt.ylabel("number of notes due for review on this day")
plt.legend(loc="upper right")
plt.show()
