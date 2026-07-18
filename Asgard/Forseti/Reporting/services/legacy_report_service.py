"""
Legacy Report Service - single implementation behind the per-module
`generate_text_report` / `generate_markdown_report` helpers.

Seven Forseti modules used to each hand-roll the same banner-and-sections
report format. The per-module helpers are now thin wrappers over these
two renderers (plan 08 handler/report unification); output stays
byte-identical to the historical formats.
"""

BANNER = "=" * 60
RULE = "-" * 60


def render_legacy_text_report(
    title: str,
    header_lines: list[str],
    sections: list[tuple[str, list[str]]],
    extra_blocks: list[list[str]] | None = None,
) -> str:
    """
    Render the classic text report:

        ============
        <title>
        ============
        <header lines>
        ------------
        [<extra block>\n------------]...
        \n<Section>:\n  items...
        ============
    """
    lines = [BANNER, title, BANNER, *header_lines, RULE]
    for block in extra_blocks or []:
        lines.extend(block)
        lines.append(RULE)
    for section_title, items in sections:
        if items:
            lines.append(f"\n{section_title}:")
            lines.extend(items)
    lines.append(BANNER)
    return "\n".join(lines)


def render_legacy_markdown_report(
    title: str,
    header_lines: list[str],
    sections: list[tuple[str, list[str]]],
) -> str:
    """
    Render the classic markdown report: `# <title>` + header bullets +
    `## <Section>` blocks. Wrappers pass fully formatted lines so
    module-specific layouts (tables vs bullets) are preserved verbatim.
    """
    lines = [f"# {title}\n", *header_lines]
    for index, (section_title, items) in enumerate(sections):
        if items:
            lines.append(("" if index == 0 else "\n") + f"## {section_title}\n")
            lines.extend(items)
    return "\n".join(lines)
