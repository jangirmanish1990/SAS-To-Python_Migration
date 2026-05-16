/* ============================================================
   TEST 5: PROC MEANS with CLASS + PROC FREQ
   Tests: PROC MEANS, CLASS, VAR, OUTPUT OUT=,
          PROC FREQ, TABLES, cross-tabulation
   Expected output target: pandas
   ============================================================ */

/* Summary stats by loan type */
proc means data=mortgages_clean n mean std min max median;
    var loan_amount loan_to_value interest_rate monthly_payment;
    class loan_type branch_id;
    output out=loan_stats
           mean=mean_amount mean_ltv mean_rate mean_payment
           std=std_amount std_ltv std_rate std_payment
           / autoname;
run;

/* Frequency of loan types */
proc freq data=mortgages_clean;
    tables loan_type;
run;

/* Cross-tabulation: loan type by risk band */
proc freq data=mortgages_clean;
    tables loan_type * risk_band;
run;

/* Overall stats — no class variable */
proc means data=mortgages_clean n mean std min max;
    var loan_amount loan_to_value;
run;
