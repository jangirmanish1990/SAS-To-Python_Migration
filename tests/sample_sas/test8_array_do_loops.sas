/* ============================================================
   TEST 8: ARRAY and DO loops
   Tests: Static ARRAY, dynamic _numeric_ ARRAY,
          DO WHILE, DO UNTIL, COALESCE fill,
          POINT= random access
   Expected output target: pandas
   ============================================================ */

/* Fill missing exam scores with 0 using static array */
data exam_filled;
    set student_exams;
    array scores(5) sub1 sub2 sub3 sub4 sub5;

    do i = 1 to 5;
        scores(i) = coalesce(scores(i), 0);
    end;

    total_score = sum(of sub1-sub5);
    avg_score   = mean(of sub1-sub5);
    drop i;
run;

/* Fill all numeric columns dynamically */
data exam_filled2;
    set student_exams;
    array all_scores(*) _numeric_;

    do i = 1 to dim(all_scores);
        if all_scores(i) = . then all_scores(i) = 0;
    end;
    drop i;
run;

/* DO WHILE — generate rows until condition met */
data payment_schedule;
    balance     = 100000;
    month       = 0;
    rate        = 0.005;
    payment     = 1000;

    do while (balance > 0);
        month    + 1;
        interest = balance * rate;
        balance  = balance + interest - payment;
        if balance < 0 then balance = 0;
        output;
    end;

    keep month balance interest;
run;

/* DO UNTIL — runs at least once */
data compound_interest;
    amount = 1000;
    years  = 0;

    do until (amount >= 2000);
        years  + 1;
        amount = amount * 1.07;
        output;
    end;
    keep years amount;
run;
