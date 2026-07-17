"""Benchmark fixture — python.yaml-unsafe-load (not imported; scanned as text)."""
import yaml


def unsafe(stream):
    cfg = yaml.load(stream)  # ruleid: python.yaml-unsafe-load
    dangerous = yaml.load(stream, Loader=yaml.UnsafeLoader)  # ruleid: python.yaml-unsafe-load
    return cfg, dangerous


def safe(stream):
    a = yaml.load(stream, Loader=yaml.SafeLoader)
    b = yaml.safe_load(stream)
    c = yaml.load(  # ok: python.yaml-unsafe-load
        stream,
        Loader=yaml.SafeLoader,
    )
    note = "yaml.load(x) needs an explicit Loader"  # ok: python.yaml-unsafe-load
    return a, b, c, note
