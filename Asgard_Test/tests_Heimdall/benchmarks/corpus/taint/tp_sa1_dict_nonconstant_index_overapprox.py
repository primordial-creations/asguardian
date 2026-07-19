"""SA1 sound over-approximation: the index is NON-constant (`key`, a
runtime variable) at the WRITE site, so the whole container must stay
tainted -- reading a different literal key afterwards still flags. Never
mute: an unresolved index is never treated as "safe"."""


def handler(key):
    m = {}
    m[key] = request.args["q"]
    cursor.execute(m["unrelated"])
