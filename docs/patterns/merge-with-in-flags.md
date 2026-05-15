# Pattern file: MERGE with IN= dataset flags
## Source: Real SAS practice code — BFS/mortgage domain
## Complexity: HIGH — IN= flags control join behaviour precisely

---

## Pattern 1: Basic MERGE (inner join equivalent)

**SAS input**:
```sas
proc sort data=merge1 out=sortedM1; by rollno; run;
proc sort data=merge2 out=sortedM2; by rollno; run;

data Merged12;
merge sortedM1 sortedM2;
by rollno;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: MERGE without IN= → outer join (keeps all rows from both)
# SAS: BY rollno → merge key
merged12 = pd.merge(
    merge1,
    merge2,
    on="rollno",
    how="outer"
)
# SAS: MERGE without IN= flags = full outer join
```

**Notes**: SAS MERGE without IN= flags is a full outer join — it keeps all
rows from both datasets. This is different from SQL INNER JOIN.

---

## Pattern 2: MERGE with IN= — left join (keep only left rows)

**SAS input**:
```sas
data mar;
merge jan(in=x) feb(in=y);
by id;
if x=1 and y=0;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: IN=x flag → tracks which dataset contributed each row
# SAS: if x=1 and y=0 → rows ONLY in jan, not in feb (left anti-join)
mar = jan.merge(feb, on="id", how="left", indicator=True)
mar = mar[mar["_merge"] == "left_only"].drop(columns=["_merge"])
# SAS: x=1 AND y=0 → left_only in pandas merge indicator
```

---

## Pattern 3: MERGE with IN= — inner join (keep matching rows only)

**SAS input**:
```sas
data want;
merge x(in=a) y(in=b);
by managerid;
if a;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: if a → keep rows where left dataset contributed (left join, not anti)
# SAS: if a AND b → inner join
# SAS: if a (alone, after merge) → left join keeping all left rows
want = x.merge(y, on="managerid", how="left")
# SAS: if a; alone after MERGE = left join (all x rows, matched y cols)
```

**IN= flag truth table**:

| SAS condition | pandas equivalent |
|---|---|
| `if a and b` | `how="inner"` |
| `if a` | `how="left"` |
| `if b` | `how="right"` |
| `if a and not b` (i.e. `y=0`) | `how="left", indicator=True`, filter `left_only` |
| `if b and not a` | `how="right", indicator=True`, filter `right_only` |
| No condition | `how="outer"` |

---

## Pattern 4: MERGE with rename= option

**SAS input**:
```sas
data MJ.Merged12;
merge MJ.sortedM1 MJ.sortedM2 (rename=(age=price)(name=city));
by rollno;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: rename= on one dataset before merge
# → rename columns in the right DataFrame before merging
sortedm2_renamed = mj_sortedm2.rename(columns={"age": "price", "name": "city"})

# SAS: MERGE ... BY rollno → merge on rollno
mj_merged12 = mj_sortedm1.merge(
    sortedm2_renamed,
    on="rollno",
    how="outer"
)
# SAS: rename= applied to sortedM2 only, before the merge
```

---

## Pattern 5: SET (vertical stack) vs MERGE (horizontal join)

**SAS input**:
```sas
/* Vertical stack — SET */
data b;
set merge1 merge2;
run;

/* Horizontal join — MERGE */
data a;
merge merge1 merge2;
by rollno;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: SET multiple datasets = vertical stack (append rows)
b = pd.concat([merge1, merge2], ignore_index=True)
# SAS: set merge1 merge2 → pd.concat

# SAS: MERGE ... BY = horizontal join (match columns by key)
a = pd.merge(merge1, merge2, on="rollno", how="outer")
# SAS: merge merge1 merge2 BY rollno → pd.merge
```

**Notes**: `SET` = `pd.concat` (stack rows). `MERGE` = `pd.merge` (join columns).
This is the most common source of confusion when migrating SAS to pandas.

---

## Pattern 6: One-to-many MERGE

**SAS input**:
```sas
data merge2;
input rollno name$ age;
datalines;
1 Ram 2
2 Shyam 34
2 kaka 53
3 same31 53
3 same32 54
;
run;

data a;
merge merge1 merge2;
by rollno;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: One-to-many MERGE → pandas handles automatically with merge
# SAS: merge1 has 1 row per rollno, merge2 has many → result has many rows
a = pd.merge(merge1, merge2, on="rollno", how="outer")
# SAS: One-to-many MERGE expands left dataset rows to match right dataset
# pandas merge does this automatically — no special handling needed
```

---

## Pattern 7: MERGE with conflict column resolution

**SAS input**:
```sas
data mergel;
merge b a(rename=(id=student_id));
by student_id;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: rename=(id=student_id) aligns key column names before merge
a_renamed = a.rename(columns={"id": "student_id"})

# SAS: merge b a(rename=...) BY student_id → right dataset listed second
mergel = pd.merge(b, a_renamed, on="student_id", how="outer")
# SAS: dataset order in MERGE matters when both have same-name non-key cols
# → right dataset values overwrite left for same-named columns
```

**Notes**: In SAS MERGE, when both datasets have a column with the same name
(other than the BY key), the rightmost dataset's value wins. In pandas,
use `suffixes=("_left", "_right")` and then resolve manually.

---

## Complete IN= flag → how= mapping

```python
# Reference: translate SAS MERGE IN= condition to pandas how=

def sas_merge_to_pandas(left_df, right_df, by_cols, in_condition):
    """
    in_condition examples:
      "if a"          → how="left"
      "if b"          → how="right"
      "if a and b"    → how="inner"
      "if a and not b"→ how="left" + filter left_only
      no condition    → how="outer"
    """
    conditions = {
        "left_only":   ("left",  "left_only"),
        "right_only":  ("right", "right_only"),
        "inner":       ("inner", None),
        "left":        ("left",  None),
        "right":       ("right", None),
        "outer":       ("outer", None),
    }
    # Always merge with indicator first for anti-join cases
    merged = pd.merge(left_df, right_df, on=by_cols, how="outer", indicator=True)
    return merged
```
