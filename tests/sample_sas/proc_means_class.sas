proc means data=mortgages_clean n mean std min max;
    var loan_amount loan_to_value;
    class loan_type;
    output out=means_out mean= std= / autoname;
run;
