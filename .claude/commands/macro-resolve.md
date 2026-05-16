# Command: /macro-resolve
**Usage**: `/macro-resolve <file.sas>`
**Purpose**: Resolve all %LET, %MACRO variable references before conversion
**Output**: Resolved SAS file written to `output/<filename>_resolved.sas`

---

## What this command does

Scans a SAS file for macro variable definitions and references,
resolves all `&variable` substitutions, and writes a clean SAS file
ready for `/convert`. Run this before `/convert` on any file
containing `%LET`, `%MACRO` parameters, or `&variable` references.

---

## Usage examples

```
/macro-resolve tests/sample_sas/macro_heavy.sas
/macro-resolve src/sas/credit_risk_report.sas
```

---

## Step-by-step execution — follow this exactly

### Step 1 — Read the SAS file
Read the file at the provided path.

### Step 2 — Extract %LET definitions
Scan for all `%LET varname = value;` statements.
Build a macro variable dict:
```
Found %LET definitions:
  &a        = "Manish"
  &threshold = 90
  &indata   = mortgages_raw
  &outdata  = mortgages_clean
  &n        = (computed — see Step 4)
```

### Step 3 — Extract %MACRO parameter definitions
For each `%MACRO name(param1=default, param2=default)` block:
```
Found %MACRO definitions:
  %macro calc_ltv(indata=, outdata=, threshold=90)
    Parameters: indata=None, outdata=None, threshold=90

  %macro plate(n=, name=)
    Parameters: n=None, name=None
```

### Step 4 — Identify unresolvable variables
Variables that cannot be resolved automatically:
- Parameters with no default: `indata=`, `outdata=`
- Variables set via `call symput` at runtime
- Variables from `PROC SQL into:`
- Variables referencing other unresolved variables

For each unresolvable variable, prompt the user:
```
⚠ Cannot auto-resolve these macro variables:
  &indata    — %MACRO parameter with no default
  &outdata   — %MACRO parameter with no default
  &threshold — has default (90) but may be overridden

Please provide values (press Enter to use default):
  &indata    = [user input]
  &outdata   = [user input]
  &threshold = [Enter for 90]
```

### Step 5 — Resolve all &variable references
Substitute every `&varname` and `&varname.` (with period) in the code
with the resolved value.

Handle dot notation:
```sas
data &name.1234;   →   data Mydata231234;
x="786&a.1";       →   x="786Manish1";
```

### Step 6 — Validate no unresolved references remain
Scan output for any remaining `&` followed by word characters.
If any remain → list them and ask user to provide values.

### Step 7 — Write resolved file
Write to: `output/<filename>_resolved.sas`
Example: `src/sas/report.sas` → `output/report_resolved.sas`

### Step 8 — Print summary
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/macro-resolve complete
Input:    src/sas/report.sas
Output:   output/report_resolved.sas
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Resolved:
  &threshold  → 90     (default from %MACRO)
  &indata     → mortgages_raw   (user provided)
  &outdata    → mortgages_clean (user provided)
  &a          → Manish   (from %LET)

Unresolved:
  (none)

Ready for: /convert output/report_resolved.sas
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Macro resolution reference

| SAS pattern | Resolution strategy |
|---|---|
| `%let x = value;` | Direct substitution → `x = "value"` |
| `%macro m(x=default)` | Use default unless overridden at call site |
| `%macro m(x=)` | No default — must prompt user |
| `call symput('var', val)` | Runtime — cannot auto-resolve, flag as TODO |
| `proc sql; select into: var` | Runtime — cannot auto-resolve, flag as TODO |
| `&var.suffix` (dot notation) | Resolve `&var`, preserve `suffix` after dot |
| `&&var&i` (indirect) | Resolve inner first → `&var1` → then resolve again |
| `%eval(&a + &b)` | Evaluate arithmetic after resolving `&a` and `&b` |
| `%sysevalf(&a / &b)` | Float arithmetic after resolving variables |

---

## Special SAS macro patterns from our codebase

### Double ampersand (indirect reference)
```sas
%let i=1;
%let dsn=abc;
%let abc1=cba1;

%put &&dsn&i;    /* resolves to: &dsn1 → abc1 */
%put &&&dsn&i;   /* resolves to: &&abc1 → cba1 */
```
Resolution steps:
1. `&&dsn&i` → `&dsn1` (first pass)
2. `&dsn1` → `abc1` (second pass — value of dsn1)

### Dot notation suffix
```sas
data &name.1234;   /* &name + literal "1234" */
x="&a.1";          /* &a + literal "1" */
```
Strip the dot after resolving — it is a delimiter, not part of the value.

### %sysfunc in macro
```sas
%let datarowsfinal = %sysfunc(ceil(&datarows));
```
After resolving `&datarows` → evaluate `ceil()` → store result.

---

## What this command must NOT do

- Must not modify the original `.sas` file
- Must not attempt to resolve `call symput` variables automatically
  (they are runtime values — flag as TODO only)
- Must not proceed to `/convert` automatically — let the user review
  the resolved file first
- Must not silently skip unresolvable variables — always prompt or flag
