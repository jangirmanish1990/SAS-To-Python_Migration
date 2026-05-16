"""SAS parser: tokenises raw SAS source into structured block dicts."""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_STEP_KEYWORDS: frozenset[str] = frozenset({
    'data', 'set', 'merge', 'by', 'where', 'drop', 'keep', 'label',
    'run', 'quit', 'if', 'else', 'then', 'do', 'end', 'output', 'retain',
    'array', 'length', 'format', 'informat', 'file', 'put', 'input',
    'return', 'stop', 'delete', 'abort', 'goto', 'link', 'leave',
    'continue', 'select', 'when', 'otherwise',
})

# Statement-starting keywords — these begin a SAS statement, not an assignment
_STMT_PREFIXES: frozenset[str] = frozenset({
    'data', 'set', 'merge', 'by', 'where', 'drop', 'keep', 'label',
    'run', 'quit', 'retain', 'array', 'length', 'format', 'informat',
    'file', 'return', 'stop', 'delete', 'abort', 'goto', 'link', 'leave',
    'continue', 'select', 'when', 'otherwise', 'output', 'do', 'end', 'put',
    'attrib', 'rename', 'title', 'footnote', 'missing', 'options', 'input',
})

_PROC_MEANS_STATS: frozenset[str] = frozenset({
    'n', 'mean', 'std', 'min', 'max', 'median', 'sum', 'var', 'cv', 'p25', 'p75',
})

_AGG_FUNCS: frozenset[str] = frozenset({
    'count', 'sum', 'avg', 'mean', 'min', 'max', 'std', 'var',
})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _strip_comments(code: str) -> str:
    """Remove /* block */ and * line; comments, preserving quoted string content."""
    result: list[str] = []
    i = 0
    n = len(code)

    while i < n:
        ch = code[i]
        if ch in ("'", '"'):
            result.append(ch)
            i += 1
            while i < n:
                c = code[i]
                result.append(c)
                i += 1
                if c == ch:
                    break
        elif ch == '/' and i + 1 < n and code[i + 1] == '*':
            # Consume block comment, emit a space to avoid token merging
            i += 2
            while i < n:
                if code[i] == '*' and i + 1 < n and code[i + 1] == '/':
                    i += 2
                    break
                i += 1
            result.append(' ')
        else:
            result.append(ch)
            i += 1

    stripped = ''.join(result)
    # * comment statements: optional whitespace, *, anything, ; — only at line start
    stripped = re.sub(r'(?m)^[ \t]*\*[^;]*;[ \t]*$', '', stripped)
    return stripped


def _normalise(code: str) -> str:
    """Collapse all whitespace runs to a single space."""
    return re.sub(r'\s+', ' ', code).strip()


def _dataset_names(val: str) -> list[str]:
    """Extract bare dataset names from a SET/MERGE/FROM value, stripping options."""
    # Remove (option=...) clauses so jan(in=x) feb(in=y) → ['jan', 'feb']
    clean = re.sub(r'\([^)]*\)', '', val)
    parts = clean.split()
    return [
        p.lower() for p in parts
        if re.match(r'^[A-Za-z_][\w.]*$', p) and p.lower() not in _DATA_STEP_KEYWORDS
    ]


def _split_into_raw_blocks(code: str) -> list[str]:
    """Split cleaned SAS source at DATA / PROC / %MACRO boundaries."""
    parts = re.split(r'(?im)(?=^\s*(?:data|proc|%macro)\b)', code)
    blocks: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        term = re.search(r'(?i)\b(?:run|quit)\s*;|%mend\b[^;]*;', part)
        blocks.append(part[: term.end()].strip() if term else part)
    return blocks


# ---------------------------------------------------------------------------
# Construct-specific parsers (operate on normalised text, store raw original)
# ---------------------------------------------------------------------------

