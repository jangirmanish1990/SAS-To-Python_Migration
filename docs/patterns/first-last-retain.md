# Pattern file: FIRST./LAST. with RETAIN
## Source: Real SAS practice code — BFS/mortgage domain
## Complexity: HIGH — most common source of migration errors

---

## Pattern 1: Count observations per group (FIRST./LAST. + counter)

**SAS input**:
```sas
Data CC_Analysis3;
set Creditcard;
by cc;
if first.cc=1 then swipe_count=1;
else swipe_count+1;
if last.cc=1;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: BY cc — requires pre-sorted data
# SAS: FIRST./LAST. + counter → groupby cumcount
cc_analysis3 = (
    creditcard
    .assign(swipe_count=creditcard.groupby("cc").cumcount() + 1)
    .groupby("cc")
    .last()
    .reset_index()
)
# SAS: IF last.cc=1 → keep only last row per group
```

**Notes**: `cumcount() + 1` replicates the SAS counter that resets to 1 on `first.cc`.
`.groupby().last()` replicates `if last.cc=1` — keeps only the final row per group.

---

## Pattern 2: Running sum per group, keep last row

**SAS input**:
```sas
Data CC_Analysis6;
set Creditcard;
by cc;
if first.cc=1 then count=swipe;
else count+swipe;
if last.cc=1;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Running sum per group → groupby sum, keep last
cc_analysis6 = (
    creditcard
    .groupby("cc", as_index=False)
    .agg(count=("swipe", "sum"))
)
# SAS: IF last.cc=1 → groupby().sum() already collapses to one row per group
```

**Notes**: SAS `count+swipe` is a running total retained across rows — the final value
at `last.cc` equals the group sum. `groupby().sum()` is the direct equivalent.

---

## Pattern 3: Running sum with conditional threshold filter

**SAS input**:
```sas
Data CC_Analysis2;
set Creditcard;
by cc;
if first.cc=1 then swipe_500=Swipe;
else swipe_500+Swipe;
if swipe_500 gt 500 and last.cc=1;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Running sum per group with threshold filter at last row
cc_analysis2 = (
    creditcard
    .groupby("cc", as_index=False)
    .agg(swipe_500=("Swipe", "sum"))
    .query("swipe_500 > 500")
)
# SAS: swipe_500 gt 500 AND last.cc=1 → filter after aggregation
```

---

## Pattern 4: Nested BY groups (two-level FIRST./LAST.)

**SAS input**:
```sas
Data CC_Analysis4;
set sorted_type_cc;
by CCTypes cc;
if first.cc=1 and first.CCTypes=1 then swipe_count=1;
else swipe_count+1;
if last.cc=1 and last.CCTypes=1;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Nested BY — CCTypes then cc
# SAS: FIRST./LAST. on both levels → groupby both columns
cc_analysis4 = (
    sorted_type_cc
    .assign(swipe_count=sorted_type_cc.groupby(["CCTypes", "cc"]).cumcount() + 1)
    .groupby(["CCTypes", "cc"])
    .last()
    .reset_index()
)
# SAS: if last.cc and last.CCTypes → last row of each CCTypes+cc group
```

**Notes**: SAS nested BY groups map to multi-column `groupby()`. The order of columns
in `groupby()` must match the SAS BY statement order exactly.

---

## Pattern 5: Keep top N rows per group using FIRST./LAST.

**SAS input**:
```sas
proc sort data=Student_exam_info out=sorted_Stud;
by name descending marks;
run;

data high3_Marks;
set sorted_Stud;
by name;
if first.name=1 then cnt=1;
else cnt+1;
if cnt=3 OR (last.name=1 AND cnt=2);
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: PROC SORT descending → sort_values
sorted_stud = student_exam_info.sort_values(
    ["name", "marks"], ascending=[True, False]
)
# SAS: Keep top 3 marks per student, or all if fewer than 3 exist
high3_marks = (
    sorted_stud
    .groupby("name")
    .head(3)
    .reset_index(drop=True)
)
# SAS: cnt=3 OR (last.name AND cnt=2) → head(3) handles both cases
```

---

## Pattern 6: Row number within group using RETAIN counter

**SAS input**:
```sas
data a;
input id sal;
run;

data want;
set a;
retain cnt;
by id;
cnt=ifn(first.id,1,cnt+1);
if cnt=2;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: RETAIN cnt resets on first.id → cumcount within group
# SAS: if cnt=2 → keep 2nd row of each group
want = (
    a.assign(cnt=a.groupby("id").cumcount() + 1)
    .query("cnt == 2")
    .drop(columns=["cnt"])
    .reset_index(drop=True)
)
# SAS: ifn(first.id,1,cnt+1) → cumcount()+1 resets per group automatically
```

---

## Pattern 7: Keep first row per group only

**SAS input**:
```sas
data first_by_group;
set first_by_group_Sorted;
by id date_mm datee;
if first.date_mm;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: if first.date_mm → keep first row per id+date_mm group
first_by_group = (
    first_by_group_sorted
    .groupby(["id", "date_mm"], as_index=False)
    .first()
)
# SAS: BY id date_mm datee — groupby on the FIRST. variable and its parents
```

**Notes**: In SAS, `if first.X` keeps the first row where X changes. The groupby
key must include all BY variables that appear before X in the BY statement.

---

## Common mistakes to avoid

| SAS pattern | Wrong pandas | Correct pandas |
|---|---|---|
| `count+1` (RETAIN) | `df["count"] = 1` | `df.groupby("key").cumcount() + 1` |
| `if last.key` | `df.tail(1)` | `df.groupby("key").last()` |
| `if first.key` | `df.head(1)` | `df.groupby("key").first()` |
| Nested BY groups | Single groupby | `groupby(["outer", "inner"])` |
| Running sum at last row | Loop | `groupby().sum()` |

---

## PySpark equivalents

```python
from pyspark.sql import functions as F
from pyspark.sql.window import Window

w = Window.partitionBy("cc").orderBy("cc")

# FIRST./LAST. row number
df = df.withColumn("cnt", F.row_number().over(w))

# Running sum (equivalent to RETAIN sum+col)
df = df.withColumn("running_sum", F.sum("swipe").over(w))

# Keep last row per group
df = df.withColumn("rn", F.row_number().over(w.rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)))
df_last = df.filter(F.col("rn") == F.count("*").over(Window.partitionBy("cc")))
```
