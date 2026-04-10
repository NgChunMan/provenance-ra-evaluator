"""
SQL-to-Relational-Algebra translator.

Translates a subset of SQL SELECT queries into relational algebra
expression strings compatible with ``src.parser.parse()``.

Supported SQL subset
--------------------
- ``SELECT [DISTINCT] col1, col2, ... FROM table1, table2, ... [WHERE cond]``
- ``SELECT [DISTINCT] * FROM table [WHERE cond]``
- ``UNION ALL`` maps to multiset sum ⊎; ``UNION`` maps to δ(⊎) (deduplication applied after merging)
- WHERE conditions: ``=``, ``<>``, ``!=``, ``>=``, ``<=``, ``>``, ``<``,
  ``AND``, ``OR``, ``NOT``, and parentheses for grouping
- ``IN (val1, val2, ...)``, ``NOT IN (...)``
- ``LIKE 'pattern'``, ``NOT LIKE 'pattern'`` (``%`` and ``_`` wildcards)
- ``BETWEEN val1 AND val2``
- ``expr % expr`` (modulo)
- ``DATE 'YYYY-MM-DD'`` literals (treated as string comparisons)
- ``DATE 'YYYY-MM-DD' + INTERVAL 'n' YEAR|MONTH|DAY`` (computed at translation time)
- Qualified column references: ``T.col``
- Optional ``AS`` aliases on tables and columns (aliases are silently ignored)

Unsupported SQL constructs (raise :class:`SQLTranslationError`)
---------------------------------------------------------------
- ``GROUP BY`` / ``HAVING`` / aggregate functions
- ``ORDER BY`` / ``LIMIT`` / ``OFFSET``
- Subqueries in FROM or WHERE
- ``JOIN … ON`` syntax (use ``FROM t1, t2 WHERE …`` instead)
- ``INTERSECT`` / ``EXCEPT``

SQL → RA operator mapping
--------------------------
+--------------------------+---------------------------+
| SQL construct            | RA expression             |
+==========================+===========================+
| ``FROM R``               | ``R``                     |
| ``FROM R, S``            | ``(R × S)``               |
| ``WHERE cond``           | ``σ[cond](…)``            |
| ``SELECT a, b``          | ``π[a, b](…)``            |
| ``SELECT *``             | (no projection node)      |
| ``DISTINCT``             | ``δ(…)``                  |
| ``UNION``                | ``δ(… ⊎ …)``             |
| ``UNION ALL``            | ``(… ⊎ …)``               |
| ``AND``                  | ``/\\``                   |
| ``OR``                   | ``\\/``                   |
| ``NOT``                  | ``~(…)``                  |
| ``=``                    | ``==``                    |
| ``<>``                   | ``!=``                    |
+--------------------------+---------------------------+
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# ── Public exception ──────────────────────────────────────────────────

class SQLTranslationError(ValueError):
    """Raised when a SQL query cannot be translated to relational algebra.

    Covers both syntax errors and the use of unsupported SQL constructs.
    """


# ── Tokenizer ─────────────────────────────────────────────────────────

_KEYWORDS = frozenset({
    # Supported
    'SELECT', 'DISTINCT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT',
    'UNION', 'ALL', 'AS',
    'IN', 'LIKE', 'BETWEEN', 'DATE',
    'INTERVAL', 'YEAR', 'MONTH', 'DAY',
    # Recognised but unsupported — kept for clear error messages
    'GROUP', 'BY', 'HAVING', 'ORDER', 'LIMIT', 'OFFSET',
    'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'ON',
    'INTERSECT', 'EXCEPT',
})

# Maps the first keyword of an unsupported trailing clause to its display name.
_UNSUPPORTED_CLAUSES = {
    'GROUP': 'GROUP BY (aggregation)',
    'HAVING': 'HAVING (aggregation filter)',
    'ORDER': 'ORDER BY',
    'LIMIT': 'LIMIT',
    'OFFSET': 'OFFSET',
    'JOIN': 'JOIN … ON (use FROM t1, t2 WHERE … instead)',
    'INNER': 'INNER JOIN',
    'LEFT': 'LEFT JOIN',
    'RIGHT': 'RIGHT JOIN',
    'CROSS': 'CROSS JOIN (use FROM t1, t2 instead)',
    'INTERSECT': 'INTERSECT',
    'EXCEPT': 'EXCEPT',
}

_Token = Tuple[str, str]
_TokenList = List[_Token]


def _tokenize(sql: str) -> _TokenList:
    """Tokenize a SQL string into ``(tag, value)`` pairs.

    Tags:
        ``KW``: SQL keyword (stored upper-cased).
        ``IDENT``: Identifier, or ``table.column`` qualified name.
        ``INT``: Integer literal (stored as string of digits).
        ``STR``: String literal (including surrounding single quotes).
        ``OP``: Comparison operator (``=``, ``<>``, ``!=``, ``>=``, ``<=``,
            ``>``, ``<``).
        ``COMMA``: ``,``.
        ``STAR``: ``*``.
        ``OPAR``: ``(``.
        ``CPAR``: ``)``.
        ``MOD``: ``%``.

    Args:
        sql (str): A SQL query string.

    Returns:
        _TokenList: List of ``(tag, value)`` token tuples.

    Raises:
        SQLTranslationError: On unterminated string literals or unrecognised
            characters.
    """
    tokens: _TokenList = []
    i = 0
    n = len(sql)

    while i < n:
        # Whitespace
        if sql[i].isspace():
            i += 1
            continue

        # String literal 'value'
        if sql[i] == "'":
            j = i + 1
            while j < n and sql[j] != "'":
                j += 1
            if j >= n:
                raise SQLTranslationError(
                    f"Unterminated string literal starting at position {i}"
                )
            tokens.append(('STR', sql[i : j + 1]))
            i = j + 1
            continue

        # Two-character operators
        if i + 1 < n and sql[i : i + 2] in ('<>', '!=', '>=', '<='):
            tokens.append(('OP', sql[i : i + 2]))
            i += 2
            continue

        # Single-character operators and punctuation
        if sql[i] in ('=', '>', '<'):
            tokens.append(('OP', sql[i]))
            i += 1
            continue
        if sql[i] == ',':
            tokens.append(('COMMA', ','))
            i += 1
            continue
        if sql[i] == '%':
            tokens.append(('MOD', '%'))
            i += 1
            continue
        if sql[i] == '+':
            tokens.append(('PLUS', '+'))
            i += 1
            continue
        if sql[i] == '-':
            # Distinguish minus from negative: only emit MINUS token
            # (date arithmetic); negative numbers not supported yet.
            tokens.append(('MINUS', '-'))
            i += 1
            continue
        if sql[i] == '*':
            tokens.append(('STAR', '*'))
            i += 1
            continue
        if sql[i] == '(':
            tokens.append(('OPAR', '('))
            i += 1
            continue
        if sql[i] == ')':
            tokens.append(('CPAR', ')'))
            i += 1
            continue

        # Integer literal
        if sql[i].isdigit():
            j = i
            while j < n and sql[j].isdigit():
                j += 1
            tokens.append(('INT', sql[i : j]))
            i = j
            continue

        # Identifier or keyword
        if sql[i].isalpha() or sql[i] == '_':
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == '_'):
                j += 1
            word = sql[i : j]
            upper = word.upper()
            if upper in _KEYWORDS:
                tokens.append(('KW', upper))
                i = j
            else:
                # Handle table.column qualified references
                if j < n and sql[j] == '.':
                    k = j + 1
                    while k < n and (sql[k].isalnum() or sql[k] == '_'):
                        k += 1
                    col = sql[j + 1 : k]
                    if not col:
                        raise SQLTranslationError(
                            f"Expected a column name after '.' in '{word}.'"
                        )
                    tokens.append(('IDENT', f"{word}.{col}"))
                    i = k
                else:
                    tokens.append(('IDENT', word))
                    i = j
            continue

        raise SQLTranslationError(
            f"Unrecognised character '{sql[i]}' at position {i}"
        )

    return tokens


# ── Date arithmetic helper ────────────────────────────────────────────

def _date_add(date_lit: str, amount: int, unit: str) -> str:
    """Compute ``date_lit +/- amount unit`` and return a new ``'YYYY-MM-DD'`` literal.

    Args:
        date_lit (str): A date string literal like ``'1994-01-01'`` (with or
            without surrounding single quotes).
        amount (int): Number of units to add (use a negative value to subtract).
        unit (str): One of ``'YEAR'``, ``'MONTH'``, ``'DAY'``.

    Returns:
        str: New date literal with surrounding single quotes,
        e.g. ``"'1995-01-01'"``.

    Raises:
        SQLTranslationError: If the date literal cannot be parsed or the unit
            is not recognised.
    """
    from datetime import date, timedelta

    # Strip surrounding quotes
    raw = date_lit.strip("'")
    parts = raw.split("-")
    if len(parts) != 3:
        raise SQLTranslationError(
            f"Cannot parse date literal: {date_lit}"
        )
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])

    if unit == "YEAR":
        y += amount
    elif unit == "MONTH":
        m += amount
        # Normalise month overflow/underflow
        while m > 12:
            m -= 12
            y += 1
        while m < 1:
            m += 12
            y -= 1
    elif unit == "DAY":
        dt = date(y, m, d) + timedelta(days=amount)
        return f"'{dt.isoformat()}'"
    else:
        raise SQLTranslationError(f"Unsupported interval unit: {unit}")

    # Clamp day to max valid day for the resulting month
    import calendar
    max_day = calendar.monthrange(y, m)[1]
    d = min(d, max_day)

    return f"'{date(y, m, d).isoformat()}'"


# ── Recursive-descent translator ──────────────────────────────────────

class _Translator:
    """
    Consumes a token list and produces a relational algebra expression string.

    The grammar supported is::

        query:= select_stmt (UNION [ALL] select_stmt)*
        select_stmt:= SELECT [DISTINCT] col_list FROM table_list [WHERE condition]
        col_list:= * | col (, col)*
        col:= IDENT [AS IDENT]
        table_list:= table (, table)*
        table:= IDENT [AS IDENT]
        condition:= or_cond
        or_cond:= and_cond (OR and_cond)*
        and_cond:= not_cond (AND not_cond)*
        not_cond:= NOT not_cond | atom_cond
        atom_cond:= (condition) | comparison
        comparison:= expr OP expr
        expr:= IDENT | INT | STR
    """

    _SQL_TO_RA_OP = {
        '=': '==',
        '<>': '!=',
        '!=': '!=',
        '>=': '>=',
        '<=': '<=',
        '>': '>',
        '<': '<',
    }

    def __init__(self, tokens: _TokenList) -> None:
        self._tokens = tokens
        self._pos = 0
        self._alias_map: Dict[str, str] = {}  # alias → real table name

    # ── Low-level helpers ─────────────────────────────────────────────

    def _peek(self) -> Optional[_Token]:
        if self._pos >= len(self._tokens):
            return None
        return self._tokens[self._pos]

    def _peek_tag(self) -> Optional[str]:
        t = self._peek()
        return t[0] if t else None

    def _peek_is(self, tag: str, val: str) -> bool:
        t = self._peek()
        return t is not None and t == (tag, val)

    def _consume(self) -> _Token:
        if self._pos >= len(self._tokens):
            raise SQLTranslationError("Unexpected end of SQL input")
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect_kw(self, kw: str) -> None:
        tag, val = self._consume()
        if tag != 'KW' or val != kw:
            raise SQLTranslationError(
                f"Expected SQL keyword '{kw}', got '{val}'"
            )

    # ── Grammar rules ─────────────────────────────────────────────────

    def translate(self) -> str:
        """Produce the full RA expression string from the token stream.

        Returns:
            str: The translated relational algebra expression.

        Raises:
            SQLTranslationError: If the token stream does not match the
                supported SQL grammar.
        """
        result = self._parse_select()
        while self._peek_is('KW', 'UNION'):
            self._consume()
            is_union_all = False
            if self._peek_is('KW', 'ALL'):
                self._consume() 
                is_union_all = True
            rhs = self._parse_select()
            merged = f"({result} ∪ {rhs})"
            result = merged if is_union_all else f"δ({merged})"
        if self._peek() is not None:
            _, val = self._peek()
            raise SQLTranslationError(
                f"Unexpected token '{val}' after end of query. "
                "Did you mean to use UNION?"
            )
        return result

    def _parse_select(self) -> str:
        self._expect_kw('SELECT')

        distinct = False
        if self._peek_is('KW', 'DISTINCT'):
            self._consume()
            distinct = True

        cols: Optional[List[str]] = self._parse_col_list()
        self._expect_kw('FROM')
        tables: List[str] = self._parse_table_list()

        where_cond: Optional[str] = None
        if self._peek_is('KW', 'WHERE'):
            self._consume()
            where_cond = self._parse_or_cond()

        # Reject unsupported trailing clauses with a helpful message
        t = self._peek()
        if t is not None and t[0] == 'KW' and t[1] in _UNSUPPORTED_CLAUSES:
            clause = _UNSUPPORTED_CLAUSES[t[1]]
            raise SQLTranslationError(
                f"SQL clause '{clause}' is not supported. "
                "Supported syntax: SELECT [DISTINCT] cols FROM tables [WHERE cond]"
            )

        # Build RA expression bottom-up:
        # 1. Cross product of all FROM tables (left-associative)
        rel = self._build_cross_product(tables)
        # 2. Selection (WHERE)
        if where_cond is not None:
            rel = f"σ[{where_cond}]({rel})"
        # 3. Projection (SELECT cols; omitted for SELECT *)
        if cols is not None:
            rel = f"π[{', '.join(cols)}]({rel})"
        # 4. Deduplication (DISTINCT)
        if distinct:
            rel = f"δ({rel})"

        return rel

    def _build_cross_product(self, tables: List[str]) -> str:
        rel = tables[0]
        for t in tables[1:]:
            rel = f"({rel} × {t})"
        return rel

    def _parse_col_list(self) -> Optional[List[str]]:
        """Parse the SELECT column list.

        Returns:
            Optional[List[str]]: ``None`` for ``SELECT *``, or a list of
            column name strings.
        """
        if self._peek_tag() == 'STAR':
            self._consume()
            return None
        cols = [self._parse_col()]
        while self._peek_tag() == 'COMMA':
            self._consume()
            cols.append(self._parse_col())
        return cols

    def _parse_col(self) -> str:
        tag, val = self._consume()
        if tag != 'IDENT':
            raise SQLTranslationError(
                f"Expected a column name in SELECT list, got '{val}'"
            )
        # Silently ignore optional AS alias
        if self._peek_is('KW', 'AS'):
            self._consume()
            if self._peek_tag() == 'IDENT':
                self._consume()
        return val

    def _parse_table_list(self) -> List[str]:
        tables = [self._parse_table()]
        while self._peek_tag() == 'COMMA':
            self._consume()
            tables.append(self._parse_table())
        return tables

    def _parse_table(self) -> str:
        tag, val = self._consume()
        if tag != 'IDENT':
            raise SQLTranslationError(
                f"Expected a table name in FROM clause, got '{val}'"
            )
        table_name = val
        alias = val  # default: alias is the table name itself
        # Check for optional alias: table_name alias or table_name AS alias
        if self._peek_is('KW', 'AS'):
            self._consume()
            if self._peek_tag() == 'IDENT':
                _, alias = self._consume()
        elif (self._peek_tag() == 'IDENT'
              and not self._peek_is('KW', 'WHERE')
              and not self._peek_is('KW', 'GROUP')
              and not self._peek_is('KW', 'ORDER')):
            # Bare alias without AS: "nation n1"
            # Only consume if next token is NOT a keyword we care about
            next_tok = self._peek()
            if next_tok and next_tok[0] == 'IDENT':
                _, alias = self._consume()
        if alias != table_name:
            self._alias_map[alias] = table_name
        return alias

    # ── Condition parsing ─────────────────────────────────────────────

    def _parse_or_cond(self) -> str:
        result = self._parse_and_cond()
        while self._peek_is('KW', 'OR'):
            self._consume()
            rhs = self._parse_and_cond()
            result = f"{result} \\/ {rhs}"
        return result

    def _parse_and_cond(self) -> str:
        result = self._parse_not_cond()
        while self._peek_is('KW', 'AND'):
            self._consume()
            rhs = self._parse_not_cond()
            result = f"{result} /\\ {rhs}"
        return result

    def _parse_not_cond(self) -> str:
        if self._peek_is('KW', 'NOT'):
            # Peek ahead: NOT followed by IN or LIKE belongs to the
            # comparison (e.g. "col NOT IN (...)"), not boolean negation.
            next_pos = self._pos + 1
            if next_pos < len(self._tokens):
                next_tok = self._tokens[next_pos]
                if next_tok == ('KW', 'IN') or next_tok == ('KW', 'LIKE'):
                    return self._parse_atom_cond()
            self._consume()
            inner = self._parse_not_cond()
            return f"~({inner})"
        return self._parse_atom_cond()

    def _parse_atom_cond(self) -> str:
        if self._peek_tag() == 'OPAR':
            self._consume()
            inner = self._parse_or_cond()
            if self._peek_tag() != 'CPAR':
                raise SQLTranslationError(
                    "Expected closing ')' to match '(' in condition"
                )
            self._consume()
            return f"({inner})"
        return self._parse_comparison()

    def _parse_comparison(self) -> str:
        lhs = self._parse_atom_expr()

        # Handle: expr IN (v1, v2, ...)
        if self._peek_is('KW', 'IN'):
            self._consume()
            return self._parse_in_list(lhs, negated=False)

        # Handle: expr NOT IN (...) / expr NOT LIKE pat
        if self._peek_is('KW', 'NOT'):
            next_pos = self._pos + 1
            if next_pos < len(self._tokens):
                next_tok = self._tokens[next_pos]
                if next_tok == ('KW', 'IN'):
                    self._consume()  # consume NOT
                    self._consume()  # consume IN
                    return self._parse_in_list(lhs, negated=True)
                if next_tok == ('KW', 'LIKE'):
                    self._consume()  # consume NOT
                    self._consume()  # consume LIKE
                    pat = self._parse_atom_expr()
                    return f"{lhs} NOT LIKE {pat}"

        # Handle: expr LIKE pattern
        if self._peek_is('KW', 'LIKE'):
            self._consume()
            pat = self._parse_atom_expr()
            return f"{lhs} LIKE {pat}"

        # Handle: expr BETWEEN lo AND hi
        if self._peek_is('KW', 'BETWEEN'):
            self._consume()
            lo = self._parse_atom_expr()
            if not self._peek_is('KW', 'AND'):
                raise SQLTranslationError(
                    "Expected AND in BETWEEN ... AND ... expression"
                )
            self._consume()
            hi = self._parse_atom_expr()
            return f"{lhs} BETWEEN {lo} AND {hi}"

        op_tok = self._peek()
        if op_tok is None or op_tok[0] != 'OP':
            raise SQLTranslationError(
                f"Expected a comparison operator (=, <>, >=, …) after '{lhs}', "
                f"got '{op_tok[1] if op_tok else 'end of input'}'"
            )
        _, sql_op = self._consume()
        if sql_op not in self._SQL_TO_RA_OP:
            raise SQLTranslationError(
                f"Unrecognised comparison operator '{sql_op}'"
            )
        rhs = self._parse_atom_expr()
        return f"{lhs} {self._SQL_TO_RA_OP[sql_op]} {rhs}"

    def _parse_in_list(self, lhs: str, negated: bool) -> str:
        """Parse ``(v1, v2, ...)`` after the IN keyword and emit an RA IN expression.

        Args:
            lhs (str): The left-hand side expression string.
            negated (bool): If ``True``, emit a ``NOT IN`` expression.

        Returns:
            str: RA-compatible IN or NOT IN expression string.

        Raises:
            SQLTranslationError: If the parenthesised value list is malformed.
        """
        if self._peek_tag() != 'OPAR':
            raise SQLTranslationError("Expected '(' after IN")
        self._consume()
        values = [self._parse_atom_expr()]
        while self._peek_tag() == 'COMMA':
            self._consume()
            values.append(self._parse_atom_expr())
        if self._peek_tag() != 'CPAR':
            raise SQLTranslationError("Expected ')' to close IN list")
        self._consume()
        vals_str = ', '.join(values)
        keyword = 'NOT IN' if negated else 'IN'
        return f"{lhs} {keyword} ({vals_str})"

    def _parse_atom_expr(self) -> str:
        # DATE 'xxxx-xx-xx' [+/- INTERVAL 'n' YEAR|MONTH|DAY]
        if self._peek_is('KW', 'DATE'):
            self._consume()
            tag, val = self._consume()
            if tag != 'STR':
                raise SQLTranslationError(
                    f"Expected a string literal after DATE, got '{val}'"
                )
            date_str = val  # e.g. '1994-01-01'
            # Handle optional date arithmetic: + interval '1' year
            while self._peek_tag() in ('PLUS', 'MINUS'):
                op_tag = self._consume()[1]  # '+' or '-'
                if not self._peek_is('KW', 'INTERVAL'):
                    raise SQLTranslationError(
                        f"Expected INTERVAL after '{op_tag}' in date expression"
                    )
                self._consume()  # consume INTERVAL
                amt_tag, amt_val = self._consume()
                if amt_tag == 'STR':
                    amt_val = amt_val.strip("'")
                try:
                    amount = int(amt_val)
                except ValueError:
                    raise SQLTranslationError(
                        f"Expected integer interval amount, got '{amt_val}'"
                    )
                # Unit keyword
                unit_tok = self._peek()
                if unit_tok is None or unit_tok[0] != 'KW' or unit_tok[1] not in ('YEAR', 'MONTH', 'DAY'):
                    raise SQLTranslationError(
                        "Expected YEAR, MONTH, or DAY after interval amount"
                    )
                _, unit = self._consume()
                date_str = _date_add(
                    date_str, amount if op_tag == '+' else -amount, unit
                )
            return date_str  # return as 'YYYY-MM-DD' string literal

        tag, val = self._consume()
        if tag in ('IDENT', 'INT', 'STR'):
            # Check for modulo: IDENT % INT or INT % INT
            if self._peek_tag() == 'MOD':
                self._consume()  # consume %
                rhs_tag, rhs_val = self._consume()
                if rhs_tag not in ('IDENT', 'INT'):
                    raise SQLTranslationError(
                        f"Expected number or column after %, got '{rhs_val}'"
                    )
                return f"{val} % {rhs_val}"
            return val
        raise SQLTranslationError(
            f"Expected a column name or literal value, got '{val}'"
        )


def sql_to_ra(sql: str) -> str:
    """
    Translate a SQL SELECT query into a relational algebra expression string.

    The returned string is compatible with ``src.parser.parse()``.

    Args:
        sql (str): A SQL query using the supported subset (see module docstring).

    Returns:
        str: Relational algebra expression string, e.g.
        ``"δ(π[Name](σ[Dept == 'Eng'](Emp)))"``.

    Raises:
        SQLTranslationError: If the query uses an unsupported SQL construct
            or has a syntax error.
    """
    tokens = _tokenize(sql.strip())
    if not tokens:
        raise SQLTranslationError("Empty SQL query")
    translator = _Translator(tokens)
    return translator.translate()


def sql_to_ra_with_aliases(sql: str) -> Tuple[str, Dict[str, str]]:
    """Translate a SQL query to RA and also return the alias-to-table mapping.

    Like :func:`sql_to_ra` but additionally exposes the alias map built during
    parsing, which is required for self-join queries.

    Args:
        sql (str): A SQL query using the supported subset.

    Returns:
        Tuple[str, Dict[str, str]]: A tuple of ``(ra_expression, alias_map)``
        where ``alias_map`` maps each alias to its real table name.  Only
        aliases that differ from the table name are included
        (e.g. ``{'n1': 'nation', 'n2': 'nation'}``).

    Raises:
        SQLTranslationError: If the query cannot be translated.
    """
    tokens = _tokenize(sql.strip())
    if not tokens:
        raise SQLTranslationError("Empty SQL query")
    translator = _Translator(tokens)
    ra = translator.translate()
    return ra, dict(translator._alias_map)
