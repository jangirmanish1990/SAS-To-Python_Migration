/* ============================================================
   TEST 6: PROC SQL subqueries
   Tests: NOT IN subquery, correlated subquery, scalar
          subquery, second highest, monotonic()
   Expected output target: sql
   ============================================================ */

/* Anti-join using NOT IN subquery */
proc sql;
    create table new_customers as
    select *
    from feb_customers
    where customer_id not in (select customer_id from jan_customers);
quit;

/* Second highest loan amount */
proc sql;
    select max(loan_amount) as second_highest
    from mortgages_clean
    where loan_amount < (select max(loan_amount) from mortgages_clean);
quit;

/* Top 10 loans per branch using correlated subquery */
proc sql;
    select a.branch_id, a.account_id, a.loan_amount,
        (
            select count(loan_amount)
            from mortgages_clean as b
            where b.branch_id  = a.branch_id
              and b.loan_amount >= a.loan_amount
        ) as rank
    from mortgages_clean as a
    where calculated rank <= 10
    order by branch_id, rank;
quit;

/* Row number using monotonic() */
proc sql;
    create table top5_loans as
    select *, monotonic() as row_num
    from mortgages_clean
    order by loan_amount desc;

    select *
    from top5_loans
    where row_num <= 5;
quit;

/* Min date per customer */
proc sql;
    select customer_id,
           min(transaction_date) format=date9. as first_txn_date
    from transactions
    group by customer_id;
quit;
