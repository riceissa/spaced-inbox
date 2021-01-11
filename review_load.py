#!/usr/bin/env python3

# This script displays a histogram of your future review load.

import matplotlib.pyplot as plt
import datetime
import sqlite3
import sys


conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()
data = cur.execute("select interval_anchor, interval from notes where interval >= 0")

due_ins = []
for interval_anchor_, interval in data:
    interval_anchor = datetime.datetime.strptime(interval_anchor_, "%Y-%m-%d")
    due_on = interval_anchor + datetime.timedelta(days=interval)
    due_in = (due_on - datetime.datetime.today()).days
    due_ins.append(due_in)

fig, axs = plt.subplots(2)

axs[0].hist(due_ins, bins=200)

due_dict = {}
for x in due_ins:
    due_dict[x] = due_dict.get(x, 0) + 1
xs = list(range(min(due_ins), max(due_ins) + 1))
ys = []
for x in xs:
    if x in due_dict:
        ys.append(due_dict[x])
    else:
        ys.append(0)
axs[1].plot(xs, ys)


plt.xlabel("days in the future")
plt.ylabel("number of notes due for review on this day")
plt.show()
