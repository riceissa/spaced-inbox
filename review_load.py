#!/usr/bin/env python3

import matplotlib.pyplot as plt
import datetime
import sqlite3


conn = sqlite3.connect('data.db')
cur = conn.cursor()
data = cur.execute("select last_reviewed_on, interval from notes where interval >= 0")

due_ins = []
for last_reviewed_on_, interval in data:
    last_reviewed_on = datetime.datetime.strptime(last_reviewed_on_, "%Y-%m-%d")
    due_on = last_reviewed_on + datetime.timedelta(days=interval)
    due_in = (due_on - datetime.datetime.today()).days
    due_ins.append(due_in)

plt.hist(due_ins, bins=200)
plt.show()


