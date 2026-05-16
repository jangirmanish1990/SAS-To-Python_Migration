data mortgages_clean;
    set mortgages_raw;
    where loan_status = 'ACTIVE';
    loan_to_value = loan_amount / property_value * 100;
    if loan_to_value > 90 then high_ltv = 1;
    else high_ltv = 0;
    drop internal_ref created_dt;
run;
