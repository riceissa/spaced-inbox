#!/usr/bin/env python3

import argparse
import shutil
import textwrap
import datetime
import re
import os
import os.path
import sys
import random
import sqlite3
from sqlite3 import Connection, Cursor
from io import TextIOWrapper
import hashlib
import subprocess
from collections import namedtuple
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
sys.stderr.reconfigure(encoding='utf-8')  # type: ignore

def print_terminal(string: str, file=None) -> None:
    terminal_width = shutil.get_terminal_size().columns
    wrapped = textwrap.fill(string, width=min(80, terminal_width), break_long_words=False, break_on_hyphens=False)
    print(wrapped, file=file)

CONFIG_FILE_PATH: Path = Path("~/.config/spaced-inbox/config.txt").expanduser()
DB_PATH: Path = Path("~/.local/share/spaced-inbox/data.db").expanduser()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
REVIEW_LOAD_PATH: Path = Path("~/.local/share/spaced-inbox/review-load.csv").expanduser()
INBOX_PATHS: list[Path] = []

if not CONFIG_FILE_PATH.exists():
    print_terminal(f"Config file not found! Please create a file at {CONFIG_FILE_PATH} containing the location(s) of your inbox.txt files. You can put one file path per line.")
    sys.exit()

# This value sets the initial interval in days.
INITIAL_INTERVAL: int = 50

# TODO: all the separate calls to .today() seem sketchy to me. if someone is
# doing reviews right before midnight, it's possible that a weird inconsistent
# state could be stored. possibly define it just once at the start of the
# script, although idk if that's a good idea either.

# TODO: one thing that smooth.sh did that the new-as-of-January-2023 version
# doesn't do is having different quotas for the different inbox text files. If
# I do a large import of a new "stream" like browser bookmarks or something,
# then the reviews will (after 50 days) probably get dominated by these browser
# bookmarks. There should be some way to be like "limit browser bookmarks to at
# most 1% of all reviews" or something.  For now this hasn't been a problem for
# me, but it is something I will probably want to handle at some point.
# I notice that I want to specify weights using different methods. For
# example, with something like browser bookmarks, i want to say "don't make
# this thing dominate the reviews". but i may also want to say something like
# "github projects ideas repo notes should get a bit of penalty because they
# tend to be boring".  A bit thing to keep in mind that some inbox files
# can contain WAY more notes than some others.

# TODO: i am realizing that i often purposely don't fix some typos on boring
# notes because i reason that if i *do* fix them then that will reset the
# review schedule to 50 days, which i don't want. maybe there should be some
# way to make trivial changes without affecting the review schedule.

DB_COLUMNS: list[str] = ['sha1sum', 'line_number_start', 'line_number_end',
                         'ease_factor', 'interval', 'last_reviewed_on',
                         'created_on', 'reviewed_count', 'note_state',
                         'filepath', 'note_text']

def is_yyyymmdd_date(s: str) -> bool:
    """If the string is a YYYY-MM-DD date string like "2025-03-30" then return
    True, otherwise return False."""
    match = re.match(r'(\d\d\d\d)-(\d\d)-(\d\d)$', s)
    if not match:
        return False
    year, month, day = map(int, match.groups())
    # This is not a perfect algorithm, but it will be good enough for our
    # purposes. Might fix it at some point.
    if year < 1960:
        return False
    if not (1 <= month <= 12):
        return False
    if not (1 <= day <= 31):
        return False
    return True

@dataclass
class React:
    date: datetime.date
    text: str