def _parse_data_step(norm: str, raw: str) -> dict:
    block: dict = {'type': 'data_step', 'raw_code': raw}

    m = re.match(r'(?i)DATA\s+(\S+?)\s*;', norm)
    if m:
        block['output_dataset'] = m.group(1).lower()

    merge_m = re.search(r'(?i)\bMERGE\s+([\w\s.()\-=]+?)\s*;', norm)
    set_m = re.search(r'(?i)\bSET\s+([\w\s.()\-=]+?)\s*;', norm)

    if merge_m:
        block['is_merge'] = True
        block['input_datasets'] = _dataset_names(merge_m.group(1))
        by_m = re.search(r'(?i)\bBY\s+([\w\s]+?)\s*;', norm)
        if by_m:
            keys = [k.lower() for k in by_m.group(1).split()
                    if k.lower() not in _DATA_STEP_KEYWORDS]
            if keys:
                block['merge_keys'] = keys
    elif set_m:
        block['is_merge'] = False
        block['input_datasets'] = _dataset_names(set_m.group(1))
    else:
        block['is_merge'] = False

    where_m = re.search(r'(?i)\bWHERE\s+(.+?)\s*;', norm)
    if where_m:
        block['where_clause'] = where_m.group(1).strip()

    derived: dict[str, str] = {}

    for stmt in norm.split(';'):
        stmt = stmt.strip()
        if not stmt:
            continue
        first_word = stmt.split()[0].lower() if stmt.split() else ''

        if first_word in _STMT_PREFIXES:
            continue

        if first_word == 'if':
            then_m = re.search(r'(?i)\bTHEN\s+([A-Za-z_][\w.]*)\s*=\s*(.+)$', stmt)
            if then_m:
                col, expr = then_m.group(1).lower(), then_m.group(2).strip()
                if col not in _DATA_STEP_KEYWORDS:
                    derived[col] = f'IF ... THEN {col} = {expr}'
            elif 'where_clause' not in block:
                # Subsetting IF with no THEN: treat as filter condition
                cond = re.sub(r'(?i)^if\s+', '', stmt).strip()
                if cond:
                    block['where_clause'] = cond
            continue

        if first_word == 'else':
            rest = re.sub(r'(?i)^else\s+', '', stmt).strip()
            am = re.match(r'([A-Za-z_][\w.]*)\s*=\s*(.+)$', rest, re.IGNORECASE)
            sm = re.match(r'([A-Za-z_][\w.]*)\s*\+\s*(.+)$', rest, re.IGNORECASE)
            if am:
                col, expr = am.group(1).lower(), am.group(2).strip()
                if col not in _DATA_STEP_KEYWORDS:
                    derived[col] = expr
            elif sm:
                col, incr = sm.group(1).lower(), sm.group(2).strip()
                if col not in _DATA_STEP_KEYWORDS:
                    derived[col] = f'{col} + {incr}'
            continue

        # Running sum: var + expr (SAS sum statement)
        sm = re.match(r'([A-Za-z_][\w.]*)\s*\+\s*(.+)$', stmt, re.IGNORECASE)
        if sm:
            col, incr = sm.group(1).lower(), sm.group(2).strip()
            if col not in _DATA_STEP_KEYWORDS:
                derived[col] = f'{col} + {incr}'
            continue

        # Regular assignment: col = expr
        am = re.match(r'([A-Za-z_][\w.]*)\s*=\s*(.+)$', stmt, re.IGNORECASE)
        if am:
            col, expr = am.group(1).lower(), am.group(2).strip()
            # Exclude FIRST./LAST. pseudo-variables and SAS keywords
            if col not in _DATA_STEP_KEYWORDS and '.' not in col:
                derived[col] = expr

    if derived:
        block['derived_columns'] = derived

    drop_m = re.search(r'(?i)\bDROP\s+([\w\s]+?)\s*;', norm)
    if drop_m:
        block['dropped_columns'] = [c.lower() for c in drop_m.group(1).split()]

    keep_m = re.search(r'(?i)\bKEEP\s+([\w\s]+?)\s*;', norm)
    if keep_m:
        block['kept_columns'] = [c.lower() for c in keep_m.group(1).split()]

    labels: dict[str, str] = {}
    for lm in re.finditer(r"(?i)\bLABEL\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]", norm):
        labels[lm.group(1).lower()] = lm.group(2)
    if labels:
        block['label_map'] = labels

    return block


def _build_sql_block(stmt: str, raw: str) -> dict:
    """Build a block dict from one normalised SQL statement string."""
    block: dict = {'type': 'proc_sql', 'raw_code': raw}

    ct_m = re.match(r'(?i)CREATE\s+TABLE\s+(\w+)\s+AS\b', stmt)
    if ct_m:
        block['output_dataset'] = ct_m.group(1).lower()

    sel_m = re.search(r'(?i)\bSELECT\s+(.+?)\s+\bFROM\b', stmt)
    if sel_m:
        raw_sel = sel_m.group(1)
        block['select_columns'] = [c.strip() for c in raw_sel.split(',') if c.strip()]
        aggs = [f for f in _AGG_FUNCS if re.search(r'(?i)\b' + f + r'\s*\(', raw_sel)]
        if aggs:
            block['aggregate_functions'] = sorted(aggs)

    sources: list[str] = []
    from_m = re.search(r'(?i)\bFROM\s+(\w+)', stmt)
    if from_m:
        sources.append(from_m.group(1).lower())
    for jm in re.finditer(r'(?i)\bJOIN\s+(\w+)', stmt):
        sources.append(jm.group(1).lower())
    if sources:
        block['input_datasets'] = sources

    where_m = re.search(
        r'(?i)\bWHERE\s+(.+?)(?=\s+(?:GROUP|ORDER|HAVING)\b|$)', stmt
    )
    if where_m:
        block['where_clause'] = where_m.group(1).strip()

    grp_m = re.search(
        r'(?i)\bGROUP\s+BY\s+([\w\s,]+?)(?=\s+(?:ORDER|HAVING|WHERE)\b|$)', stmt
    )
    if grp_m:
        cols = [c.strip().lower() for c in grp_m.group(1).split(',') if c.strip()]
        block['group_by'] = cols
        block['has_group_by'] = True

    ord_m = re.search(r'(?i)\bORDER\s+BY\s+(.+?)(?=\s+\b|$)', stmt)
    if ord_m:
        cols = [c.strip() for c in ord_m.group(1).split(',') if c.strip()]
        block['sort_by'] = cols

    return block


