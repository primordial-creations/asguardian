"""
AST bounding-box representation and spatial matching (plan 10 s2).

Ground truth is defined by the AST node span the fix/vulnerability
touches, not a single line number, so a report matches if its line falls
within that span; a small fallback tolerance absorbs off-by-a-few line
drift between the scanner's reported line and the annotated node
boundaries (e.g. decorator lines, multi-line call arguments).
"""

from dataclasses import dataclass

DEFAULT_LINE_FALLBACK = 3


@dataclass(frozen=True)
class ASTSpan:
    """A bounding box for an AST node: file + inclusive line range."""

    file_path: str
    start_line: int
    end_line: int
    start_col: int = 0
    end_col: int = 0

    def __post_init__(self) -> None:
        if self.end_line < self.start_line:
            object.__setattr__(self, "end_line", self.start_line)

    def contains_line(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line

    def distance_to_line(self, line: int) -> int:
        """0 if inside the span, else the number of lines to the nearest edge."""
        if self.contains_line(line):
            return 0
        return min(abs(line - self.start_line), abs(line - self.end_line))


def spans_overlap(
    span: ASTSpan,
    file_path: str,
    line: int,
    fallback: int = DEFAULT_LINE_FALLBACK,
) -> bool:
    """True if ``(file_path, line)`` matches ``span`` within tolerance.

    Exact containment always matches; otherwise the fallback allows a
    match within ``fallback`` lines of either span edge (default: 3, per
    plan 10 s2 "fallback ±3 lines").
    """
    if span.file_path != file_path:
        return False
    return span.distance_to_line(line) <= fallback
