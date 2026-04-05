"""
Tokenizer and recursive-descent parser for relational algebra expressions.

Supported operators
-------------------
σ   Selection          σ[cond](R)
π   Projection         π[a, b](R)
ρ   Rename             ρ(old, new)
δ   Deduplication      δ(R)
ɣ   Grouping           ɣ[attrs][aggrs](R)
×   Cross product      R × S
÷   Division           R ÷ S
⨝   Inner join         R ⨝[cond] S
⟕   Left outer join    R ⟕[cond] S
⊳   Anti join          R ⊳[cond] S
∪   Union              R ∪ S
∩   Intersection       R ∩ S
-   Difference         R - S
"""

from src.parser.grammar import (
    Select, Project, Rename, Dedup, Group, Cross,
    Div, Inner, Outer, Anti, Union, Intersect,
    Minus, Table, And, Or, Not, Comp, Attr, Val,
    Aggr, In, Like, Between, Mod
)


#########################
# Parse
#########################
def parse(expr):
    """
    Parse a relational algebra expression string into an AST.

    Parameters
    ----------
    expr : str
        A relational algebra expression using Unicode operator symbols
        (e.g. ``σ[A == 1](R)``, ``π[A](R × S)``).

    Returns
    -------
    Alg
        The root AST node of the parsed expression.

    Raises
    ------
    Exception
        If the expression contains unknown symbols or is syntactically invalid.
    """
    tokens = tokenizer(expr)
    return parser(tokens)


#########################
# Tokenizer
#########################
NUM = "0123456789"
ALP = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
SYM = "_"
AGG = ('COUNT', 'MAX', 'MIN', 'SUM', 'AVG')


def tokenizer(s):
    """
    Tokenize a relational algebra expression string.

    Parameters
    ----------
    s : str
        Raw expression string.

    Returns
    -------
    list[list]
        A list of tokens.  Each token is a list whose first element is a
        tag string (e.g. ``'SELECT'``, ``'NAME'``, ``'VAL'``) and whose
        optional second element carries the token's payload value.

    Raises
    ------
    Exception
        If an unrecognised symbol is encountered.
    """

    def match(v):
        if idx + len(v) - 1 >= end:
            return False
        elif s[idx:idx + len(v)] == v:
            return True
        else:
            return False

    def isany(vl):
        if idx > len(s):
            return False
        elif s[idx] in vl:
            return True
        else:
            return False

    idx = 0
    end = len(s)
    res = []
    while idx < end:
        if match(' '):
            idx += 1
        elif match('~'):
            res.append(['NOT'])
            idx += 1
        elif match('/\\'):
            res.append(['AND'])
            idx += 2
        elif match('\\/'):
            res.append(['OR'])
            idx += 2
        elif match(','):
            res.append(['COMMA'])
            idx += 1
        elif match('.'):
            res.append(['DOT'])
            idx += 1
        elif match('['):
            res.append(['OSQR'])
            idx += 1
        elif match(']'):
            res.append(['CSQR'])
            idx += 1
        elif match('=='):
            res.append(['EQ'])
            idx += 2
        elif match('!='):
            res.append(['NEQ'])
            idx += 2
        elif match('>='):
            res.append(['GEQ'])
            idx += 2
        elif match('<='):
            res.append(['LEQ'])
            idx += 2
        elif match('>'):
            res.append(['GT'])
            idx += 1
        elif match('<'):
            res.append(['LT'])
            idx += 1
        elif match('('):
            res.append(['OPAR'])
            idx += 1
        elif match(')'):
            res.append(['CPAR'])
            idx += 1
        elif match('%'):
            res.append(['MOD'])
            idx += 1
        elif match('σ'):
            res.append(['SELECT'])
            idx += 1
        elif match('π'):
            res.append(['PROJECT'])
            idx += 1
        elif match('ρ'):
            res.append(['RENAME'])
            idx += 1
        elif match('ɣ'):
            res.append(['GROUP'])
            idx += 1
        elif match('δ'):
            res.append(['DEDUP'])
            idx += 1
        elif match('×'):
            res.append(['CROSS'])
            idx += 1
        elif match('÷'):
            res.append(['DIV'])
            idx += 1
        elif match('⨝'):
            res.append(['INNER'])
            idx += 1
        elif match('⟕'):
            res.append(['OUTER'])
            idx += 1
        elif match('⊳'):
            res.append(['ANTI'])
            idx += 1
        elif match('∪'):
            res.append(['UNION'])
            idx += 1
        elif match('∩'):
            res.append(['INTERSECT'])
            idx += 1
        elif match('-'):
            res.append(['MINUS'])
            idx += 1
        elif match('NULL'):
            res.append(['VAL', None])
            idx += 4
        elif match("'"):
            idx += 1
            val = ''
            while idx < end and not match("'"):
                val += s[idx]
                idx += 1
            res.append(['VAL', val])
            idx += 1
        elif isany(NUM):
            val = ''
            while idx < end and isany(NUM):
                val += s[idx]
                idx += 1
            res.append(['VAL', int(val)])
            continue
        elif isany(ALP + SYM):
            val = ''
            while idx < end and (isany(ALP + SYM) or isany(NUM)):
                val += s[idx]
                idx += 1
            upper = val.upper()
            if upper == 'IN':
                res.append(['IN'])
            elif upper == 'NOT':
                res.append(['KNOT'])
            elif upper == 'LIKE':
                res.append(['LIKE'])
            elif upper == 'BETWEEN':
                res.append(['BETWEEN'])
            elif upper == 'AND':
                res.append(['AND'])
            else:
                res.append(['NAME', val])
            continue
        else:
            raise Exception(f'Unknown symbol {s[idx]}')
    return res


