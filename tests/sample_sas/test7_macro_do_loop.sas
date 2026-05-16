/* ============================================================
   TEST 7: %MACRO with %DO loop and %LET
   Tests: %LET, %MACRO, keyword parameters, %DO loop,
          auto-resolution of &variables
   Expected output target: pandas
   Note: /convert should auto-resolve all &variables
   ============================================================ */

%let indata    = mortgages_raw;
%let outdata   = mortgages_clean;
%let threshold = 85;
%let min_loan  = 50000;

/* Macro to filter and flag high-LTV loans */
%macro flag_high_ltv(indata=, outdata=, threshold=90, min_loan=0);

    data &outdata;
        set &indata;
        where loan_amount >= &min_loan;

        loan_to_value = loan_amount / property_value * 100;

        if loan_to_value > &threshold then do;
            high_ltv    = 1;
            risk_label  = 'HIGH';
        end;
        else do;
            high_ltv    = 0;
            risk_label  = 'NORMAL';
        end;
    run;

%mend flag_high_ltv;

%flag_high_ltv(
    indata    = &indata,
    outdata   = &outdata,
    threshold = &threshold,
    min_loan  = &min_loan
);

/* Macro to create one dataset per loan type */
%let loan_types = FTB REMORTGAGE BUYTOLET;
%let n          = 3;

%macro split_by_type(indata=, n=, types=);
    %do i = 1 %to &n;
        %let ltype = %scan(&types, &i, ' ');

        data loans_&ltype;
            set &indata;
            where loan_type = "&ltype";
        run;

    %end;
%mend split_by_type;

%split_by_type(
    indata = &outdata,
    n      = &n,
    types  = &loan_types
);