def _parse_proc_sql(norm: str, raw: str) -> list[dict]:
    """Parse PROC SQL, returning one block dict per CREATE TABLE statement."""
    # Group semicolon-delimited statements into CREATE TABLE chunks
    stmts = norm.split(';')
    create_stmts: list[str] = []
    current: list[str] = []

    for stmt in stmts:
        stmt = stmt.strip()
        if not stmt or re.match(r'(?i)^(?:PROC\s+SQL|QUIT)\b', stmt):
            if current:
                create_stmts.append(' '.join(current))
                current = []
            continue
        if re.match(r'(?i)^CREATE\s+TABLE\b', stmt):
            if current:
                create_stmts.append(' '.join(current))
            current = [stmt]
        elif current:
            current.append(stmt)

    if current:
        create_stmts.append(' '.join(current))

    if not create_stmts:
        # Plain SELECT with no CREATE TABLE
        return [_build_sql_block(norm, raw)]

    return [_build_sql_block(cs, raw) for cs in create_stmts]


def _parse_proc_means(norm: str, raw: str) -> dict:
    block: dict = {'type': 'proc_means', 'raw_code': raw}

    proc_line_m = re.match(r'(?i)(PROC\s+MEANS[^;]*);', norm)
    if proc_line_m:
        proc_line = proc_line_m.group(1).upper()
        stats = [s.upper() for s in _PROC_MEANS_STATS
                 if re.search(r'\b' + s.upper() + r'\b', proc_line)]
        if stats:
            block['stats_requested'] = stats

    m = re.search(r'(?i)\bDATA\s*=\s*(\w+)', norm)
    if m:
        block['input_datasets'] = [m.group(1).lower()]

    m = re.search(r'(?i)\bOUT\s*=\s*(\w+)', norm)
    if m:
        block['output_dataset'] = m.group(1).lower()

    m = re.search(r'(?i)\bVAR\s+([\w\s]+?)\s*;', norm)
    if m:
        block['stat_vars'] = m.group(1).split()

    m = re.search(r'(?i)\bCLASS\s+([\w\s]+?)\s*;', norm)
    if m:
        block['class_vars'] = m.group(1).split()

    return block


def _parse_proc_freq(norm: str, raw: str) -> dict:
    block: dict = {'type': 'proc_freq', 'raw_code': raw}

    m = re.search(r'(?i)\bDATA\s*=\s*(\w+)', norm)
    if m:
        block['input_datasets'] = [m.group(1).lower()]

    m = re.search(r'(?i)\bTABLES\s+([\w\s*/]+?)\s*;', norm)
    if m:
        # Take only the variable spec before the / (options follow /)
        var_part = m.group(1).split('/')[0]
        vars_ = re.split(r'[\s*]+', var_part.strip())
        block['stat_vars'] = [v for v in vars_ if v and re.match(r'^\w+$', v)]

    return block


def _parse_proc_sort(norm: str, raw: str) -> dict:
    block: dict = {'type': 'proc_sort', 'raw_code': raw}

    m = re.search(r'(?i)\bDATA\s*=\s*(\w+)', norm)
    if m:
        block['input_datasets'] = [m.group(1).lower()]

    m = re.search(r'(?i)\bOUT\s*=\s*(\w+)', norm)
    if m:
        block['output_dataset'] = m.group(1).lower()

    m = re.search(r'(?i)\bBY\s+([\w\s]+?)\s*;', norm)
    if m:
        block['sort_by'] = m.group(1).split()

    m = re.search(r'(?i)\bWHERE\s+(.+?)\s*;', norm)
    if m:
        block['where_clause'] = m.group(1).strip()

    return block


def _parse_macro_block(norm: str, raw: str) -> dict:
    block: dict = {'type': 'macro', 'raw_code': raw}

    m = re.match(r'(?i)%MACRO\s+(\w+)\s*(?:\(([^)]*)\))?', norm)
    if m:
        block['macro_name'] = m.group(1).lower()
        params_str = m.group(2) or ''
        params: dict[str, dict] = {}
        if params_str.strip():
            for param in params_str.split(','):
                param = param.strip()
                if not param:
                    continue
                if '=' in param:
                    pname, default = param.split('=', 1)
                    params[pname.strip().lower()] = {'default': default.strip() or None}
                else:
                    params[param.lower()] = {'default': None}
        block['parameters'] = params

    return block


