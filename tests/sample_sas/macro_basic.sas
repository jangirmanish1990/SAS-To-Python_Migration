%macro calc_ltv(indata=, outdata=, threshold=90);
    data &outdata;
        set &indata;
        loan_to_value = loan_amount / property_value * 100;
        high_ltv = (loan_to_value > &threshold);
    run;
%mend calc_ltv;
