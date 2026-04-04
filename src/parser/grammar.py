# DO NOT MODIFY THE FILE

from Operations import *

#########################
# Algebra
#########################
class Alg():
  def __str__(self):
    return self.__repr__()

class Select(Alg):
  def __init__(self, cond, rel):
    self.cond = cond
    self.rel = rel
  def eval(self):
    return select(self.cond, self.rel.eval())
  def __repr__(self):
    return f'σ[{self.cond}]({self.rel})'

class Project(Alg):
  def __init__(self, attrs, rel):
    self.attrs = attrs
    self.rel = rel
  def eval(self):
    return project(self.attrs, self.rel.eval())
  def __repr__(self):
    return f'π[{", ".join(map(str, self.attrs))}]({self.rel})'

class Rename(Alg):
  def __init__(self, old, new):
    self.old = Table(old)
    self.new = new
  def eval(self):
    return rename(self.old.eval(), self.new)
  def __repr__(self):
    return f'ρ({self.old}, {self.new})'

class Dedup(Alg):
  def __init__(self, rel):
    self.rel = rel
  def eval(self):
    return dedup(self.rel.eval())
  def __repr__(self):
    return f'δ({self.rel})'

class Group(Alg):
  def __init__(self, attrs, aggrs, rel):
    self.attrs = attrs
    self.aggrs = aggrs
    self.rel = rel
  def eval(self):
    return group(self.attrs, self.aggrs, self.rel.eval())
  def __repr__(self):
    return f'ɣ[{", ".join(map(str, self.attrs))}][{", ".join(map(str, self.aggrs))}]({self.rel})'

class Cross(Alg):
  def __init__(self, lhs, rhs):
    self.lhs = lhs
    self.rhs = rhs
  def eval(self):
    return cross(self.lhs.eval(), self.rhs.eval())
  def __repr__(self):
    return f'{self.lhs} × {self.rhs}'

# DO NOT MODIFY
class Div(Alg):
  def __init__(self, lhs, rhs):
    self.lhs = lhs
    self.rhs = rhs
  def eval(self):
    return op_div(self.lhs.eval(), self.rhs.eval())
  def __repr__(self):
    return f'{self.lhs} ÷ {self.rhs}'

class Inner(Alg):
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
  def __init__(self, lhs, rhs, cond):
    self.lhs = lhs
    self.rhs = rhs
    self.cond = cond
  def eval(self):
    lhs = self.lhs.eval()
    rhs = self.rhs.eval()
    # Implement Outer as Inner + Anti + Union
    return union(select(self.cond, cross(lhs, rhs)), op_anti(lhs, rhs, self.cond))
  def __repr__(self):
    return f'{self.lhs} ⟕[{self.cond}] {self.rhs}'

# DO NOT MODIFY
class Anti(Alg):
  def __init__(self, lhs, rhs, cond):
    self.lhs = lhs
    self.rhs = rhs
    self.cond = cond
  def eval(self):
    return op_anti(self.lhs.eval(), self.rhs.eval(), self.cond)
  def __repr__(self):
    return f'{self.lhs} ⊳[{self.cond}] {self.rhs}'

class Union(Alg):
  def __init__(self, lhs, rhs):
    self.lhs = lhs
    self.rhs = rhs
  def eval(self):
    return union(self.lhs.eval(), self.rhs.eval())
  def __repr__(self):
    return f'{self.lhs} ∪ {self.rhs}'

class Intersect(Alg):
  def __init__(self, lhs, rhs):
    self.lhs = lhs
    self.rhs = rhs
  def eval(self):
    return intersect(self.lhs.eval(), self.rhs.eval())
  def __repr__(self):
    return f'{self.lhs} ∩ {self.rhs}'

class Minus(Alg):
  def __init__(self, lhs, rhs):
    self.lhs = lhs
    self.rhs = rhs
  def eval(self):
    return minus(self.lhs.eval(), self.rhs.eval())
  def __repr__(self):
    return f'{self.lhs} - {self.rhs}'

class Table(Alg):
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
  def eval(self, row, attr):
    return False

# lhs & rhs
class And(Cond):
  def __init__(self, lhs, rhs):
    self.lhs = lhs
    self.rhs = rhs
  def eval(self, row, attr):
    return self.lhs.eval(row, attr) and self.rhs.eval(row, attr)
  def __repr__(self):
    return f'({self.lhs} /\\ {self.rhs})'

# lhs | rhs
class Or(Cond):
  def __init__(self, lhs, rhs):
    self.lhs = lhs
    self.rhs = rhs
  def eval(self, row, attr):
    return self.lhs.eval(row, attr) or self.rhs.eval(row, attr)
  def __repr__(self):
    return f'({self.lhs} \\/ {self.rhs})'

# ~arg
class Not(Cond):
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
  '>' : lambda x, y: x >  y if x != None and y != None else False,
  '<' : lambda x, y: x <  y if x != None and y != None else False,
}
class Comp(Cond):
  def __init__(self, lhs, op, rhs):
    self.lhs = lhs
    self.op  = op
    self.rhs = rhs
  def eval(self, row, attr):
    return _COMP[self.op](self.lhs.eval(row, attr), self.rhs.eval(row, attr))
  def __repr__(self):
    return f'({self.lhs} {self.op} {self.rhs})'



#########################
# Atom
#########################
class Atom():
  def eval(self, row, attr):
    return None
  def __str__(self):
    return self.__repr__()
  
class Attr(Atom):
  def __init__(self, attr):
    self.attr = attr
  def eval(self, row, attr):
    return row[find(attr, self.attr)]
  def __repr__(self):
    return self.attr
  
class Val(Atom):
  def __init__(self, val):
    self.val = val
  def eval(self, row, attr):
    return self.val
  def __repr__(self):
    return f'{self.val}' if type(self.val) == int else f"'{self.val}'"



#########################
# Aggregation
#########################
class Aggr():
  def __init__(self, func, attr):
    self.func = func
    self.attr = attr
  def eval(self, row, attr):
    return row[find(attr, self.attr)]
  def __repr__(self):
    return f'{self.func}({self.attr})'
