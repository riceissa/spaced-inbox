#!/bin/bash

# This is a sample smooth.sh file.  If your inbox file paths are different, you
# will need to edit the lines below.

# If I fall behind on reviews, run this script to limit the number of notes
# that are due.  If more inbox files are added at inbox_files.txt then I will
# need to copy those over into here as well.

./smooth_schedule.py data.db /home/issa/projects/notes/inbox.txt 5
./smooth_schedule.py data.db /home/issa/projects/notes/ai-safety-inbox.txt 2
./smooth_schedule.py data.db /home/issa/projects/notes/questions.txt 2
./smooth_schedule.py data.db /home/issa/projects/notes/project-ideas.txt 2
