# Pattern file: %MACRO and %DO loops
## Source: Real SAS practice code — BFS/mortgage domain
## Complexity: HIGH — macros have no direct Python equivalent; must restructure

---

## Pattern 1: Basic %MACRO with keyword parameters

**SAS input**:
```sas
%macro Man(a=);
data &a;
    set sasuser.admit;
run;
%mend Man;

%Man(a=Mydata23);
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: %MACRO with keyword param → Python function
def man(a: str, source_df: pd.DataFrame) -> pd.DataFrame:
    # SAS: data &a; set sasuser.admit; run;
    result = source_df.copy()
    return result

# SAS: %Man(a=Mydata23)
mydata23 = man(a="Mydata23", source_df=sasuser_admit)
```

**Notes**: SAS macro keyword parameters (`param=`) map to Python keyword arguments.
The dataset name `&a` becomes the variable name in Python — assign the return value.

---

## Pattern 2: %DO loop creating multiple datasets

**SAS input**:
```sas
%macro plate(n=, name=);
%do i=1 %to &n;
    data &name&i;
        set sasuser.admit;
    run;
%end;
%mend plate;

%plate(n=5, name=plate);
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: %DO loop creating N datasets → dict of DataFrames
def plate(n: int, name: str, source_df: pd.DataFrame) -> dict:
    # SAS: %do i=1 %to &n → Python range loop
    datasets = {}
    for i in range(1, n + 1):
        # SAS: data &name&i → dict key f"{name}{i}"
        datasets[f"{name}{i}"] = source_df.copy()
    return datasets

# SAS: %plate(n=5, name=plate)
plate_datasets = plate(n=5, name="plate", source_df=sasuser_admit)
# Access: plate_datasets["plate1"], plate_datasets["plate2"], ...
```

---

## Pattern 3: %DO loop with PROC SQL into: (macro array)

**SAS input**:
```sas
proc sql noprint;
    select distinct memname into: MemNames separated by "@"
    from dictionary.columns
    where upcase(libname)="MJ";
    select count(distinct memname) into: n
    from dictionary.columns
    where upcase(libname)="MJ";
quit;

%do i=1 %to &n;
    %let mName=%scan(&MemNames, &i, "@");
    proc export data=MJ.&mName
        outfile="C:\...\&mName..xlsx"
        DBMS=xlsx replace;
        sheet="&mName";
    run;
%end;
```

**Python (pandas) output**:
```python
import pandas as pd
from pathlib import Path

# SAS: SELECT DISTINCT into: separated by "@" → Python list
# SAS: Dictionary.columns → use actual list of table names
mem_names = ["table1", "table2", "table3"]  # TODO: replace with actual table names

# SAS: %do i=1 %to &n → enumerate the list
output_dir = Path("C:/output")
for mem_name in mem_names:
    # SAS: proc export → df.to_excel()
    df = datasets[mem_name]  # assumes dict of DataFrames
    output_path = output_dir / f"{mem_name}.xlsx"
    df.to_excel(output_path, sheet_name=mem_name, index=False)
    # SAS: sheet="&mName" → sheet_name=mem_name
```

---

## Pattern 4: %MACRO splitting dataset into N parts

**SAS input**:
```sas
%macro SJ(nameD=, nParts=);
    proc sql noprint;
        select count(*) into: n from &nameD;
    quit;

    %let datarows=(&n/&nParts);
    %let datarowsfinal=%sysfunc(round(&datarows));

    %do i=1 %to &nParts.;
        data MyMCR&i.;
            set &nameD.;
            retain cnt 0;
            cnt=cnt+1;
            if cnt gt &predatarowsfinal. and cnt le &datarowsfinal.;
            drop cnt;
        run;
    %end;
%mend SJ;

%SJ(nameD=sashelp.class, nParts=4);
```