@dataclass
class Note:
    sha1sum: str
    line_number_start: int
    line_number_end: int
    ease_factor: int
    interval: int
    last_reviewed_on: datetime.date
    created_on: datetime.date
    reviewed_count: int
    note_state: str
    filepath: Path
    # TODO: I'm not sure if note_text should contain the reacts part of the raw
    # text or not. the sha1sum hash above definitely needs to exclude that
    # part. so then it might be confusing that sha1sum != hash(note_text),
    # rather it will be sha1sum == hash(reacts_removed(note_text)). The reason
    # I'm thinking in this direction is because the ParseChunk does have info
    # about reacts (since it was just parsed), but the db doesn't store
    # anything about reacts, so we just have to partially recollect what the
    # reacts were by using last_reviewed_on and note_state.
    note_text: str

    def __repr__(self) -> str:
        fragment = initial_fragment(self.note_text)
        string = f"Note({self.filepath}:L{self.line_number_start}-{self.line_number_end} interval={self.interval} ease_factor={self.ease_factor} note_state={self.note_state} reviewed_count={self.reviewed_count} created_on={self.created_on} last_reviewed_on={self.last_reviewed_on} {fragment})"
        return string

    def to_db_row(self):
        return (
            self.sha1sum,
            self.line_number_start,
            self.line_number_end,
            self.ease_factor,
            self.interval,
            self.last_reviewed_on.strftime("%Y-%m-%d"),
            self.created_on.strftime("%Y-%m-%d"),
            self.reviewed_count,
            self.note_state,
            str(self.filepath),
            self.note_text,
        )

@dataclass
class ParseChunk:
    note_text: str
    line_number_start: int
    line_number_end: int

    sha1sum: str = field(init=False)
    reacts: list[React] = field(init=False)

    def __post_init__(self) -> None:
        self.note_text = self.note_text.strip()

        # The date separator entries don't contain any actual content, so we
        # blank them out so that they will get filtered out and won't be stored
        # in the database.
        if is_yyyymmdd_date(self.note_text):
            self.note_text = ""
            self.sha1sum = sha1sum(self.note_text)
            return

        to_be_hashed = ""
        self.reacts = []
        for line in self.note_text.splitlines(keepends=True):
            match = re.match(r'(\d\d\d\d-\d\d-\d\d): #(exciting|interesting|meh|cringe|taxing|yeah|lol)$', line.strip())
            is_react = False
            if match:
                try:
                    self.reacts.append(React(
                        datetime.datetime.strptime(match.group(1), "%Y-%m-%d").date(),
                        match.group(2)
                    ))
                    is_react = True
                except ValueError:
                    # Failed to parse date, so must not be a reaction after all.
                    pass
            if not is_react:
                to_be_hashed += line
        self.reacts.sort(key=lambda r: r.date)
        self.sha1sum = sha1sum(to_be_hashed.strip())
        if not to_be_hashed:
            # The note consists solely of a reaction, so the actual note text
            # itself would be empty, so exclude such notes
            self.note_text = ""


if CONFIG_FILE_PATH.exists():
    with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("#"):
                # Lines starting with # are comments
                continue
            if not line.strip():
                # Skip blank lines as well
                continue
            path = Path(line.strip())
            if not (path.exists() and path.is_file()):
                print_terminal(f"Inbox file {path} not found! Are you sure it is a valid file? Make sure to expand out any abbreviations such as '~/'.", file=sys.stderr)
                sys.exit()
            INBOX_PATHS.append(path)

if not INBOX_PATHS:
    print_terminal(f"Inbox file not found! Does your {CONFIG_FILE_PATH} contain the locations of valid files?",
          file=sys.stderr)
    sys.exit()

def note_from_db_row(row, has_note_text=True) -> Note:
    if has_note_text:
        return Note(
            sha1sum=row[0],
            line_number_start=row[1],
            line_number_end=row[2],
            ease_factor=row[3],
            interval=row[4],
            last_reviewed_on=yyyymmdd_to_date(row[5]),
            created_on=yyyymmdd_to_date(row[6]),
            reviewed_count=row[7],
            note_state=row[8],
            filepath=row[9],
            note_text=row[10],
        )
    return Note(
        sha1sum=row[0],
        line_number_start=row[1],
        line_number_end=row[2],
        ease_factor=row[3],
        interval=row[4],
        last_reviewed_on=yyyymmdd_to_date(row[5]),
        created_on=yyyymmdd_to_date(row[6]),
        reviewed_count=row[7],
        note_state=row[8],
        filepath=row[9],
        note_text="",
    )


