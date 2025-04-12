#!/usr/bin/env python3

# This script displays a histogram of your future review load.

import matplotlib.pyplot as plt
import datetime
import sqlite3
import sys


conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()
data = cur.execute("select last_reviewed_on, interval, filepath from notes where interval >= 0")

names = set()

due_ins = {}
for interval_anchor_, interval, name in data:
    interval_anchor = datetime.datetime.strptime(interval_anchor_, "%Y-%m-%d")
    due_on = interval_anchor + datetime.timedelta(days=interval)
    due_in = (due_on - datetime.datetime.today()).days
    due_ins[name] = due_ins.get(name, []) + [due_in]
    names.add(name)

fig, axs = plt.subplots(1)

for name in names:
    due_dict = {}
    for x in due_ins[name]:
        due_dict[x] = due_dict.get(x, 0) + 1
    xs = list(range(min(due_ins[name]), max(due_ins[name]) + 1))
    ys = []
    for x in xs:
        if x in due_dict:
            ys.append(due_dict[x])
        else:
            ys.append(0)
    axs.plot(xs, ys, label=name)


plt.xlabel("days in the future")
plt.ylabel("number of notes due for review on this day")
plt.legend(loc="upper right")
plt.show()
