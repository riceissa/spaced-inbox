#!/bin/bash

echo "Note: this script was useful prior to 2023-01-12 when"
echo "the scheduling algorithm was worse in many ways. But"
echo "it's not necessary now. So I am commenting out the"
echo "code to prevent myself from accidentally running it."

# This is a sample smooth.sh file.  If your inbox file paths are different, you
# will need to edit the lines below.

# If I fall behind on reviews, run this script to limit the number of notes
# that are due.  If more inbox files are added at inbox_files.txt then I will
# need to copy those over into here as well.

# ./smooth_schedule.py data.db inbox 7
# ./smooth_schedule.py data.db ai-safety-inbox 2
# ./smooth_schedule.py data.db questions 1
# ./smooth_schedule.py data.db project-ideas 1
