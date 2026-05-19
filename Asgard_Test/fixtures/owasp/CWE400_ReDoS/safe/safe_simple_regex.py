import re
# Safe: no nested quantifiers
p = re.compile(r"^\d{4}-\d{2}-\d{2}$")
result = p.match(date_str)
