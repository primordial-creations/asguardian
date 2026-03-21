from datetime import datetime
from typing import cast

from Asgard.Heimdall.cli.handlers._base import _strip_ansi


_SCAN_TAB_LABELS: dict = {
    "file_length": "File Length",
    "complexity": "Complexity",
    "lazy_imports": "Lazy Imports",
    "env_fallbacks": "Env Fallbacks",
    "type_check": "Type Check",
    "security": "Security",
    "performance": "Performance",
    "oop": "OOP",
    "architecture": "Architecture",
    "dependencies": "Dependencies",
    "test_coverage": "Test Coverage",
}

_SCAN_DISPLAY_NAMES: dict = {
    "file_length": "File Length",
    "complexity": "Complexity",
    "lazy_imports": "Lazy Imports",
    "env_fallbacks": "Env Fallbacks",
    "type_check": "Type Check",
    "security": "Security",
    "performance": "Performance",
    "oop": "Object Oriented Programming",
    "architecture": "Architecture",
    "dependencies": "Dependencies",
    "test_coverage": "Test Coverage",
}

_SCAN_DESCRIPTIONS: dict = {
    "file_length": "Max lines per file threshold",
    "complexity": "Cyclomatic & cognitive complexity of functions",
    "lazy_imports": "Imports inside functions, methods, or blocks",
    "env_fallbacks": "Environment variables with hardcoded fallback values",
    "type_check": "Static type errors detected by mypy",
    "security": "Security vulnerabilities, secrets & misconfigurations",
    "performance": "Performance anti-patterns & inefficient code",
    "oop": "OOP coupling, cohesion & inheritance metrics",
    "architecture": "SOLID principles, layer & hexagonal design",
    "dependencies": "Circular import cycles between modules",
    "test_coverage": "Test coverage gaps across source methods",
}


def _detail_str(category: str, data: dict) -> str:
    status = data.get("status", "?")
    if status == "ERROR":
        return cast(str, data.get("error", "")[:80])
    if category == "type_check":
        return f"{data.get('errors', 0)} errors, {data.get('files_with_errors', 0)} files affected"
    if category == "security":
        return f"{data.get('total_findings', 0)} findings ({data.get('critical', 0)} critical)"
    if category == "file_length":
        rate = data.get("compliance_rate")
        base = f"{data.get('violations', 0)} violations"
        return f"{base} ({rate:.1f}% compliant)" if rate is not None else base
    if category == "test_coverage":
        pct = data.get("method_coverage_percent")
        gaps = data.get("total_gaps", 0)
        return f"{pct:.1f}% method coverage, {gaps} gaps" if pct is not None else f"{gaps} gaps"
    if "violations" in data:
        return f"{data['violations']} violations"
    if "total_findings" in data:
        return f"{data['total_findings']} findings"
    if "circular_imports" in data:
        return f"{data['circular_imports']} cycles"
    return ""


