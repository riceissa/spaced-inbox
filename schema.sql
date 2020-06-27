drop table if exists notes;

create table notes (
        id integer primary key autoincrement,
        sha1sum text unique not null,
        note_text text,
        line_number_start integer,
        line_number_end integer
);
