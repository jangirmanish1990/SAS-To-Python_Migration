/* ============================================================
   TEST 4: MERGE with IN= flags
   Tests: MERGE, BY, IN= flags (inner, left, anti-join),
          RENAME= option, SET vs MERGE
   Expected output target: pandas
   ============================================================ */

/* Sort both datasets before merging */
proc sort data=loan_accounts out=loan_sorted;
    by account_id;
run;

proc sort data=customer_details out=cust_sorted;
    by account_id;
run;

/* Inner join — keep only matched records */
data matched_accounts;
    merge loan_sorted  (in=a)
          cust_sorted  (in=b rename=(name=customer_name age=customer_age));
    by account_id;
    if a and b;
run;

/* Left anti-join — loans with no matching customer record */
data unmatched_loans;
    merge loan_sorted (in=a)
          cust_sorted (in=b);
    by account_id;
    if a and not b;
run;

/* Vertical stack — combine January and February loan data */
data all_loans;
    set jan_loans feb_loans mar_loans;
run;
