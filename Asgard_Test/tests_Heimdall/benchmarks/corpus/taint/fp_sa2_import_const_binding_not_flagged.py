"""SA2 constant/string propagation: `__import__(mod)` where `mod` is a
Name bound to a plain string literal earlier in the same straight-line
scope is constant-foldable -- a resolved, ordinary import, NOT a
dynamic-construct finding."""


def handler():
    mod = "os"
    return __import__(mod)
