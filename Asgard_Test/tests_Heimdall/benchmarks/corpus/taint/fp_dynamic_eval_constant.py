"""FP sibling of tp_dynamic_eval_construct.py: a statically-constant
argument (`eval("1+1")`) must NOT flag."""


def run():
    eval("1+1")