def get_notes_from_db(conn: Connection, fetch_note_text=True) -> list[Note]:
    cursor = conn.cursor()
    if fetch_note_text:
        query = f"select sha1sum, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on, created_on, reviewed_count, note_state, filepath, note_text from notes"
    else:
        query = f"select sha1sum, line_number_start, line_number_end, ease_factor, interval, last_reviewed_on, created_on, reviewed_count, note_state, filepath from notes"
    rows = cursor.execute(query).fetchall()
    result = [note_from_db_row(row, has_note_text=fetch_note_text) for row in rows]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    format_help = "The printed format is <filename>:<line number>:<column number>:<starting fragment of the note>. This format is intended to be used by text editors such as Vim and Emacs."
    parser.add_argument("-c", "--compile",
                        help=(f"Print all the \"due\" notes. {format_help} Essentially, this flag allows this script to act like a \"compiler\" for your notes, allowing you to jump to whichever \"due\" note you select (as long as your text editor supports navigating such output)."),
                        action="store_true")
    parser.add_argument("-r", "--roll",
                        help=(f"Pick a random note to review. The note is chosen by the scheduling algorithm. Repeatedly running the script with this flag will allow you to do a \"review session\" where you review and edit notes in a sequence. {format_help}"),
                        action="store_true")
    args = parser.parse_args()
    if args.compile and args.roll:
        print_terminal("You cannot use both --compile/-c and --roll/-r simultaneously, as they both change how the output is printed. Please pick one or the other.", file=sys.stderr)
        sys.exit()
    if not (DB_PATH.exists() and DB_PATH.is_file()):
        script_dir = Path(__file__).parent.absolute()
        schema_location = script_dir / "schema.sql"
        with open(schema_location, "r", encoding="utf-8") as f:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.executescript(f.read())
    else:
        conn = sqlite3.connect(DB_PATH)

    if args.roll:
        notes_from_db = reload_db(conn, log_level=0)
        note: Note | None = pick_note_to_review(notes_from_db, log_level=0)
        if note:
            inbox_file = note.filepath
            line_number = note.line_number_start
            column_number = 1
            line_fragment = initial_fragment(note.note_text)
            print(f"{inbox_file}:{line_number}:{column_number}:{line_fragment}")
    elif args.compile:
        notes_from_db = reload_db(conn, log_level=0)
        for note in sorted(due_notes(notes_from_db), key=lambda n: (n.filepath, n.line_number_start)):
            inbox_file = note.filepath
            line_number = note.line_number_start
            column_number = 1
            line_fragment = initial_fragment(note.note_text)
            print(f"{inbox_file}:{line_number}:{column_number}:{line_fragment}")
    else:
        # The following (i.e. not passing in any flags, the default action) is
        # useful if you just want to import new notes as a cronjob or
        # something, and don't want to do a review.
        notes_from_db = reload_db(conn)
        num_notes, num_due_notes = calc_stats(notes_from_db)
        print("Number of notes:", num_notes)
        print("Number of notes that are due:", num_due_notes)
        record_review_load(num_notes, num_due_notes)

def tag_with_filename(filepath: Path) -> Callable[[ParseChunk], tuple[Path, ParseChunk]]:
    def tag_it(pc: ParseChunk) -> tuple[Path, ParseChunk]:
        return (filepath, pc)
    return tag_it


def reload_db(conn: Connection, log_level=1) -> list[Note]:
    current_inbox: list[tuple[Path, ParseChunk]] = []
    for path in INBOX_PATHS:
        if log_level > 0:
            print(f"Importing new notes from {path}... ", file=sys.stderr,
                  end="")
        with open(path, "r", encoding="utf-8") as f:
            current_inbox.extend(map(tag_with_filename(path),
                                     parse_inbox(f)))
        if log_level > 0:
            print("done.", file=sys.stderr)
    updated = update_notes_db(conn, current_inbox, log_level)

    # After we update the db using the current inbox, we must query the db
    # again since the due dates for some of the notes may have changed (e.g.
    # some notes may have been deleted). This fixes a bug where if a note is
    # due, then I edit it and type 'quit' and then re-run the script, the note
    # is still due.
    # combined_notes_db = get_notes_from_db(conn)
    return updated


def clear_screen() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')


