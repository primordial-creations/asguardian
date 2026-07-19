"""FP sibling of tp_dynamic_getattr_dispatch_construct.py: a
statically-constant attribute name (`getattr(handlers, "create")(...)`) is
ordinary, decidable code -- must NOT flag."""


def run():
    getattr(handlers, "create")()
