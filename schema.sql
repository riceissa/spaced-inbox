drop table if exists notes;

create table notes (
        id integer primary key autoincrement,
        sha1sum text unique not null,
        note_text text,
        line_number_start integer,
        line_number_end integer,
        ease_factor integer,  /* as a percentage, defaults to 250% like in Anki */
        interval integer,  /* in days; -1 means the note has been soft-deleted */
        last_reviewed_on date,
        /* Usually the same as last_reviewed_on, but this allows us to
           keep track of the last date on which a card was reviewed
           separately from the scheduling calculation (which is calcualted
           as interval_anchor + interval). This is useful for smoothing
           out the review schedule (if we didn't know the
           last_reviewed_on date, then we might accidentally keep pushing
           certain cards out in the future without ever reviewing them). */
        interval_anchor date,
        /* This is the shortname name for the inbox text file */
        inbox_name text,

        created_on date,

        /* Number of times note has been reviewed; if a note is modified it is
           considered a different note, so this is actually the number of times
           a note has been "passed" on in reviews without modification */
        reviewed_count integer,

        /* Can be one of:
           - "just created"
           - "exciting" (want to keep thinking about this idea in the near
                future and add to it, but can't think of anything to add in
                this exact moment)
           - "meh"
           - "cringe"
           - "taxing" (too cognitively taxing to read/think about right now)

           The note state (except for "just created") also corresponds to the
           response that was given to the note when the note was
           last reviewed. */
        note_state text
);
