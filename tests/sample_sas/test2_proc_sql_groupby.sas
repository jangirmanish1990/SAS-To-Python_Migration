/* ============================================================
   TEST 2: PROC SQL with GROUP BY, aggregates, CASE WHEN
   Tests: CREATE TABLE, GROUP BY, COUNT/SUM/AVG, CASE WHEN,
          ORDER BY, WHERE
   Expected output target: sql
   ============================================================ */

proc sql;
    create table branch_summary as
    select
        branch_id,
        loan_type,
        count(*)                          as total_loans,
        sum(loan_amount)                  as total_exposure,
        avg(loan_to_value)                as avg_ltv,
        min(interest_rate)                as min_rate,
        max(interest_rate)                as max_rate,
        case
            when avg(loan_to_value) > 85 then 'HIGH RISK'
            when avg(loan_to_value) > 75 then 'MEDIUM RISK'
            else 'LOW RISK'
        end                               as risk_band
    from mortgages_clean
    where loan_status = 'ACTIVE'
      and branch_id is not missing
    group by branch_id, loan_type
    order by total_exposure desc;
quit;
