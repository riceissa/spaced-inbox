#!/bin/bash

# This is a sample smooth.sh file.  If your inbox file paths are different, you
# will need to edit the lines below.

# If I fall behind on reviews, run this script to limit the number of notes
# that are due.  If more inbox files are added at inbox_files.txt then I will
# need to copy those over into here as well.

./smooth_schedule.py data.db inbox 5
./smooth_schedule.py data.db ai-safety-inbox 2
./smooth_schedule.py data.db questions 1
./smooth_schedule.py data.db project-ideas 1
