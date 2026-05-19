import re
# Nested quantifiers - exponential
p = re.compile(r"(a|aa)+")
p.search(text)