#########################
# Parser
#########################
def parser(tok):
    """
    Convert a token list produced by :func:`tokenizer` into an AST.

    The grammar is a recursive-descent parser organised into the following
    levels (highest to lowest precedence):

    * ``parse_alg``   — binary algebra operators (×, ÷, ⋈, ∪, ∩, -)
    * ``parse_expr``  — unary prefix operators (σ, π, ρ, δ, ɣ) and base cases
    * ``parse_log``   — logical connectives (AND, OR, NOT)
    * ``parse_rel``   — relational comparisons (==, !=, >=, <=, >, <)
    * ``parse_cond``  — atomic terms (VAL literals, NAME attributes, parentheses)
    * ``parse_attrs`` — comma-separated attribute lists
    * ``parse_aggrs`` — comma-separated aggregation lists
    * ``parse_aggr``  — single aggregation expression

    Parameters
    ----------
    tok : list[list]
        Token list produced by :func:`tokenizer`.

    Returns
    -------
    Alg
        Root AST node representing the full expression.

    Raises
    ------
    Exception
        If the token stream does not conform to the grammar.
    """

    def match(tag):
        nonlocal idx
        if idx >= end:
            return False
        elif tok[idx][0] == tag:
            return True
        else:
            return False

    def expect(tag):
        nonlocal idx
        if idx >= end:
            raise Exception(f'Unexpected end of input, expect {tag}')
        elif tok[idx][0] == tag:
            idx += 1
            return True
        else:
            raise Exception(
                f'Unexpected input, expect {tag}, actually {tok[idx]}')

    idx = 0
    end = len(tok)

    cmp = {
        'EQ': '==',
        'NEQ': '!=',
        'GEQ': '>=',
        'LEQ': '<=',
        'GT': '>',
        'LT': '<'
    }

    def parse_alg(tok):  # algebra
        nonlocal idx
        res = parse_expr(tok)
        while idx < end and (match('CROSS') or match('DIV') or match('INNER')
                             or match('OUTER') or match('ANTI')
                             or match('UNION') or match('INTERSECT')
                             or match('MINUS')):
            if match('CROSS'):
                idx += 1
                rhs = parse_expr(tok)
                res = Cross(res, rhs)
            elif match('DIV'):
                idx += 1
                rhs = parse_expr(tok)
                res = Div(res, rhs)
            elif match('INNER'):
                idx += 1
                expect('OSQR')
                cond = parse_log(tok)
                expect('CSQR')
                rhs = parse_expr(tok)
                res = Inner(res, rhs, cond)
            elif match('OUTER'):
                idx += 1
                expect('OSQR')
                cond = parse_log(tok)
                expect('CSQR')
                rhs = parse_expr(tok)
                res = Outer(res, rhs, cond)
            elif match('ANTI'):
                idx += 1
                expect('OSQR')
                cond = parse_log(tok)
                expect('CSQR')
                rhs = parse_expr(tok)
                res = Anti(res, rhs, cond)
            elif match('UNION'):
                idx += 1
                rhs = parse_expr(tok)
                res = Union(res, rhs)
            elif match('INTERSECT'):
                idx += 1
                rhs = parse_expr(tok)
                res = Intersect(res, rhs)
            elif match('MINUS'):
                idx += 1
                rhs = parse_expr(tok)
                res = Minus(res, rhs)
            else:
                raise Exception(
                    f'Unexpected token, expect "algebra", but token is {tok[idx]}'
                )
        return res

    def parse_expr(tok):  # expression
        nonlocal idx
        if match('SELECT'):
            idx += 1
            expect('OSQR')
            cond = parse_log(tok)
            expect('CSQR')
            expect('OPAR')
            rel = parse_alg(tok)
            expect('CPAR')
            return Select(cond, rel)
        elif match('PROJECT'):
            idx += 1
            expect('OSQR')
            attrs = parse_attrs(tok)
            expect('CSQR')
            expect('OPAR')
            rel = parse_alg(tok)
            expect('CPAR')
            return Project(attrs, rel)
        elif match('RENAME'):
            idx += 1
            expect('OPAR')
            if match('NAME'):
                old = tok[idx][1]
                idx += 1
            else:
                raise Exception(
                    f'Unexpected token, expect "old name", but token is {tok[idx]}'
                )
            expect('COMMA')
            if match('NAME'):
                new = tok[idx][1]
                idx += 1
            else:
                raise Exception(
                    f'Unexpected token, expect "new name", but token is {tok[idx]}'
                )
            expect('CPAR')
            return Rename(old, new)
        elif match('DEDUP'):
            idx += 1
            expect('OPAR')
            rel = parse_alg(tok)
            expect('CPAR')
            return Dedup(rel)
        elif match('GROUP'):
            idx += 1
            expect('OSQR')
            attrs = parse_attrs(tok)
            expect('CSQR')
            expect('OSQR')
            aggrs = parse_aggrs(tok)
            expect('CSQR')
            expect('OPAR')
            rel = parse_alg(tok)
            expect('CPAR')
            return Group(attrs, aggrs, rel)
        elif match('OPAR'):
            idx += 1
            rel = parse_alg(tok)
            expect('CPAR')
            return rel
        elif match('NAME'):
            res = Table(tok[idx][1])
            idx += 1
            return res
        else:
            raise Exception(
                f'Unexpected token, expect "expression", but token is {tok[idx]}'
            )

    def parse_log(tok):  # logical
        nonlocal idx
        if match('NOT'):
            idx += 1
            arg = parse_log(tok)
            return Not(arg)
        else:
            res = parse_rel(tok)
            while idx < end and (match('AND') or match('OR')):
                if match('AND'):
                    idx += 1
                    rhs = parse_rel(tok)
                    res = And(res, rhs)
                elif match('OR'):
                    idx += 1
                    rhs = parse_rel(tok)
                    res = Or(res, rhs)
            return res

    def parse_rel(tok):  # relational
        nonlocal idx
        res = parse_cond(tok)
        # Handle IN: expr IN (v1, v2, ...)
        if idx < end and match('IN'):
            idx += 1
            expect('OPAR')
            values = [parse_cond(tok)]
            while idx < end and match('COMMA'):
                idx += 1
                values.append(parse_cond(tok))
            expect('CPAR')
            return In(res, values)
        # Handle NOT IN / NOT LIKE
        if idx < end and match('KNOT'):
            idx += 1
            if match('IN'):
                idx += 1
                expect('OPAR')
                values = [parse_cond(tok)]
                while idx < end and match('COMMA'):
                    idx += 1
                    values.append(parse_cond(tok))
                expect('CPAR')
                return In(res, values, negated=True)
            elif match('LIKE'):
                idx += 1
                pat = parse_cond(tok)
                return Like(res, pat, negated=True)
            else:
                raise Exception(
                    f'Unexpected token after NOT, expect IN or LIKE, got {tok[idx]}'
                )
        # Handle LIKE: expr LIKE pattern
        if idx < end and match('LIKE'):
            idx += 1
            pat = parse_cond(tok)
            return Like(res, pat)
        # Handle BETWEEN: expr BETWEEN lo AND hi
        if idx < end and match('BETWEEN'):
            idx += 1
            lo = parse_cond(tok)
            expect('AND')
            hi = parse_cond(tok)
            return Between(res, lo, hi)
        while idx < end and (match('EQ') or match('NEQ') or match('GEQ')
                             or match('LEQ') or match('GT') or match('LT')):
            op = tok[idx][0]
            idx += 1
            rhs = parse_rel(tok)
            res = Comp(res, cmp[op], rhs)
        return res

    def parse_cond(tok):  # conditional
        nonlocal idx
        if match('VAL'):
            res = Val(tok[idx][1])
            idx += 1
            if idx < end and match('MOD'):
                idx += 1
                rhs = parse_cond(tok)
                res = Mod(res, rhs)
            return res
        elif match('NAME'):
            arg = tok[idx][1]
            idx += 1
            if match('DOT'):
                idx += 1
                arg += '.' + tok[idx][1]
                idx += 1
            res = Attr(arg)
            if idx < end and match('MOD'):
                idx += 1
                rhs = parse_cond(tok)
                res = Mod(res, rhs)
            return res
        elif match('OPAR'):
            idx += 1
            expr = parse_log(tok)
            expect('CPAR')
            return expr
        else:
            raise Exception(
                f'Unexpected token, expect "conditional", but token is {tok[idx]}'
            )

    def parse_attrs(tok):  # list of attributes
        nonlocal idx
        if match('NAME'):
            arg = tok[idx][1]
            idx += 1
            if match('DOT'):
                idx += 1
                arg += '.' + tok[idx][1]
                idx += 1
            res = [arg]
            while idx < end and match('COMMA'):
                idx += 1
                if match('NAME'):
                    arg = tok[idx][1]
                    idx += 1
                    if match('DOT'):
                        idx += 1
                        arg += '.' + tok[idx][1]
                        idx += 1
                    res.append(arg)
                else:
                    raise Exception(
                        f'Unexpected token, expect "attribute", but token is {tok[idx]}'
                    )
            return res
        else:
            raise Exception(
                f'Unexpected token, expect "attribute", but token is {tok[idx]}'
            )

    def parse_aggrs(tok):  # list of aggregation
        nonlocal idx
        res = [parse_aggr(tok)]
        while idx < end and match('COMMA'):
            idx += 1
            res.append(parse_aggr(tok))
        return res

    def parse_aggr(tok):  # a single aggregation
        nonlocal idx
        if match('NAME'):
            func = tok[idx][1]
            if func not in AGG:
                raise Exception(
                    f'Unexpected token, expect "aggregation function", but token is {tok[idx]}'
                )
            idx += 1
            expect('OPAR')
            if match('NAME'):
                attr = tok[idx][1]
                idx += 1
            else:
                raise Exception(
                    f'Unexpected token, expect "attribute", but token is {tok[idx]}'
                )
            expect('CPAR')
            return Aggr(func, attr)
        else:
            raise Exception(
                f'Unexpected token, expect "attribute", but token is {tok[idx]}'
            )

    return parse_alg(tok)
