/* This is a block comment */
data out; /* inline comment */
    set inp;
    where x = 1; /* filter */
    * This is a line comment;
    y = x * 2;
run;
