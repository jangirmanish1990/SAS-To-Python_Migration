data merged;
    merge left_ds(in=x) right_ds(in=y);
    by id;
    if x and y;
run;