def parse_inbox(lines: TextIOWrapper) -> list[ParseChunk]:
    """Parsing rules:
    - two or more blank lines in a row start a new note
    - a line with three or more equals signs and nothing else starts a new note
    """
    result: list[ParseChunk] = []
    note_text = ""
    state = "text"
    # This is a finite state machine with three states (text, 1 newline, 2+
    # newline) and three actions (text, blank, ===+).
    line_number = 0
    line_number_start = 1
    for raw_line in lines:
        line = raw_line.strip()
        line_number += 1
        if state == "text":
            if not line:
                state = "1 newline"
            elif re.match("===+$", line):
                state = "2+ newline"
            else:
                # state remains the same
                note_text += line + "\n"
        elif state == "1 newline":
            if (not line) or re.match("===+$", line):
                state = "2+ newline"
            else:
                state = "text"
                note_text += "\n" + line + "\n"
        else:
            assert state == "2+ newline"
            if line and not re.match("===+$", line):
                state = "text"
                result.append(ParseChunk(note_text, line_number_start,
                                         line_number - 1))
                line_number_start = line_number
                note_text = line + "\n"
            # else: state remains the same
    # We ended the loop above without adding the final note, so add it now
    result.append(ParseChunk(note_text, line_number_start, line_number))
    # Filter out blank notes
    result = [pc for pc in result if pc.note_text]
    return result


def _print_lines(string: str) -> None:
    """Print a string with line numbers (for debugging parse_inbox)."""
    line_number = 0
    for line in string.split("\n"):
        line_number += 1
        print(line_number, line)


