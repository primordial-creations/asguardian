"""Benchmark fixture — python.eval-exec-usage (not imported; scanned as text)."""
import ast


def dynamic(user_expr, code, model, batch):
    eval(user_expr)  # ruleid: python.eval-exec-usage
    exec(code)  # ruleid: python.eval-exec-usage
    return eval("1 + 1")  # ruleid: python.eval-exec-usage


def safe(model, batch):
    text = "never call eval(payload) in prod"  # ok: python.eval-exec-usage
    doc = 'exec(cmd) is dangerous'  # ok: python.eval-exec-usage
    value = ast.literal_eval("[1, 2]")
    result = model.eval(batch)
    return text, doc, value, result
