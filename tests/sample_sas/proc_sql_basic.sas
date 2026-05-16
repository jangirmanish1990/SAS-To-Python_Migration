proc sql;
    create table summary as
    select branch_id,
           count(*) as total_loans,
           sum(loan_amount) as total_exposure,
           avg(loan_to_value) as avg_ltv
    from mortgages_clean
    where loan_status = 'ACTIVE'
    group by branch_id
    order by total_exposure desc;
quit;
