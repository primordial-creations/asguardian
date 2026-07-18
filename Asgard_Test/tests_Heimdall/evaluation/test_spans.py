"""AST bounding-box matching (plan 10 s2)."""

from Asgard.Heimdall.evaluation.spans import ASTSpan, spans_overlap


def test_contains_line_inside_span():
    span = ASTSpan(file_path="a.py", start_line=10, end_line=20)
    assert span.contains_line(10)
    assert span.contains_line(15)
    assert span.contains_line(20)
    assert not span.contains_line(9)
    assert not span.contains_line(21)


def test_spans_overlap_exact():
    span = ASTSpan(file_path="a.py", start_line=10, end_line=20)
    assert spans_overlap(span, "a.py", 15)
    assert not spans_overlap(span, "b.py", 15)


def test_spans_overlap_fallback_tolerance():
    span = ASTSpan(file_path="a.py", start_line=10, end_line=20)
    # within default fallback of 3
    assert spans_overlap(span, "a.py", 22)
    assert spans_overlap(span, "a.py", 7)
    # outside fallback
    assert not spans_overlap(span, "a.py", 25)
    assert not spans_overlap(span, "a.py", 3)


def test_spans_overlap_custom_fallback():
    span = ASTSpan(file_path="a.py", start_line=10, end_line=10)
    assert spans_overlap(span, "a.py", 10 + 5, fallback=5)
    assert not spans_overlap(span, "a.py", 10 + 6, fallback=5)


def test_distance_to_line():
    span = ASTSpan(file_path="a.py", start_line=10, end_line=20)
    assert span.distance_to_line(15) == 0
    assert span.distance_to_line(9) == 1
    assert span.distance_to_line(23) == 3


def test_span_normalizes_inverted_range():
    span = ASTSpan(file_path="a.py", start_line=20, end_line=10)
    assert span.end_line == 20
