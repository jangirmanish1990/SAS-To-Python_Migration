data mortgages_clean;
    set mortgages_raw;
    where loan_status = 'ACTIVE';
    loan_to_value = loan_amount / property_value * 100;
    drop internal_ref;
run;

proc sql;
    create table summary as
    select branch_id, count(*) as total_loans
    from mortgages_clean
    group by branch_id;
quit;

proc means data=mortgages_clean n mean;
    var loan_amount;
run;
