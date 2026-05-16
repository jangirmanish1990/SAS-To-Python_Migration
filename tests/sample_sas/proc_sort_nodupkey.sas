proc sort data=mortgages_raw out=mortgages_sorted nodupkey;
    by id;
run;
