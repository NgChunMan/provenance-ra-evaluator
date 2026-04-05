"""
AST node classes for the relational algebra parser.

Organised into three groups:

* Algebra nodes (subclasses of :class:`Alg`) — relational operators:
  Select, Project, Rename, Dedup, Group, Cross, Div, Inner, Outer, Anti,
  Union, Intersect, Minus, Table.
* Condition nodes (subclasses of :class:`Cond`) — boolean predicates:
  And, Or, Not, Comp.
* Atom nodes (subclasses of :class:`Atom`) — values inside predicates:
  Attr (column reference), Val (literal).
* Aggregation nodes: Aggr.
"""


#########################
# Algebra
#########################
class Alg():
    """Abstract base class for all relational algebra operator nodes."""

    def __str__(self):
        return self.__repr__()


class Select(Alg):
    """Selection operator σ[cond](rel): retains only rows satisfying *cond*."""

    def __init__(self, cond, rel):
        self.cond = cond
        self.rel = rel

    def eval(self):
        return select(self.cond, self.rel.eval())

    def __repr__(self):
        return f'σ[{self.cond}]({self.rel})'


class Project(Alg):
    """Projection operator π[attrs](rel): keeps only the listed columns."""

    def __init__(self, attrs, rel):
        self.attrs = attrs
        self.rel = rel

    def eval(self):
        return project(self.attrs, self.rel.eval())

    def __repr__(self):
        return f'π[{", ".join(map(str, self.attrs))}]({self.rel})'


class Rename(Alg):
    """Rename operator ρ(old, new): renames a relation."""

    def __init__(self, old, new):
        self.old = Table(old)
        self.new = new

    def eval(self):
        return rename(self.old.eval(), self.new)

    def __repr__(self):
        return f'ρ({self.old}, {self.new})'


class Dedup(Alg):
    """Deduplication operator δ(rel): collapses duplicate rows."""

    def __init__(self, rel):
        self.rel = rel

    def eval(self):
        return dedup(self.rel.eval())

    def __repr__(self):
        return f'δ({self.rel})'


class Group(Alg):
    """Grouping operator ɣ[attrs][aggrs](rel): groups rows and applies aggregations."""

    def __init__(self, attrs, aggrs, rel):
        self.attrs = attrs
        self.aggrs = aggrs
        self.rel = rel

    def eval(self):
        return group(self.attrs, self.aggrs, self.rel.eval())

    def __repr__(self):
        return f'ɣ[{", ".join(map(str, self.attrs))}][{", ".join(map(str, self.aggrs))}]({self.rel})'


class Cross(Alg):
    """Cross product R × S: cartesian product of two relations."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self):
        return cross(self.lhs.eval(), self.rhs.eval())

    def __repr__(self):
        return f'{self.lhs} × {self.rhs}'


class Div(Alg):
    """Division operator R ÷ S."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self):
        return op_div(self.lhs.eval(), self.rhs.eval())

    def __repr__(self):
        return f'{self.lhs} ÷ {self.rhs}'


class Inner(Alg):
    """Inner join R ⨝[cond] S: implemented as Cross followed by Select."""

    def __init__(self, lhs, rhs, cond):
        self.lhs = lhs
        self.rhs = rhs
        self.cond = cond

    def eval(self):
        # Implement Inner as Cross + Select
        return select(self.cond, cross(self.lhs.eval(), self.rhs.eval()))

    def __repr__(self):
        return f'{self.lhs} ⨝[{self.cond}] {self.rhs}'


class Outer(Alg):
    """Left outer join R ⟕[cond] S: implemented as Inner ∪ Anti."""

    def __init__(self, lhs, rhs, cond):
        self.lhs = lhs
        self.rhs = rhs
        self.cond = cond

    def eval(self):
        lhs = self.lhs.eval()
        rhs = self.rhs.eval()
        # Implement Outer as Inner + Anti + Union
        return union(select(self.cond, cross(lhs, rhs)),
                     op_anti(lhs, rhs, self.cond))

    def __repr__(self):
        return f'{self.lhs} ⟕[{self.cond}] {self.rhs}'


class Anti(Alg):
    """Anti join R ⊳[cond] S: rows in R with no matching row in S."""

    def __init__(self, lhs, rhs, cond):
        self.lhs = lhs
        self.rhs = rhs
        self.cond = cond

    def eval(self):
        return op_anti(self.lhs.eval(), self.rhs.eval(), self.cond)

    def __repr__(self):
        return f'{self.lhs} ⊳[{self.cond}] {self.rhs}'


class Union(Alg):
    """Union R ∪ S: multiset union of two relations."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self):
        return union(self.lhs.eval(), self.rhs.eval())

    def __repr__(self):
        return f'{self.lhs} ∪ {self.rhs}'


class Intersect(Alg):
    """Intersection R ∩ S: rows present in both relations."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self):
        return intersect(self.lhs.eval(), self.rhs.eval())

    def __repr__(self):
        return f'{self.lhs} ∩ {self.rhs}'


class Minus(Alg):
    """Set difference R - S: rows in R that are not in S."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self):
        return minus(self.lhs.eval(), self.rhs.eval())

    def __repr__(self):
        return f'{self.lhs} - {self.rhs}'


class Table(Alg):
    """Leaf node representing a named base relation."""

    def __init__(self, name):
        self.name = name

    def eval(self):
        return Tbl(self.name)

    def __repr__(self):
        return f'{self.name}'


#########################
# Conditions
#########################
class Cond():
    """Abstract base class for boolean condition nodes used in selections."""

    def eval(self, row, attr):
        return False


# lhs & rhs
class And(Cond):
    """Conjunction (lhs /\\ rhs): true when both sub-conditions hold."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self, row, attr):
        return self.lhs.eval(row, attr) and self.rhs.eval(row, attr)

    def __repr__(self):
        return f'({self.lhs} /\\ {self.rhs})'