def _parse_block(raw_block: str) -> list[dict]:
    """Dispatch a raw block to the appropriate parser, returning block dict(s)."""
    norm = _normalise(raw_block)
    construct = detect_construct(norm)
    try:
        if construct == 'data_step':
            return [_parse_data_step(norm, raw_block)]
        if construct == 'proc_sql':
            return _parse_proc_sql(norm, raw_block)
        if construct == 'proc_means':
            return [_parse_proc_means(norm, raw_block)]
        if construct == 'proc_freq':
            return [_parse_proc_freq(norm, raw_block)]
        if construct == 'proc_sort':
            return [_parse_proc_sort(norm, raw_block)]
        if construct == 'macro':
            return [_parse_macro_block(norm, raw_block)]
        return [{'type': construct, 'raw_code': raw_block}]
    except Exception:
        return [{'type': 'unknown', 'raw_code': raw_block}]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_construct(code: str) -> str:
    """Return the SAS construct type for a single block string.

    Args:
        code: Single SAS block (raw or normalised). Case-insensitive.

    Returns:
        One of: ``data_step``, ``proc_sql``, ``proc_means``, ``proc_freq``,
        ``proc_sort``, ``proc_print``, ``proc_transpose``, ``macro``, ``unknown``.
    """
    norm = _normalise(code).upper()
    if re.match(r'DATA\b', norm):
        return 'data_step'
    if re.match(r'PROC\s+SQL\b', norm):
        return 'proc_sql'
    if re.match(r'PROC\s+MEANS\b', norm):
        return 'proc_means'
    if re.match(r'PROC\s+FREQ\b', norm):
        return 'proc_freq'
    if re.match(r'PROC\s+SORT\b', norm):
        return 'proc_sort'
    if re.match(r'PROC\s+PRINT\b', norm):
        return 'proc_print'
    if re.match(r'PROC\s+TRANSPOSE\b', norm):
        return 'proc_transpose'
    if re.match(r'%MACRO\b', norm):
        return 'macro'
    return 'unknown'


def parse_sas(code: str) -> list[dict]:
    """Parse a full SAS program into a list of structured block dicts.

    Args:
        code: Full SAS program as a string (single or multi-block).

    Returns:
        Ordered list of block dicts, one per logical SAS construct.
        Returns ``[]`` for empty or comments-only input. Never raises.
    """
    if not code or not code.strip():
        return []

    cleaned = _strip_comments(code)
    if not cleaned.strip():
        return []

    result: list[dict] = []
    for raw_block in _split_into_raw_blocks(cleaned):
        result.extend(_parse_block(raw_block))

    return result


def extract_macros(code: str) -> dict:
    """Extract all %MACRO definitions from SAS source.

    Args:
        code: SAS source containing one or more %MACRO definitions.

    Returns:
        ``{ macro_name: { parameters: { name: { default: value | None } }, body: str } }``
    """
    cleaned = _strip_comments(code)
    macros: dict[str, dict] = {}

    for m in re.finditer(
        r'(?i)%MACRO\s+(\w+)\s*(?:\(([^)]*)\))?\s*;(.+?)%MEND\b[^;]*;',
        cleaned,
        re.DOTALL,
    ):
        name = m.group(1).lower()
        params_str = m.group(2) or ''
        body = m.group(3).strip()

        params: dict[str, dict] = {}
        if params_str.strip():
            for param in params_str.split(','):
                param = param.strip()
                if not param:
                    continue
                if '=' in param:
                    pname, default = param.split('=', 1)
                    params[pname.strip().lower()] = {'default': default.strip() or None}
                else:
                    params[param.lower()] = {'default': None}

        macros[name] = {'parameters': params, 'body': body}

    return macros


def resolve_macros(code: str, macro_values: dict) -> str:
    """Replace ``&variable`` references in SAS source with substitution values.

    Args:
        code: SAS source containing ``&variable`` references.
        macro_values: Mapping of variable names to replacement strings.

    Returns:
        SAS source with all ``&variable`` (and ``&variable.``) refs replaced.

    Raises:
        ValueError: If any ``&variable`` reference remains unresolved.
    """
    result = code
    # Longest names first to avoid partial substitution (e.g. &nm before &name)
    for name, value in sorted(macro_values.items(), key=lambda kv: -len(kv[0])):
        result = re.sub(
            r'(?i)&' + re.escape(name) + r'\.?',
            str(value),
            result,
        )

    remaining = re.findall(r'&\w+', result)
    if remaining:
        raise ValueError(f'Unresolved macro variable: {remaining[0]}')

    return result