def update_notes_db(conn: Connection, current_inbox: list[tuple[Path, ParseChunk]], log_level=1) -> list[Note]:
    """
    Add new notes to db.
    Remove notes from db if they no longer exist in the notes file?
    Return the new notes by combining the current inbox and what's already in the db.
    """
    result: list[Note] = []
    if log_level > 0:
        print("Updating the database with the contents of the new inbox files... ", end="", file=sys.stderr)
    c = conn.cursor()
    notes_from_db = get_notes_from_db(conn, fetch_note_text=False)
    db_hashes = {note.sha1sum: note for note in notes_from_db}
    note_number = 0
    unchanged_number = 0
    new_react_added_number = 0
    resurrected_number = 0
    inbox_size = len(current_inbox)

    inbox_filepath: Path
    pc: ParseChunk
    for inbox_filepath, pc in current_inbox:
        note_from_db: Note = db_hashes[pc.sha1sum]
        if pc.sha1sum in db_hashes and note_from_db.interval >= 0:
            # The note content is not new, but the following things may have
            # changed:
            #     - the file in which the note appears
            #     - the position in the file
            #     - new reacts may have been added, which means interval,
            #       last_reviewed_on, reviewed_count, and note_state
            #       need to be changed
            # So we need to update these things.
            new_interval = note_from_db.interval
            new_last_reviewed_on = note_from_db.last_reviewed_on
            new_reviewed_count = note_from_db.reviewed_count
            new_note_state = note_from_db.note_state
            if pc.reacts and pc.reacts[-1].date > note_from_db.last_reviewed_on:
                new_interval = good_interval(note_from_db.interval, note_from_db.ease_factor)
                new_last_reviewed_on = pc.reacts[-1].date
                new_reviewed_count += 1
                new_note_state = pc.reacts[-1].text
                new_react_added_number += 1
            else:
                unchanged_number += 1
            result.append(Note(pc.sha1sum, pc.line_number_start, pc.line_number_end, note_from_db.ease_factor, new_interval, new_last_reviewed_on, note_from_db.created_on, new_reviewed_count, new_note_state, inbox_filepath, pc.note_text))
            c.execute("""update notes set line_number_start = ?,
                                          line_number_end = ?,
                                          filepath = ?,
                                          interval = ?,
                                          last_reviewed_on = ?,
                                          reviewed_count = ?,
                                          note_state = ?,
                                          note_text = ?
                         where sha1sum = ?""", (
                                          pc.line_number_start,
                                          pc.line_number_end,
                                          str(inbox_filepath),
                                          new_interval,
                                          new_last_reviewed_on.strftime("%Y-%m-%d"),
                                          new_reviewed_count,
                                          new_note_state,
                                          pc.note_text,
                         pc.sha1sum,
            ))
        elif pc.sha1sum in db_hashes:
            # The note content is not new but the same note content was
            # previously added and then soft-deleted from the db, so we want to
            # reset the review schedule.
            c.execute("""update notes set line_number_start = ?,
                                          line_number_end = ?,
                                          ease_factor = ?,
                                          interval = ?,
                                          last_reviewed_on = ?,
                                          reviewed_count = ?,
                                          note_state = ?,
                                          filepath = ?,
                                          note_text
                         where sha1sum = ?""", (
                                          pc.line_number_start,
                                          pc.line_number_end,
                                          300,
                                          INITIAL_INTERVAL,
                                          datetime.date.today().strftime("%Y-%m-%d"),
                                          0,
                                          "normal",
                                          str(inbox_filepath),
                                          pc.note_text,
                         pc.sha1sum))
            resurrected_number += 1
            result.append(Note(pc.sha1sum, pc.line_number_start, pc.line_number_end, 300, INITIAL_INTERVAL, datetime.date.today(), note_from_db.created_on, 0, "normal", inbox_filepath, pc.note_text))
        else:
            # The note content is new.
            note_number += 1
            try:
                new_note = Note(sha1sum=pc.sha1sum,
                               line_number_start=pc.line_number_start,
                               line_number_end=pc.line_number_end,
                               ease_factor=300,
                               interval=INITIAL_INTERVAL,
                               last_reviewed_on=datetime.date.today(),
                               created_on=datetime.date.today(),
                               reviewed_count=0,
                               note_state="normal",
                               filepath=inbox_filepath,
                               note_text=pc.note_text,
                            )
                c.execute("insert into notes (%s) values (%s)"
                          % (", ".join(DB_COLUMNS),
                             ", ".join(["?"]*len(DB_COLUMNS))),
                          new_note.to_db_row())
                result.append(new_note)
            except sqlite3.IntegrityError:
                print("Duplicate note text found! Please remove all duplicates and then re-import.", pc.note_text, file=sys.stderr)
                sys.exit()
    if log_level > 0:
        print(f"{note_number} new notes found, ", file=sys.stderr, end="")
        print(f"{new_react_added_number} pre-existing notes got a new react, ", file=sys.stderr, end="")
        print(f"{resurrected_number} notes were resurrected, ", file=sys.stderr, end="")
        print(f"{unchanged_number} notes were completely unchanged other than potentially their location, ", file=sys.stderr, end="")

    # Soft-delete any notes that no longer exist in the current inbox
    inbox_hashes = set(pc.sha1sum for _, pc in current_inbox)
    delete_count = 0
    for note in notes_from_db:
        if note.sha1sum not in inbox_hashes and note.interval >= 0:
            delete_count += 1
            c.execute("update notes set interval = -1 where sha1sum = ?",
                      (note.sha1sum,))
    conn.commit()
    if log_level > 0:
        print(f"{delete_count} notes were soft-deleted... ", file=sys.stderr,
              end="")
        print("done.", file=sys.stderr)
    return result


def due_notes(notes_from_db: list[Note]) -> list[Note]:
    result = []
    for note in notes_from_db:
        if note.interval < 0:
            # This note was soft-deleted, so don't include in reviews
            continue
        due_date = (note.last_reviewed_on +
                    datetime.timedelta(days=note.interval))
        if datetime.date.today() >= due_date:
            result.append(note)
    return result