# lhs | rhs
class Or(Cond):
    """Disjunction (lhs \\/ rhs): true when either sub-condition holds."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self, row, attr):
        return self.lhs.eval(row, attr) or self.rhs.eval(row, attr)

    def __repr__(self):
        return f'({self.lhs} \\/ {self.rhs})'


# ~arg
class Not(Cond):
    """Negation (~arg): true when the inner condition does not hold."""

    def __init__(self, arg):
        self.arg = arg

    def eval(self, row, attr):
        return not self.arg.eval(row, attr)

    def __repr__(self):
        return f'(~{self.arg})'


# lhs $ rhs
_COMP = {
    '==': lambda x, y: x == y if x != None and y != None else False,
    '!=': lambda x, y: x != y if x != None and y != None else False,
    '>=': lambda x, y: x >= y if x != None and y != None else False,
    '<=': lambda x, y: x <= y if x != None and y != None else False,
    '>': lambda x, y: x > y if x != None and y != None else False,
    '<': lambda x, y: x < y if x != None and y != None else False,
    '%': lambda x, y: x % y if x != None and y != None else None,
}


class Comp(Cond):
    """Comparison (lhs op rhs) where op ∈ {==, !=, >=, <=, >, <}."""

    def __init__(self, lhs, op, rhs):
        self.lhs = lhs
        self.op = op
        self.rhs = rhs

    def eval(self, row, attr):
        return _COMP[self.op](self.lhs.eval(row, attr),
                              self.rhs.eval(row, attr))

    def __repr__(self):
        return f'({self.lhs} {self.op} {self.rhs})'


#########################
# Atom
#########################
class Atom():
    """Abstract base class for atomic expression nodes used inside conditions."""

    def eval(self, row, attr):
        return None

    def __str__(self):
        return self.__repr__()


class Attr(Atom):
    """Column reference: evaluates to the value of the named column in a row."""

    def __init__(self, attr):
        self.attr = attr

    def eval(self, row, attr):
        return row[find(attr, self.attr)]

    def __repr__(self):
        return self.attr


class Val(Atom):
    """Literal value: evaluates to a constant regardless of the row."""

    def __init__(self, val):
        self.val = val

    def eval(self, row, attr):
        return self.val

    def __repr__(self):
        return f'{self.val}' if type(self.val) == int else f"'{self.val}'"


class In(Cond):
    """Membership test (lhs IN (v1, v2, ...)): true when lhs is in the value list."""

    def __init__(self, lhs, values, negated=False):
        self.lhs = lhs
        self.values = values
        self.negated = negated

    def eval(self, row, attr):
        result = self.lhs.eval(row, attr) in [v.eval(row, attr) for v in self.values]
        return not result if self.negated else result

    def __repr__(self):
        vals = ', '.join(str(v) for v in self.values)
        if self.negated:
            return f'({self.lhs} NOT IN ({vals}))'
        return f'({self.lhs} IN ({vals}))'


class Like(Cond):
    """Pattern match (lhs LIKE pattern): SQL LIKE with % and _ wildcards."""

    def __init__(self, lhs, pattern, negated=False):
        self.lhs = lhs
        self.pattern = pattern
        self.negated = negated

    def eval(self, row, attr):
        import re
        val = self.lhs.eval(row, attr)
        pat = self.pattern.eval(row, attr)
        if val is None or pat is None:
            return False
        # Convert SQL LIKE pattern to regex: % -> .*, _ -> ., escape rest
        regex = '^' + re.escape(str(pat)).replace(r'\%', '.*').replace(r'\_', '.') + '$'
        # re.escape escapes % as \% and _ as \_
        regex = regex.replace(r'\%', '.*').replace(r'\_', '.')
        result = bool(re.match(regex, str(val)))
        return not result if self.negated else result

    def __repr__(self):
        if self.negated:
            return f'({self.lhs} NOT LIKE {self.pattern})'
        return f'({self.lhs} LIKE {self.pattern})'


class Between(Cond):
    """Range test (lhs BETWEEN lo AND hi): sugar for lhs >= lo AND lhs <= hi."""

    def __init__(self, lhs, lo, hi):
        self.lhs = lhs
        self.lo = lo
        self.hi = hi

    def eval(self, row, attr):
        val = self.lhs.eval(row, attr)
        lo = self.lo.eval(row, attr)
        hi = self.hi.eval(row, attr)
        if val is None or lo is None or hi is None:
            return False
        return lo <= val <= hi

    def __repr__(self):
        return f'({self.lhs} BETWEEN {self.lo} AND {self.hi})'


class Mod(Atom):
    """Modulo expression (lhs % rhs): evaluates to the remainder."""

    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def eval(self, row, attr):
        l = self.lhs.eval(row, attr)
        r = self.rhs.eval(row, attr)
        if l is None or r is None:
            return None
        return l % r

    def __repr__(self):
        return f'{self.lhs} % {self.rhs}'


#########################
# Aggregation
#########################
class Aggr():
    """Aggregation expression FUNC(attr), e.g. COUNT(x) or SUM(y)."""

    def __init__(self, func, attr):
        self.func = func
        self.attr = attr

    def eval(self, row, attr):
        return row[find(attr, self.attr)]

    def __repr__(self):
        return f'{self.func}({self.attr})'
