import re
# Overlapping alternation with quantifier
pat = re.compile(r"(foo|foobar)+")
pat.match(s)
