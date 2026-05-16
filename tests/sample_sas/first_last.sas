data cc_analysis;
    set creditcard;
    by cc;
    if first.cc = 1 then count = 1;
    else count + 1;
    if last.cc = 1;
run;