def get_recent_unreviewed_note(notes_from_db: list[Note]) -> Note | None:
    """Randomly select a note that was created in the last 50-100 days and has
    not yet been reviewed yet."""
    candidates = []
    for note in notes_from_db:
        # FIXME: I suspect using days_since_created here actually causes a
        # problem, where even if a note has been reviewed, it will still keep
        # showing up in reviews. So I need to add a check for when the note was
        # last reviewed as well, I think.
        # 2025-03-30: Actually, I was mistaken in there being a bug here. The
        # only time a note has the "normal" state is when it has just been
        # created. So as soon as the note gets reviewed, it will no longer have
        # that state, so it will never be picked here. HOWEVER, I'm planning to
        # store the responses "in bound" inside the inbox.txt file itself,
        # which means notes CAN have a "normal" state now even though they've
        # been reviewed. So it WILL become a bug soon.
        days_since_created = (datetime.date.today() - note.created_on).days
        if (note.interval > 0 and note.note_state == "normal" and
            days_since_created >= INITIAL_INTERVAL and days_since_created <= 2*INITIAL_INTERVAL):
            candidates.append(note)
    if not candidates:
        return None
    return random.choice(candidates)

def get_exciting_note(notes_from_db: list[Note]) -> Note | None:
    candidates = []
    weights = []
    for note in notes_from_db:
        days_since_reviewed = (datetime.date.today() - note.last_reviewed_on).days
        days_overdue = days_since_reviewed - INITIAL_INTERVAL * 2.5**note.reviewed_count
        if note.interval > 0 and note.note_state == "exciting" and days_overdue > 0:
            candidates.append(note)
            # We allow any exciting and overdue note to be selected, but weight
            # the probabilities so that the ones that are more overdue are more
            # likely to be selected.
            # TODO: I need to learn more about what sensible weights for this
            # are.
            weights.append(days_overdue**2)

    if not candidates:
        return None
    return random.choices(candidates, weights, k=1)[0]

# TODO: I only deal with "normal" and "exciting" notes specially. But
# there's support for more reactions to notes during review. Eventually, I'd
# like to incorporate these other reactions into the review algo as well.

def get_all_other_note(notes_from_db: list[Note]) -> Note | None:
    candidates = []
    weights = []
    for note in notes_from_db:
        days_since_reviewed = (datetime.date.today() - note.last_reviewed_on).days
        days_overdue = days_since_reviewed - INITIAL_INTERVAL * 2.5**note.reviewed_count
        if note.interval > 0 and note.note_state not in ["exciting"] and days_overdue > 0:
            candidates.append(note)
            # TODO: I need to learn more about what sensible weights for this
            # are.  For example, maybe if a note has a longer interval then
            # it can be further delayed because it's already been so long
            # since you last saw the note.  So the weight should possibly
            # containt some percentage of the interval.
            weights.append(days_overdue**2)
    if not candidates:
        return None
    return random.choices(candidates, weights, k=1)[0]

def pick_note_to_review(notes: list[Note], log_level=1) -> Note | None:
    note: Note | None = None
    rand = random.random()
    if log_level > 0:
        print("random number =", rand, file=sys.stderr)
    if rand < 0.5:
        if log_level > 0:
            print("Attempting to choose a recent unreviewed note...",
                  end="", file=sys.stderr)
        note = get_recent_unreviewed_note(notes)
        if note is None:
            if log_level > 0:
                print("failed.", file=sys.stderr)
        else:
            if log_level > 0:
                print("success.", file=sys.stderr)
    if note is None and rand < 0.7:
        if log_level > 0:
            print("Attempting to choose an exciting note...", end="",
                  file=sys.stderr)
        note = get_exciting_note(notes)
        if note is None:
            if log_level > 0:
                print("failed.", file=sys.stderr)
        else:
            if log_level > 0:
                print("success.", file=sys.stderr)
    if note is None:
        if log_level > 0:
            print("Attempting to choose some other note...", end="",
                  file=sys.stderr)
        note = get_all_other_note(notes)
        if note is None:
            if log_level > 0:
                print("failed.", file=sys.stderr)
        else:
            if log_level > 0:
                print("success.", file=sys.stderr)
    return note

def calc_stats(notes: list[Note]) -> tuple[int, int]:
    num_notes = 0
    num_due_notes = 0
    note: Note | None
    for note in notes:
        if note.interval > 0:
            num_notes += 1
            days_since_reviewed = (datetime.date.today() - note.last_reviewed_on).days
            days_overdue = days_since_reviewed - INITIAL_INTERVAL * 2.5**note.reviewed_count
            if days_overdue > 0:
                num_due_notes += 1
    return (num_notes, num_due_notes)

