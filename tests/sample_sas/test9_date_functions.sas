/* ============================================================
   TEST 9: Date functions
   Tests: INTNX, INTCK, PUT with date formats, TODAY(),
          MONTH/YEAR/DAY functions, date filtering
   Expected output target: pandas
   ============================================================ */

data loan_dates;
    set mortgages_clean;

    /* Age of loan in months */
    loan_age_months = intck('month', origination_date, today());
    loan_age_years  = intck('year',  origination_date, today());

    /* Next review date — 12 months from origination */
    next_review     = intnx('month', origination_date, 12, 'sameday');
    format next_review date9.;

    /* Start of origination month */
    month_start     = intnx('month', origination_date, 0, 'b');
    format month_start date9.;

    /* End of origination month */
    month_end       = intnx('month', origination_date, 0, 'e');
    format month_end date9.;

    /* Date components */
    orig_month      = month(origination_date);
    orig_year       = year(origination_date);
    orig_day        = day(origination_date);

    /* Format date as character */
    date_char       = put(origination_date, mmddyy10.);
    month_name      = put(origination_date, monname3.);

    /* Filter: originated in last 24 months */
    cutoff_date     = intnx('month', today(), -24, 'b');
    format cutoff_date date9.;

    if origination_date >= cutoff_date;

    drop cutoff_date;
run;

/* Loans maturing within 30 days */
proc sql;
    select account_id,
           maturity_date format=date9.,
           intck('day', today(), maturity_date) as days_to_maturity
    from mortgages_clean
    where intck('day', today(), maturity_date) between 0 and 30
    order by maturity_date;
quit;
