/* ============================================================
   TEST 10: Full mortgage pipeline — multi-block
   Tests: All constructs together in one realistic file
   This is the hardest test — closest to real BFS/FTB work
   Expected output target: pandas
   ============================================================ */

%let report_month = MAR2024;
%let ltv_threshold = 85;
%let min_balance   = 10000;

/* ── STEP 1: Clean raw mortgage data ── */
data mortgages_work;
    set mortgages_raw;
    where loan_status in ('ACTIVE', 'ARREARS')
      and outstanding_balance >= &min_balance;

    /* Derived risk metrics */
    loan_to_value   = outstanding_balance / current_value * 100;
    monthly_payment = (outstanding_balance * (interest_rate/100)) / 12;

    if loan_to_value > &ltv_threshold then high_ltv = 1;
    else high_ltv = 0;

    if arrears_balance > 0 then in_arrears = 1;
    else in_arrears = 0;

    /* Loan age */
    loan_age_months = intck('month', origination_date, today());

    drop internal_ref etl_load_dt;
run;

/* ── STEP 2: Sort and deduplicate ── */
proc sort data=mortgages_work out=mortgages_sorted nodupkey;
    by account_id;
run;

/* ── STEP 3: Branch-level summary ── */
proc sql;
    create table branch_summary as
    select
        branch_id,
        count(*)                           as total_accounts,
        sum(outstanding_balance)           as total_book,
        avg(loan_to_value)                 as avg_ltv,
        sum(high_ltv)                      as high_ltv_count,
        sum(in_arrears)                    as arrears_count,
        sum(arrears_balance)               as total_arrears,
        case
            when avg(loan_to_value) > 85   then 'HIGH'
            when avg(loan_to_value) > 75   then 'MEDIUM'
            else                                'LOW'
        end                                as risk_band
    from mortgages_sorted
    group by branch_id
    order by total_book desc;
quit;

/* ── STEP 4: Portfolio stats ── */
proc means data=mortgages_sorted n mean std min max;
    var outstanding_balance loan_to_value interest_rate loan_age_months;
    class loan_type high_ltv;
    output out=portfolio_stats mean= std= / autoname;
run;

/* ── STEP 5: Flag new vs existing from previous month ── */
proc sort data=mortgages_sorted  out=curr_sorted; by account_id; run;
proc sort data=prev_month_loans  out=prev_sorted; by account_id; run;

data loan_changes;
    merge curr_sorted (in=curr)
          prev_sorted (in=prev rename=(outstanding_balance=prev_balance
                                       loan_to_value=prev_ltv));
    by account_id;

    if curr and not prev then change_flag = 'NEW';
    else if curr and prev then do;
        change_flag     = 'EXISTING';
        balance_change  = outstanding_balance - prev_balance;
        ltv_change      = loan_to_value - prev_ltv;
    end;

    if curr;
run;

/* ── STEP 6: Top 5 highest risk accounts per branch ── */
proc sort data=loan_changes out=sorted_by_ltv;
    by branch_id descending loan_to_value;
run;

data top5_risk_per_branch;
    set sorted_by_ltv;
    by branch_id;

    if first.branch_id = 1 then rank = 1;
    else rank + 1;

    if rank le 5;
    drop rank;
run;
