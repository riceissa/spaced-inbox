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

        created_on date,

        /* Number of times note has been reviewed; if a note is modified it is
           considered a different note, so this is actually the number of times
           a note has been "passed" on in reviews without modification */
        reviewed_count integer,

        /* Can be one of:
           - "normal"
           - "exciting" (want to keep thinking about this idea in the near
                future and add to it, but can't think of anything to add in
                this exact moment)
           - "interesting"
           - "meh"
           - "cringe"
           - "taxing" (too cognitively taxing to read/think about right now)
           - "yeah" (agreement)
           - "lol" (funny/amusing)

           The note state (except for "just created") also corresponds to the
           response that was given to the note when the note was
           last reviewed.

           The responses are intended to mimic the kinds of responses one would
           give upon reading a chat message from a friend... you would respond
           saying "yeah" or "that's cool" or whatever.  If you have a more
           detailed response, of course you can just edit the note! It's your
           writing inbox.  This "response as chat message" idea seems like
           a better way to conceive of inbox responses than e.g. Anki's
           Easy/Good/Hard/Again.  But I'm still actively thinking of
           what the correct "primitives" are or "how to conceptualize
           responses".  For more, see these links:
           - https://wiki.issarice.com/wiki/Interaction_reversal_between_knowledge-to-be-memorized_and_ideas-to-be-developed
           - https://wiki.issarice.com/wiki/Mapping_mental_motions_to_parts_of_a_spaced_repetition_algorithm
         */
        note_state text
);
