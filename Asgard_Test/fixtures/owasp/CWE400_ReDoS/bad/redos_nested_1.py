import re
# Catastrophic backtracking: nested quantifiers
pattern = re.compile(r"(a+)+")
result = pattern.match(input_str)
