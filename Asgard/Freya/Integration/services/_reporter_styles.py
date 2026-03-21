"""
Freya HTML Reporter styles and scripts.

CSS and JavaScript assets extracted from html_reporter.py.
"""


def get_css() -> str:
    """Get CSS styles for report."""
    return """
        :root {
            --color-primary: #2563eb;
            --color-success: #16a34a;
            --color-warning: #ca8a04;
            --color-error: #dc2626;
            --color-critical: #7c2d12;
            --color-bg: #f8fafc;
            --color-card: #ffffff;
            --color-text: #1e293b;
            --color-muted: #64748b;
            --color-border: #e2e8f0;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--color-bg); color: var(--color-text); line-height: 1.6; }
        header { background: var(--color-primary); color: white; padding: 2rem; }
        header h1 { margin-bottom: 0.5rem; }
        header .meta { display: flex; gap: 2rem; opacity: 0.9; }
        header a { color: white; }
        main { max-width: 1400px; margin: 0 auto; padding: 2rem; }
        section { background: var(--color-card); border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        h2 { margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; }
        .section-score { font-size: 1rem; color: var(--color-muted); }
        .score-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
        .score-card { text-align: center; padding: 1.5rem; background: var(--color-bg); border-radius: 8px; }
        .score-card.overall { background: var(--color-primary); color: white; }
        .score-value { font-size: 2.5rem; font-weight: bold; }
        .score-label { font-size: 0.875rem; opacity: 0.8; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
        .stat-card { text-align: center; padding: 1rem; background: var(--color-bg); border-radius: 8px; }
        .stat-card.passed { border-left: 4px solid var(--color-success); }
        .stat-card.failed { border-left: 4px solid var(--color-error); }
        .stat-value { font-size: 1.5rem; font-weight: bold; }
        .severity-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
        .severity-card { display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem; border-radius: 8px; background: var(--color-bg); }
        .severity-card.critical { border-left: 4px solid var(--color-critical); }
        .severity-card.serious { border-left: 4px solid var(--color-error); }
        .severity-card.moderate { border-left: 4px solid var(--color-warning); }
        .severity-card.minor { border-left: 4px solid var(--color-muted); }
        .severity-card .count { font-weight: bold; font-size: 1.25rem; }
        .results-table { width: 100%; border-collapse: collapse; }
        .results-table th, .results-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--color-border); }
        .results-table th { background: var(--color-bg); font-weight: 600; }
        .severity-badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
        .severity-badge.critical { background: var(--color-critical); color: white; }
        .severity-badge.serious { background: var(--color-error); color: white; }
        .severity-badge.moderate { background: var(--color-warning); color: white; }
        .severity-badge.minor { background: var(--color-muted); color: white; }
        .severity-badge.passed { background: var(--color-success); color: white; }
        .wcag { display: inline-block; padding: 0.125rem 0.375rem; background: var(--color-bg); border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem; }
        code { background: var(--color-bg); padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.875rem; }
        .screenshot-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
        .screenshot-item { border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
        .screenshot-item img { width: 100%; height: auto; }
        .screenshot-label { padding: 0.5rem; background: var(--color-bg); text-align: center; font-size: 0.875rem; }
        footer { text-align: center; padding: 2rem; color: var(--color-muted); }
        @media (max-width: 768px) {
            .score-grid, .stats-grid, .severity-grid { grid-template-columns: repeat(2, 1fr); }
            header .meta { flex-direction: column; gap: 0.5rem; }
            .results-table { display: block; overflow-x: auto; }
        }
        """


def get_javascript() -> str:
    """Get JavaScript for interactivity."""
    return """
        document.addEventListener('DOMContentLoaded', function() {
            const rows = document.querySelectorAll('.result-row');
            rows.forEach(row => {
                row.addEventListener('click', function() {
                    this.classList.toggle('expanded');
                });
            });
        });
        """
