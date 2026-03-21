"""
Asgard Reporting HTML Templates

Embedded CSS and JavaScript for self-contained HTML reports.
"""

REPORT_CSS = """
:root {
    --color-bg: #1a1a2e;
    --color-surface: #16213e;
    --color-primary: #0f3460;
    --color-accent: #e94560;
    --color-text: #eaeaea;
    --color-text-muted: #a0a0a0;
    --color-success: #4caf50;
    --color-warning: #ff9800;
    --color-error: #f44336;
    --color-info: #2196f3;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: var(--color-bg);
    color: var(--color-text);
    line-height: 1.6;
    padding: 20px;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
}

header {
    background: linear-gradient(135deg, var(--color-primary), var(--color-surface));
    padding: 30px;
    border-radius: 12px;
    margin-bottom: 30px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}

header h1 {
    font-size: 2.5em;
    margin-bottom: 10px;
}

header .meta {
    color: var(--color-text-muted);
    font-size: 0.9em;
}

.dashboard {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.card {
    background: var(--color-surface);
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.card h2 {
    font-size: 1.1em;
    color: var(--color-text-muted);
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.card .score {
    font-size: 3em;
    font-weight: 700;
}

.card .score.good { color: var(--color-success); }
.card .score.warning { color: var(--color-warning); }
.card .score.bad { color: var(--color-error); }

.card .label {
    color: var(--color-text-muted);
    font-size: 0.85em;
    margin-top: 5px;
}

.section {
    background: var(--color-surface);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.section h2 {
    font-size: 1.4em;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--color-primary);
}

table {
    width: 100%;
    border-collapse: collapse;
}

th, td {
    padding: 12px 15px;
    text-align: left;
    border-bottom: 1px solid var(--color-primary);
}

th {
    background: var(--color-primary);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.85em;
    letter-spacing: 0.5px;
}

tr:hover {
    background: rgba(255,255,255,0.05);
}

.severity-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.8em;
    font-weight: 600;
    text-transform: uppercase;
}

.severity-critical { background: #c62828; color: white; }
.severity-high { background: var(--color-error); color: white; }
.severity-medium, .severity-warning { background: var(--color-warning); color: black; }
.severity-low { background: var(--color-info); color: white; }
.severity-info { background: #607d8b; color: white; }

.code-block {
    background: #0d1117;
    border-radius: 8px;
    padding: 15px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.9em;
    overflow-x: auto;
    margin: 10px 0;
}

.code-block .line-number {
    color: var(--color-text-muted);
    margin-right: 15px;
    user-select: none;
}

.code-block .highlight {
    background: rgba(233, 69, 96, 0.3);
    border-left: 3px solid var(--color-accent);
    display: block;
    margin: 0 -15px;
    padding: 0 12px;
}

.progress-bar {
    height: 8px;
    background: var(--color-primary);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 10px;
}

.progress-bar .fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}

.progress-bar .fill.good { background: var(--color-success); }
.progress-bar .fill.warning { background: var(--color-warning); }
.progress-bar .fill.bad { background: var(--color-error); }

.file-list {
    list-style: none;
}

.file-list li {
    padding: 10px 15px;
    border-bottom: 1px solid var(--color-primary);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.file-list li:hover {
    background: rgba(255,255,255,0.05);
}

.file-path {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.9em;
}

.badge-count {
    background: var(--color-accent);
    color: white;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.85em;
    font-weight: 600;
}

.collapsible {
    cursor: pointer;
}

.collapsible::after {
    content: ' [+]';
    color: var(--color-text-muted);
}

.collapsible.active::after {
    content: ' [-]';
}

.collapse-content {
    display: none;
    padding: 15px;
    background: rgba(0,0,0,0.2);
    border-radius: 8px;
    margin-top: 10px;
}

.collapse-content.show {
    display: block;
}

footer {
    text-align: center;
    padding: 20px;
    color: var(--color-text-muted);
    font-size: 0.85em;
}
"""

REPORT_JS = """
document.addEventListener('DOMContentLoaded', function() {
    // Collapsible sections
    document.querySelectorAll('.collapsible').forEach(function(elem) {
        elem.addEventListener('click', function() {
            this.classList.toggle('active');
            var content = this.nextElementSibling;
            if (content && content.classList.contains('collapse-content')) {
                content.classList.toggle('show');
            }
        });
    });
});
"""
