# spaced inbox

Spaced inbox implements a minimal [writing inbox](https://notes.andymatuschak.org/z5aJUJcSbxuQxzHr2YvaY4cX5TuvLQT7r27Dz) with support for spaced repetition. How does it work?

1. You write your notes in a plain text file. Two blank lines, or a line containing at least three equals signs (and nothing else) like `======`, are interpreted as the beginning of a new note.
2. You run `script.py --initial_import`. This imports your writing inbox into a database that manages the review schedule.
3. Every day, you run `script.py`, both to import new notes into the database and to review notes that are due. The "review" consists of a list of notes that are due on that day, along with line numbers that tell you where in the file they are located. You visit the location, edit/delete/do nothing, then tell `script.py` that you've reviewed the note. This is like pressing "Good" or "Again" in Anki, and will modify the review interval in a spaced manner.

That's it! There's no app or writing interface: you get to choose your favorite text editor, and write in whatever markup language you prefer.

The spacing algorithm is a simplified version of the one for [Anki/SM2](https://gist.github.com/riceissa/1ead1b9881ffbb48793565ce69d7dbdd).

## TODO

- there's a good chance I'll hate how interaction works (right now you have to manually go to the relevant line)
- notes identity is very crude right now: we just check the sha1 hash, so any modification to a note will turn it into a note with different identity, which means the review schedule will reset. I think there's a decent chance this is actually ok: the notes you modify are the notes you are actually engaging with, so you actually want them around more frequently.

## License

CC0. See `LICENSE` for details.