**Python (pandas) output**:
```python
import pandas as pd
import math

# SAS: %MACRO splitting dataset into N equal parts
def sj(df: pd.DataFrame, n_parts: int) -> dict:
    # SAS: SELECT count(*) into: n → len(df)
    n = len(df)
    # SAS: %sysfunc(round(&datarows)) → math.ceil for equal chunks
    chunk_size = math.ceil(n / n_parts)

    parts = {}
    for i in range(1, n_parts + 1):
        # SAS: data MyMCR&i → dict key f"MyMCR{i}"
        start = (i - 1) * chunk_size
        end = min(i * chunk_size, n)
        # SAS: retain cnt + if cnt gt prev and cnt le current → iloc slice
        parts[f"MyMCR{i}"] = df.iloc[start:end].reset_index(drop=True)

    return parts

# SAS: %SJ(nameD=sashelp.class, nParts=4)
my_mcr = sj(df=sashelp_class, n_parts=4)
# Access: my_mcr["MyMCR1"], my_mcr["MyMCR2"], etc.
```

---

## Pattern 5: %LET with %EVAL and %SYSEVALF

**SAS input**:
```sas
%let a=10;
%let b=3;

%macro mydmc;
    %let c=%eval(&a./&b.);    /* integer division */
    %put &c.;

    %let d=%sysevalf(&a./&b.);  /* float division */
    %put &d.;
%mend mydmc;

%mydmc;
```

**Python (pandas) output**:
```python
# SAS: %LET → Python variable assignment
a = 10
b = 3

# SAS: %EVAL → integer division (truncates)
c = a // b
print(c)
# SAS: %SYSEVALF → float division
d = a / b
print(d)
```

**Notes**: `%EVAL` in SAS does integer arithmetic (like `//` in Python).
`%SYSEVALF` does floating-point (like `/`). Always check which was used.

---

## Pattern 6: call symput / symget (macro variable from data step)

**SAS input**:
```sas
data _null_;
    set sashelp.class;
    if _N_ = 1 then call symput('nvar', name);
run;
%put &nvar;

data want;
    var1 = symget('nvar');
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: call symput('nvar', name) — store first value to macro var
# → Python: just assign to a variable
nvar = sashelp_class["name"].iloc[0]
print(nvar)

# SAS: symget('nvar') in data step → use the Python variable directly
want = pd.DataFrame({"var1": [nvar]})
```

**Notes**: `call symput` / `symget` are SAS's way of passing values between
data steps and macro scope. In Python, variables are already in scope — no
special mechanism needed.

---

## Pattern 7: %MACRO with conditional %IF/%ELSE

**SAS input**:
```sas
%macro ExpImp(pval=);
    %if &pval="imp" %then %do;
        proc import datafile="..." out=aImpCSV1 dbms=csv replace;
        run;
    %end;
    %else %do;
        proc export data=sasuser.admit outfile="..." DBMS=xls replace;
        run;
    %end;
%mend ExpImp;

%ExpImp(pval=imp);
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: %IF/%ELSE in macro → Python if/else in function
def exp_imp(pval: str, df: pd.DataFrame = None) -> pd.DataFrame | None:
    if pval == "imp":
        # SAS: proc import → pd.read_csv / pd.read_excel
        result = pd.read_csv("path/to/file.csv")
        return result
    else:
        # SAS: proc export → df.to_excel
        df.to_excel("path/to/output.xls", index=False)
        return None

# SAS: %ExpImp(pval=imp)
imported_df = exp_imp(pval="imp")
```

---

## Macro variable resolution reference

| SAS macro syntax | Python equivalent |
|---|---|
| `%let x = 10;` | `x = 10` |
| `&x` (reference) | `x` or `f"{x}"` in strings |
| `%eval(&a + &b)` | `a + b` (integer) |
| `%sysevalf(&a / &b)` | `a / b` (float) |
| `%scan(&str, 1, "@")` | `str.split("@")[0]` |
| `%do i=1 %to &n` | `for i in range(1, n+1):` |
| `call symput('var', val)` | `var = val` |
| `symget('var')` | `var` (already in scope) |
| `%sysfunc(ceil(&x))` | `math.ceil(x)` |
| `%sysfunc(round(&x))` | `round(x)` |
| `cats(&a, &b)` | `f"{a}{b}"` |
| `catx(" ", &a, &b)` | `f"{a} {b}"` |
