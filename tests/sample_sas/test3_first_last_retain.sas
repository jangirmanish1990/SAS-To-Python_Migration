/* ============================================================
   TEST 3: FIRST./LAST. with RETAIN running sum
   Tests: BY group processing, FIRST./LAST., running sum,
          conditional output, nested BY groups
   Expected output target: pandas
   ============================================================ */

/* Sort first — required before FIRST./LAST. */
proc sort data=creditcard out=creditcard_sorted;
    by cc_type cc;
run;

/* Count swipes and total per card */
data cc_summary;
    set creditcard_sorted;
    by cc_type cc;

    if first.cc = 1 then do;
        swipe_count = 1;
        total_spend = swipe;
    end;
    else do;
        swipe_count + 1;
        total_spend + swipe;
    end;

    if last.cc = 1;
run;

/* Top 3 transactions per card */
proc sort data=creditcard out=sorted_by_swipe;
    by cc descending swipe;
run;

data top3_per_card;
    set sorted_by_swipe;
    by cc;

    if first.cc = 1 then rank = 1;
    else rank + 1;

    if rank le 3;
run;
