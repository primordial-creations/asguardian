def format_seo_text(result) -> str:
    """Format SEO report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA SEO REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  SEO Score:        {result.score:.0f}/100")
    lines.append("")

    if result.title:
        lines.append("-" * 70)
        lines.append("  TITLE")
        lines.append("-" * 70)
        lines.append(f"    Present: {'Yes' if result.title.is_present else 'No'}")
        if result.title.value:
            lines.append(f"    Value: {result.title.value[:60]}...")
            lines.append(f"    Length: {result.title.length} chars")
        for issue in result.title.issues:
            lines.append(f"    Issue: {issue}")

    if result.description:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  DESCRIPTION")
        lines.append("-" * 70)
        lines.append(f"    Present: {'Yes' if result.description.is_present else 'No'}")
        if result.description.value:
            lines.append(f"    Value: {result.description.value[:60]}...")
            lines.append(f"    Length: {result.description.length} chars")
        for issue in result.description.issues:
            lines.append(f"    Issue: {issue}")

    if result.missing_required:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  MISSING REQUIRED")
        lines.append("-" * 70)
        for tag in result.missing_required:
            lines.append(f"    - {tag}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_meta_text(result) -> str:
    """Format meta tag report as text."""
    return format_seo_text(result)


def format_structured_data_text(result) -> str:
    """Format structured data report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA STRUCTURED DATA REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Items:      {result.total_items}")
    lines.append(f"  Valid:            {result.valid_items}")
    lines.append(f"  Invalid:          {result.invalid_items}")
    lines.append("")

    if result.schema_types:
        lines.append("-" * 70)
        lines.append("  SCHEMA TYPES FOUND")
        lines.append("-" * 70)
        for schema_type in result.schema_types:
            lines.append(f"    - {schema_type}")
        lines.append("")

    if result.errors:
        lines.append("-" * 70)
        lines.append("  ERRORS")
        lines.append("-" * 70)
        for error in result.errors:
            lines.append(f"    - {error}")
        lines.append("")

    if result.warnings:
        lines.append("-" * 70)
        lines.append("  WARNINGS")
        lines.append("-" * 70)
        for warning in result.warnings:
            lines.append(f"    - {warning}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_robots_text(robots_result, sitemap_result) -> str:
    """Format robots and sitemap report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA ROBOTS/SITEMAP REPORT")
    lines.append("=" * 70)
    lines.append("")

    lines.append("-" * 70)
    lines.append("  ROBOTS.TXT")
    lines.append("-" * 70)
    lines.append(f"    Exists: {'Yes' if robots_result.exists else 'No'}")
    if robots_result.exists:
        lines.append(f"    User-Agents: {', '.join(robots_result.user_agents[:5])}")
        lines.append(f"    Disallow Rules: {len(robots_result.disallow_directives)}")
        lines.append(f"    Sitemaps: {len(robots_result.sitemap_urls)}")

    for issue in robots_result.issues:
        lines.append(f"    Issue: {issue}")

    lines.append("")
    lines.append("-" * 70)
    lines.append("  SITEMAP")
    lines.append("-" * 70)
    lines.append(f"    Exists: {'Yes' if sitemap_result.exists else 'No'}")
    if sitemap_result.exists:
        lines.append(f"    Valid XML: {'Yes' if sitemap_result.is_valid_xml else 'No'}")
        lines.append(f"    Total URLs: {sitemap_result.total_urls}")

    for issue in sitemap_result.issues:
        lines.append(f"    Issue: {issue}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