def record_review_load(num_notes: int, num_due_notes: int) -> None:
    if not (REVIEW_LOAD_PATH.exists() and REVIEW_LOAD_PATH.is_file()):
        with open(REVIEW_LOAD_PATH, "w", encoding="utf-8") as review_load_file:
            review_load_file.write("timestamp,num_notes,num_due_notes\n")
    with open(REVIEW_LOAD_PATH, "a", encoding="utf-8") as review_load_file:
        review_load_file.write("%s,%s,%s\n" % (datetime.datetime.now().isoformat(), num_notes, num_due_notes))

def interact_loop(conn: Connection) -> None:
    no_review = False
    external_program = ""
    while True:

        note: Note | None = None
        if note is None:
            print("No notes are due")
            break
        else:
            print(note)
            if external_program == "emacs":
                loc = note.line_number_start
                elisp = ("""
                    (with-current-buffer
                        (window-buffer (selected-window))
                      (find-file "%s")
                      (goto-line %s)
                      (recenter-top-bottom 0))
                """ % (
                    # since the db only stores the inbox name, we must look up
                    # the filepath from INBOX_FILES
                    "FIXME", # INBOX_FILE.replace("\\", r"\\\\"),
                    loc
                )).replace("\n", " ").strip()
                emacsclient = "emacsclient"
                if os.name == "nt":
                    # Python on Windows is dumb and can't detect gitbash
                    # aliases so we have to get the full path of the executable
                    emacsclient = "C:/Program Files/Emacs/emacs-29.4/bin/emacsclientw"
                p = subprocess.Popen([emacsclient, "-e", elisp], stdout=subprocess.PIPE)


        command = input("Enter a command ('[e]xciting', '[i]nteresting', '[m]eh', '[c]ringe', '[t]axing', '[y]eah', '[l]ol', '[r]eroll', '[q]uit'): ")
        if not re.match(r"e|i|m|c|t|y|l|r|q", command):
            print("Not a valid command", file=sys.stderr)
            continue
        if command.strip() in ["r", "refresh", "reroll"]:
            continue
        if command.strip() in ["q", "quit"]:
            break

        command_to_state = {
                'e': "exciting",
                'i': "interesting",
                'm': "meh",
                'c': "cringe",
                't': "taxing",
                'y': "yeah",
                'l': "lol",
                }
        c = conn.cursor()
        new_interval = good_interval(note.interval, note.ease_factor)
        c.execute("""update notes set interval = ?,
                                      last_reviewed_on = ?,
                                      reviewed_count = ?,
                                      note_state = ?
                     where sha1sum = ?""",
                  (new_interval, datetime.date.today().strftime("%Y-%m-%d"), note.reviewed_count + 1, command_to_state[command.strip()], note.sha1sum))
        conn.commit()
        print("You will next see this note in " +
              human_friendly_time(new_interval), file=sys.stderr)


def sha1sum(string: str) -> str:
    return hashlib.sha1(string.encode('utf-8')).hexdigest()


def initial_fragment(string: str, words: int = 20) -> str:
    """Get the first `words` words from `string`, joining any linebreaks."""
    return " ".join(string.split()[:words])


def good_interval(interval: int, ease_factor: int) -> int:
    return int(interval * ease_factor/100)


def again_interval(interval: int) -> int:
    return int(interval * 0.90)


def human_friendly_time(days: float) -> str:
    if days < 0:
        return "-" + human_friendly_time(abs(days))
    elif days * 24 * 60 < 1:
        return str(round(days * 24 * 60 * 60, 2)) + " seconds"
    elif days * 24 < 1:
        return str(round(days * 24 * 60, 2)) + " minutes"
    elif days < 1:
        return str(round(days * 24, 2)) + " hours"
    elif days < 30:
        return str(round(days, 2)) + " days"
    elif days < 365:
        return str(round(days / (365.25 / 12), 2)) + " months"
    else:
        return str(round(days / 365.25, 2)) + " years"

def yyyymmdd_to_date(string: str) -> datetime.date:
    return datetime.datetime.strptime(string, "%Y-%m-%d").date()


if __name__ == "__main__":
    main()
