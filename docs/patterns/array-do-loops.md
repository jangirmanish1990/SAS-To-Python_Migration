# Pattern file: ARRAY and DO loops
## Source: Real SAS practice code — BFS/mortgage domain
## Complexity: HIGH — SAS arrays are not Python arrays

---

## Pattern 1: Static ARRAY to fill missing values

**SAS input**:
```sas
data b;
set a;
array Mysub(4) sub1 sub2 sub3 sub4;
do i=1 to 4;
    Mysub(i) = Coalesce(Mysub(i), 10000);
end;
drop i;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: ARRAY Mysub(4) sub1 sub2 sub3 sub4 → list of column names
mysub_cols = ["sub1", "sub2", "sub3", "sub4"]

# SAS: do i=1 to 4; Mysub(i) = Coalesce(Mysub(i), 10000) → fillna
b = a.copy()
b[mysub_cols] = b[mysub_cols].fillna(10000)
# SAS: COALESCE(col, 10000) → fillna(10000) for numeric columns
```

---

## Pattern 2: Dynamic ARRAY on all numeric columns

**SAS input**:
```sas
data c;
set a;
array Mysub(*) _numeric_;
do i=1 to dim(Mysub);
    Mysub(i) = Coalesce(Mysub(i), 10000);
end;
drop i;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: _numeric_ → select all numeric columns dynamically
numeric_cols = a.select_dtypes(include="number").columns.tolist()

# SAS: dim(Mysub) → len(numeric_cols)
# SAS: do i=1 to dim → apply across all numeric cols
c = a.copy()
c[numeric_cols] = c[numeric_cols].fillna(10000)
# SAS: ARRAY(*) _numeric_ → pandas select_dtypes("number")
```

---

## Pattern 3: ARRAY for macro-driven missing value fill

**SAS input**:
```sas
%macro missedval(noV=);
data b;
set a;
%do i=1 %to &noV;
    v&i = coalesce(v&i, 0);
%end;
run;
%mend missedval;

%missedval(noV=20);
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: %DO loop generating column names v1..v20
# SAS: COALESCE(vi, 0) → fillna(0)
def missedval(df: pd.DataFrame, no_v: int) -> pd.DataFrame:
    # SAS: %do i=1 %to &noV → list comprehension of column names
    v_cols = [f"v{i}" for i in range(1, no_v + 1)]
    # SAS: coalesce(vi, 0) → fillna(0)
    result = df.copy()
    existing_cols = [c for c in v_cols if c in result.columns]
    result[existing_cols] = result[existing_cols].fillna(0)
    return result

# SAS: %missedval(noV=20)
b = missedval(df=a, no_v=20)
```

---

## Pattern 4: DO WHILE loop

**SAS input**:
```sas
data a;
x = 5;
do while (x < 10);
    output;
    x + 1;
end;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: DO WHILE loop generating rows → build list, then DataFrame
rows = []
x = 5
# SAS: do while (x < 10)
while x < 10:
    rows.append({"x": x})
    x += 1  # SAS: x + 1 (retain increment)

a = pd.DataFrame(rows)
# SAS: OUTPUT inside loop → each iteration becomes a row
```

---

## Pattern 5: DO UNTIL loop

**SAS input**:
```sas
data a;
x = 5;
do until (x > 10);
    output;
    x + 1;
end;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: DO UNTIL — condition checked at END of loop (runs at least once)
rows = []
x = 5
# SAS: do until (x > 10) → while not condition
while True:
    rows.append({"x": x})
    x += 1
    if x > 10:  # SAS: until condition checked at end
        break

a = pd.DataFrame(rows)
```

**Notes**: `DO WHILE` checks condition at the START (may not run).
`DO UNTIL` checks at the END (always runs at least once).
Python `while True` + `break` replicates `DO UNTIL` exactly.

---

## Pattern 6: DO loop with POINT= (random access)

**SAS input**:
```sas
data a;
do sl = 2, 1, 7, 4;
    set sashelp.admit point=sl;
    output;
end;
stop;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: POINT= random access → iloc with specific indices
# SAS: do sl = 2, 1, 7, 4 → specific row positions (1-based in SAS)
row_indices = [2, 1, 7, 4]
# SAS is 1-based, pandas is 0-based
a = sashelp_admit.iloc[[i - 1 for i in row_indices]].reset_index(drop=True)
# SAS: STOP prevents infinite loop after POINT= access
```

---

## Pattern 7: DO loop for string manipulation

**SAS input**:
```sas
data test2;
str1 = "ABC DEF";
n = int(length(str1));
array marr(6) $;
do i = 1 to length(str1);
    substr(str1, i, 1) = "MJ";
end;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: DO loop over string characters → Python string operations
str1 = "ABC DEF"

# SAS: substr(str1, i, 1) = "MJ" → replace each char with "MJ"
# Note: SAS replaces in-place, limited by original string length
result = ""
for i in range(len(str1)):
    # SAS: substr assigns only up to original string length
    result += "MJ"[0]  # takes first char of "MJ" since original was 1 char wide

# SAS: ARRAY marr(6) $ → Python list for character arrays
marr = [None] * 6
for i, char in enumerate(str1[:6]):
    marr[i] = char
```

---

## Pattern 8: Iterative sum using DO loop

**SAS input**:
```sas
data a;
do i = 1 to 5;
    p + 1;
end;
drop i;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: p+1 inside DO loop → running total
# SAS: RETAIN p (implicit) → p persists across iterations
p = 0
for i in range(1, 6):
    p += 1  # SAS: p+1 increments retained variable

# SAS: Single-row output after loop → one-row DataFrame
a = pd.DataFrame({"p": [p]})
```

---

## ARRAY / DO loop conversion reference

| SAS construct | pandas equivalent |
|---|---|
| `array cols(4) c1 c2 c3 c4` | `cols = ["c1","c2","c3","c4"]` |
| `array cols(*) _numeric_` | `cols = df.select_dtypes("number").columns` |
| `dim(myarray)` | `len(cols)` |
| `do i=1 to dim(arr)` | `for i, col in enumerate(cols):` |
| `Coalesce(arr(i), 0)` | `df[cols].fillna(0)` |
| `do while (x < 10)` | `while x < 10:` |
| `do until (x > 10)` | `while True: ... if x > 10: break` |
| `do i=1 to 5; output; end` | `pd.DataFrame({"i": range(1,6)})` |
| `set ds point=n` | `df.iloc[n-1]` (0-based) |
| `stop;` after POINT= | no equivalent needed in Python |
