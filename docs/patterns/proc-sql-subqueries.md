# Pattern file: PROC SQL subqueries
## Source: Real SAS practice code — BFS/mortgage domain
## Complexity: HIGH — subqueries behave differently from pandas

---

## Pattern 1: NOT IN subquery (anti-join)

**SAS input**:
```sas
proc sql;
select * from feb
where name not in (select name from jan);
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: NOT IN subquery → anti-join using merge + indicator
result = feb.merge(
    jan[["name"]],
    on="name",
    how="left",
    indicator=True
).query('_merge == "left_only"').drop(columns=["_merge"])
# SAS: WHERE name NOT IN (SELECT name FROM jan)
```

**SQL (SQLAlchemy) output**:
```python
from sqlalchemy import select, not_

subq = select(jan.c.name).scalar_subquery()
stmt = select(feb).where(not_(feb.c.name.in_(subq)))
```

---

## Pattern 2: Correlated subquery for ranking

**SAS input**:
```sas
proc sql;
select a.make, a.origin, a.invoice,
(
    select count(make) from sashelp.cars as b
    where b.invoice >= a.invoice and a.make=b.make
) as rank
from sashelp.cars as a
where calculated rank <= 10
order by make, rank;
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Correlated subquery for rank within group
# → Use groupby + rank instead of correlated subquery
cars_ranked = sashelp_cars.copy()
cars_ranked["rank"] = (
    cars_ranked
    .groupby("make")["invoice"]
    .rank(method="min", ascending=False)
    .astype(int)
)
# SAS: WHERE calculated rank <= 10
result = (
    cars_ranked
    .query("rank <= 10")
    [["make", "origin", "invoice", "rank"]]
    .sort_values(["make", "rank"])
    .reset_index(drop=True)
)
```

**Notes**: SAS correlated subqueries counting rows where a condition holds
are almost always equivalent to pandas `rank()`. Use `method="min"` to match
SAS dense rank behaviour.

---

## Pattern 3: Scalar subquery in WHERE (compare to group aggregate)

**SAS input**:
```sas
proc sql;
select dep, sal
from emp3
having sal = max(sal);
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: HAVING sal = max(sal) → filter rows matching global max
result = emp3[emp3["sal"] == emp3["sal"].max()][["dep", "sal"]]
# SAS: HAVING without GROUP BY applies to entire table
```

---

## Pattern 4: Subquery for second highest value

**SAS input**:
```sas
proc sql;
select max(salary) from emp
where salary NOT IN (select max(salary) as mx from emp);
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Second highest salary using NOT IN subquery
max_sal = emp["salary"].max()
# SAS: WHERE salary NOT IN (SELECT max(salary))
second_highest = emp[emp["salary"] < max_sal]["salary"].max()
# SAS: SELECT max(salary) from the filtered set
```

**Notes**: For Nth highest, use `nlargest(n).iloc[-1]` — cleaner than chained subqueries.

---

## Pattern 5: CREATE TABLE with subquery + monotonic() row filter

**SAS input**:
```sas
proc sql;
create table topstates as
    select states, city, sum(Covidcase) as cnt
    from d
    group by states
    order by cnt desc;

select states, city, cnt, monotonic() as counts
from topstates
where calculated counts < 3;
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: CREATE TABLE with GROUP BY + ORDER BY
topstates = (
    d.groupby(["states", "city"], as_index=False)
    .agg(cnt=("Covidcase", "sum"))
    .sort_values("cnt", ascending=False)
    .reset_index(drop=True)
)
# SAS: monotonic() as counts → row number after sort
# SAS: WHERE counts < 3 → iloc first 2 rows
result = topstates.iloc[:2].reset_index(drop=True)
# SAS: monotonic() WARNING — only valid after ORDER BY in SAS too
```

**Notes**: `monotonic()` in SAS generates a row sequence number. In pandas,
use `.reset_index()` after sorting and filter on the index. Always treat
`monotonic()` as positional row number, not a stable ID.

---

## Pattern 6: Self-join (manager lookup)

**SAS input**:
```sas
proc sql;
select a.*, b.Name as Manager
from example2 as a
left join example2 as b
on a.managerid = b.id;
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: Self-join → merge dataframe with itself
result = example2.merge(
    example2[["id", "Name"]].rename(columns={"id": "ManagerID", "Name": "Manager"}),
    on="ManagerID",
    how="left"
)
# SAS: LEFT JOIN → how="left" preserves all rows from left (a)
```

---

## Pattern 7: MIN/MAX per group in WHERE clause

**SAS input**:
```sas
proc sql;
select distinct id, min(datee) format=date9.
from adft
group by id;
quit;
```

**Python (pandas) output**:
```python
import pandas as pd

# SAS: GROUP BY with MIN aggregate → groupby().min()
result = (
    adft
    .groupby("id", as_index=False)
    .agg(datee=("datee", "min"))
)
# SAS: DISTINCT id + MIN(datee) → one row per id with minimum date
```

---

## Pattern 8: CASE WHEN in SELECT

**SAS input**:
```sas
proc sql;
select Make, invoice,
    case when count(make) > 10 then 10
         else count(make)
    end as cnt
from sashelp.cars
group by make
having cnt = max(cnt)
order by make, invoice desc;
quit;
```

**Python (pandas) output**:
```python
import pandas as pd
import numpy as np

# SAS: CASE WHEN with aggregate → apply after groupby
cars_agg = sashelp_cars.groupby("make").agg(
    cnt=("make", "count")
).reset_index()
# SAS: CASE WHEN count > 10 THEN 10 ELSE count → np.clip
cars_agg["cnt"] = cars_agg["cnt"].clip(upper=10)
# SAS: HAVING cnt = max(cnt) → filter groups where cnt = max across all groups
max_cnt = cars_agg["cnt"].max()
result = (
    cars_agg[cars_agg["cnt"] == max_cnt]
    .merge(sashelp_cars[["make", "invoice"]], on="make")
    .sort_values(["make", "invoice"], ascending=[True, False])
    .reset_index(drop=True)
)
```

---

## monotonic() conversion reference

`monotonic()` is a SAS PROC SQL function with no direct SQL equivalent.
Always convert using one of these pandas patterns:

| SAS use case | pandas equivalent |
|---|---|
| Row number (no group) | `df.reset_index().rename(columns={"index":"cnt"})` |
| Row number within group | `df.groupby("key").cumcount() + 1` |
| Filter top N rows | `df.head(N)` or `df.iloc[:N]` |
| Filter bottom N rows | `df.tail(N)` or `df.iloc[-N:]` |
| Filter last row | `df.iloc[[-1]]` |
| Having cnt = max(cnt) | `df.iloc[[-1]]` after sort |
