#!/bin/bash

echo -n "Number of notes: "
sqlite3 data.db 'select count(*) from notes where interval >= 0;'
echo "====="
python3 script.py --no-review
echo "====="
echo "Review load before smoothing:"
sqlite3 data.db 'select date(interval_anchor, "+" || interval || " day") as due_on, count(*) from notes where due_on not null group by due_on order by due_on asc limit 5;'
echo -n "Number of notes: "
sqlite3 data.db 'select count(*) from notes where interval >= 0;'
bash smooth.sh
echo "====="
echo "Review load after smoothing:"
sqlite3 data.db 'select date(interval_anchor, "+" || interval || " day") as due_on, count(*) from notes where due_on not null group by due_on order by due_on asc limit 5;'
echo -n "Number of notes: "
sqlite3 data.db 'select count(*) from notes where interval >= 0;'
