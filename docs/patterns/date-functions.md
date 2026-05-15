# Pattern file: SAS date functions
## Source: Real SAS practice code — BFS/mortgage domain
## Complexity: MEDIUM-HIGH — SAS date encoding differs from Python

---

## Pattern 1: INTCK — date difference

**SAS input**:
```sas
data a;
b = today();
DOB = '20nov1990'd;
fdate = intck('month', DOB, b, 'c');
run;
```

**Python (pandas) output**:
```python
import pandas as pd
from dateutil.relativedelta import relativedelta

# SAS: intck('month', start, end) → whole months between dates
# SAS: 'c' modifier = continuous (fractional months counted)
b = pd.Timestamp.today()
dob = pd.Timestamp("1990-11-20")

# SAS: intck('month', DOB, b) → months elapsed
fdate = (b.year - dob.year) * 12 + (b.month - dob.month)
# SAS: intck default = discrete (counts boundary crossings, not duration)
```

**INTCK interval reference**:

| SAS `intck` interval | pandas equivalent |
|---|---|
| `'day'` | `(end - start).days` |
| `'month'` | `(end.year - start.year)*12 + (end.month - start.month)` |
| `'year'` | `end.year - start.year` |
| `'week'` | `(end - start).days // 7` |
| `'quarter'` | `((end.year - start.year)*12 + (end.month - start.month)) // 3` |

---

## Pattern 2: INTNX — date arithmetic

**SAS input**:
```sas
data temp;
mydate = '23MAR2023'd;
format mydate date9.;
firstday = intnx('month', mydate, 0, 'b');   /* beginning of month */
sameday  = intnx('month', mydate, 0, 's');   /* same day */
lastday  = intnx('month', mydate, 0, 'e');   /* end of month */
nextmon  = intnx('month', mydate, 1, 'b');   /* beginning of next month */
lastyr   = intnx('year',  mydate, -1, 's');  /* same day last year */
run;
```

**Python (pandas) output**:
```python
import pandas as pd
from pandas.tseries.offsets import MonthBegin, MonthEnd, YearBegin

mydate = pd.Timestamp("2023-03-23")

# SAS: intnx('month', date, 0, 'b') → beginning of current month
firstday = mydate.replace(day=1)
# SAS: intnx('month', date, 0, 's') → same day (no movement)
sameday = mydate
# SAS: intnx('month', date, 0, 'e') → end of current month
lastday = mydate + MonthEnd(0)
# SAS: intnx('month', date, 1, 'b') → beginning of next month
nextmon = (mydate + MonthBegin(1)).replace(day=1)
# SAS: intnx('year', date, -1, 's') → same day last year
lastyr = mydate.replace(year=mydate.year - 1)
```

**INTNX alignment reference**:

| SAS alignment | pandas equivalent |
|---|---|
| `'b'` (beginning) | `.replace(day=1)` for month; `MonthBegin` offset |
| `'e'` (end) | `+ MonthEnd(0)` |
| `'m'` (middle) | `.replace(day=15)` |
| `'s'` (same day) | no movement — just advance the period |

---

## Pattern 3: Date formatting with PUT

**SAS input**:
```sas
data making;
set adft;
date_char = put(datee, mmddyy8.);
date_mm   = substr(date_char, 1, 2);
date_m    = month(datee);
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: put(datee, mmddyy8.) → strftime format
making = adft.copy()
making["date_char"] = making["datee"].dt.strftime("%m/%d/%y")
# SAS: mmddyy8. = MM/DD/YY (8 chars including slashes)

# SAS: substr(date_char, 1, 2) → first 2 chars = month part
making["date_mm"] = making["date_char"].str[:2]

# SAS: month(datee) → dt.month
making["date_m"] = making["datee"].dt.month
```

**PUT format → strftime reference**:

| SAS format | Python strftime |
|---|---|
| `date9.` | `"%d%b%Y"` (e.g. 20NOV1990) |
| `mmddyy8.` | `"%m/%d/%y"` |
| `mmddyy10.` | `"%m/%d/%Y"` |
| `ddmmyy10.` | `"%d/%m/%Y"` |
| `monyy5.` | `"%b%y"` |
| `monname3.` | `"%b"` |
| `monname.` | `"%B"` |
| `year4.` | `"%Y"` |

---

## Pattern 4: Age calculation with INTCK

**SAS input**:
```sas
data a;
input custname $ DOB: date9.;
tday_Date = today();
Age = Intck("Years", DOB, tday_Date);
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Intck("Years", DOB, today()) → age in complete years
today = pd.Timestamp.today()
a["Age"] = (
    (today.year - a["DOB"].dt.year)
    - ((today.month, today.day) < (a["DOB"].dt.month, a["DOB"].dt.day)).astype(int)
)
# SAS: intck counts boundary crossings — this replicates exact year count
```

---

## Pattern 5: Expanding dates across months (gym membership pattern)

**SAS input**:
```sas
data GymData_Complete;
set GymData;
Start_M = month(Jdate);
Start_E = month(Edate);
FDate = JDate;
cnt = 0;

do j = Start_M to Start_E;
    cnt + 1;
    if cnt = 1 then FDate = JDate;
    else FDate = intnx('month', FDate, 1);
    CMonth = put(FDate, MONNAME.);
    output;
end;
run;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Expanding one row per month between start and end date
def expand_months(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        # SAS: do j = Start_M to Start_E
        current = row["Jdate"].replace(day=1)
        end = row["Edate"].replace(day=1)
        while current <= end:
            new_row = row.copy()
            # SAS: CMonth = put(FDate, MONNAME.)
            new_row["CMonth"] = current.strftime("%B").upper()
            new_row["FDate"] = current
            rows.append(new_row)
            # SAS: FDate = intnx('month', FDate, 1)
            current = (current + pd.DateOffset(months=1)).replace(day=1)
    return pd.DataFrame(rows).reset_index(drop=True)

gym_complete = expand_months(gym_data)
```

---

## Pattern 6: Recent date filter (last 30 days)

**SAS input**:
```sas
proc sql;
select *
from emp4
where abs(today() - hiredate) < 30;
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: today() - hiredate < 30 → filter rows within 30 days of today
today = pd.Timestamp.today()
result = emp4[abs((today - emp4["hiredate"]).dt.days) < 30]
# SAS: abs() handles dates both before and after today
```

---

## SAS date encoding note (critical)

SAS stores dates as integers counting days since **January 1, 1960**.
Python/pandas uses `datetime64` (nanoseconds since 1970-01-01).

When reading SAS dates from files (e.g. via `pyreadstat` or `pandas.read_sas`):
```python
import pandas as pd

# SAS date integer → Python datetime
sas_epoch = pd.Timestamp("1960-01-01")
sas_date_int = 22970  # e.g. 01JAN2023

python_date = sas_epoch + pd.Timedelta(days=sas_date_int)
# Result: 2022-12-31 (check off-by-one before using)

# Or use pandas built-in when reading SAS files
df = pd.read_sas("file.sas7bdat", encoding="utf-8")
# pandas automatically converts SAS date columns to datetime64
```
