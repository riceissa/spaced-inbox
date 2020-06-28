# spaced inbox

Spaced inbox implements a minimal [writing inbox](https://notes.andymatuschak.org/z5aJUJcSbxuQxzHr2YvaY4cX5TuvLQT7r27Dz) with support for spaced repetition. How does it work?

1. You write your notes in a plain text file. Two blank lines, or a line containing at least three equals signs (and nothing else) like `======`, are interpreted as the beginning of a new note.
2. You run `script.py`. This imports your writing inbox into a database that manages the review schedule.
3. Every day, you run `script.py`, both to import new notes into the database and to review notes that are due. The "review" consists of a list of notes that are due on that day, along with line numbers that tell you where in the file they are located. You visit the location, edit/delete/do nothing, then tell `script.py` that you've reviewed the file. This is like pressing "Good" or "Again" in Anki, and will modify the review interval in a spaced manner.


## License

CC0. See `LICENSE` for details.