def _generate_scan_html_report(
    scan_results: dict,
    step_reports: dict,
    scan_path: str,
    duration: float,
    scanned_at: datetime,
) -> str:
    pass_count = sum(1 for d in scan_results.values() if d.get("status") == "PASS")
    fail_count = sum(1 for d in scan_results.values() if d.get("status") == "FAIL")
    err_count = sum(1 for d in scan_results.values() if d.get("status") == "ERROR")
    overall = "PASSING" if fail_count == 0 and err_count == 0 else "FAILING"
    overall_color = "#4ec9b0" if overall == "PASSING" else "#f44747"

    rows_html = ""
    for cat, data in scan_results.items():
        status = data.get("status", "?")
        label = _SCAN_DISPLAY_NAMES.get(cat, cat.replace("_", " ").title())
        detail = _detail_str(cat, data)
        desc = _SCAN_DESCRIPTIONS.get(cat, "")
        cls = "pass" if status == "PASS" else ("fail" if status == "FAIL" else "err")
        rows_html += (
            f"<tr>"
            f"<td>{label}</td>"
            f"<td class='{cls}'>{status}</td>"
            f"<td>{detail}</td>"
            f"<td class='desc'>{desc}</td>"
            f"</tr>\n"
        )

    btn_html = '<button class="tab-btn active" onclick="showTab(this,\'overview\')">Overview</button>\n'
    panel_html = ""
    for key, report_text in step_reports.items():
        label = _SCAN_TAB_LABELS.get(key, key.replace("_", " ").title())
        status = scan_results.get(key, {}).get("status", "?")
        dot_cls = "pass" if status == "PASS" else ("fail" if status == "FAIL" else "err")
        escaped = (
            _strip_ansi(report_text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        tid = f"tab_{key}"
        btn_html += (
            f'<button class="tab-btn" onclick="showTab(this,\'{tid}\')">'
            f'<span class="{dot_cls}-dot"></span>{label}</button>\n'
        )
        panel_html += (
            f'<div id="{tid}" class="tab-panel" style="display:none">'
            f"<pre>{escaped}</pre>"
            f"</div>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Heimdall Scan - {scan_path}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#1e1e1e;color:#d4d4d4;font-family:'Cascadia Code','Fira Code',Consolas,monospace;font-size:13px;line-height:1.6;display:flex;flex-direction:column;height:100vh;overflow:hidden}}
    .hdr{{background:#252526;padding:12px 20px;border-bottom:1px solid #333;flex-shrink:0}}
    .hdr h1{{color:#569cd6;font-size:1em;margin-bottom:2px}}
    .hdr .meta{{color:#777;font-size:.85em}}
    .overall{{color:{overall_color};font-weight:bold;margin-left:8px}}
    .tab-bar{{display:flex;background:#2d2d2d;border-bottom:1px solid #333;padding:8px 16px 0;gap:4px;flex-shrink:0;flex-wrap:wrap}}
    .tab-btn{{background:#333;border:1px solid #444;border-bottom:none;color:#ccc;padding:5px 12px;cursor:pointer;font-family:inherit;font-size:12px;border-radius:4px 4px 0 0}}
    .tab-btn:hover{{background:#3e3e3e}}
    .tab-btn.active{{background:#1e1e1e;color:#fff;border-color:#569cd6;border-bottom-color:#1e1e1e}}
    .pass-dot::before{{content:"● ";color:#4ec9b0}}
    .fail-dot::before{{content:"● ";color:#f44747}}
    .err-dot::before{{content:"● ";color:#ff8c00}}
    .tab-content{{flex:1;overflow:auto;padding:20px 24px}}
    .tab-panel{{display:none}}
    .tab-panel pre{{white-space:pre-wrap;word-wrap:break-word}}
    table{{border-collapse:collapse;width:100%;max-width:920px}}
    th,td{{text-align:left;padding:6px 14px;border-bottom:1px solid #333}}
    th{{color:#777;font-weight:normal;font-size:.9em}}
    .desc{{color:#777;font-size:.9em}}
    .pass{{color:#4ec9b0}}
    .fail{{color:#f44747}}
    .err{{color:#ff8c00}}
    .summary{{margin-top:14px;color:#777;font-size:.9em}}
  </style>
</head>
<body>
  <div class="hdr">
    <h1>Heimdall Full Scan <span class="overall">{overall}</span></h1>
    <div class="meta">
      {scan_path} &nbsp;|&nbsp; {scanned_at.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; {duration:.1f}s &nbsp;|&nbsp;
      <span class="pass">{pass_count} passed</span> &nbsp;
      <span class="fail">{fail_count} failed</span> &nbsp;
      <span class="err">{err_count} errors</span>
    </div>
  </div>
  <div class="tab-bar">
    {btn_html}
  </div>
  <div class="tab-content">
    <div id="overview" class="tab-panel" style="display:block">
      <table>
        <thead><tr><th>Category</th><th>Status</th><th>Details</th><th>What It Checks</th></tr></thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
      <div class="summary">
        <span class="pass">{pass_count} passed</span> &nbsp;
        <span class="fail">{fail_count} failed</span> &nbsp;
        <span class="err">{err_count} errors</span> &nbsp;|&nbsp;
        <span class="overall">{overall}</span>
      </div>
    </div>
    {panel_html}
  </div>
  <script>
    function showTab(btn,id){{
      document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p=>p.style.display='none');
      btn.classList.add('active');
      document.getElementById(id).style.display='block';
    }}
  </script>
</body>
</html>"""
