#!/bin/bash

echo "Note: this script was useful prior to 2023-01-12 when"
echo "the scheduling algorithm was worse in many ways. But"
echo "it's not necessary now. So I am commenting out the"
echo "code to prevent myself from accidentally running it."

# echo -n "Number of notes: "
# sqlite3 data.db 'select count(*) from notes where interval >= 0;'
# echo "====="
# python3 script.py --no-review
# echo "====="
# echo "Review load before smoothing:"
# sqlite3 data.db 'select date(interval_anchor, "+" || interval || " day") as due_on, count(*) from notes where due_on not null group by due_on order by due_on asc limit 5;'
# echo -n "Number of notes: "
# sqlite3 data.db 'select count(*) from notes where interval >= 0;'
# bash smooth.sh
# echo "====="
# echo "Review load after smoothing:"
# sqlite3 data.db 'select date(interval_anchor, "+" || interval || " day") as due_on, count(*) from notes where due_on not null group by due_on order by due_on asc limit 5;'
# echo -n "Number of notes: "
# sqlite3 data.db 'select count(*) from notes where interval >= 0;'
