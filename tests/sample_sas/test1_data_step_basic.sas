/* ============================================================
   TEST 1: Basic DATA step
   Tests: SET, WHERE, derived columns, IF/THEN/ELSE, DROP
   Expected output target: pandas
   ============================================================ */

data mortgages_clean;
    set mortgages_raw;
    where loan_status = 'ACTIVE';

    /* Derived columns */
    loan_to_value = loan_amount / property_value * 100;

    if loan_to_value > 90 then high_ltv = 1;
    else high_ltv = 0;

    if loan_type = 'FTB' then first_time_buyer = 1;
    else first_time_buyer = 0;

    monthly_payment = (loan_amount * interest_rate / 100) / 12;

    drop internal_ref created_dt last_modified;
run;
