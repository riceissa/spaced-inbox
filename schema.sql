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
        interval_anchor date
);
