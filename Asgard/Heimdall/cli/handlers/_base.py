import io
import os
import re
import shutil
import subprocess
import sys
import uuid
import webbrowser
from pathlib import Path
from typing import Callable, cast

from Asgard.Heimdall.Quality.models.analysis_models import SeverityLevel


_handlers_loaded = False
_handler_functions: dict[str, Callable] = {}


def _load_handlers():
    global _handlers_loaded, _handler_functions
    if _handlers_loaded:
        return
    _handlers_loaded = True


def _create_handler(func_name: str, analysis_func):
    def wrapper(*args, **kwargs):
        return analysis_func(*args, **kwargs)
    wrapper.__name__ = func_name
    return wrapper


class _TeeStream:
    def __init__(self, primary, secondary: io.StringIO) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> int:
        self._primary.write(s)
        self._secondary.write(s)
        return len(s)

    def flush(self) -> None:
        self._primary.flush()

    def reconfigure(self, **kwargs) -> None:
        if hasattr(self._primary, "reconfigure"):
            self._primary.reconfigure(**kwargs)

    def fileno(self) -> int:
        return cast(int, self._primary.fileno())

    @property
    def encoding(self) -> str:
        return getattr(self._primary, "encoding", "utf-8")


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _report_file_path(suffix: str = ".html") -> Path:
    return Path.cwd() / f"heimdall_report_{uuid.uuid4().hex[:8]}{suffix}"


def _save_html_report(content: str, title: str = "Heimdall Report") -> Path:
    is_html = content.lstrip().startswith(("<!DOCTYPE", "<html", "<!doctype"))
    if is_html:
        html = content
    else:
        clean = _strip_ansi(content)
        escaped = (
            clean
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{
      background: #1e1e1e;
      color: #d4d4d4;
      font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
      margin: 0;
      padding: 24px;
      font-size: 13px;
      line-height: 1.6;
    }}
    h1 {{
      color: #569cd6;
      font-size: 1.1em;
      margin: 0 0 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid #333;
    }}
    pre {{
      white-space: pre-wrap;
      word-wrap: break-word;
      margin: 0;
    }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <pre>{escaped}</pre>
</body>
</html>"""

    report_path = _report_file_path()
    report_path.write_text(html, encoding="utf-8")
    return report_path


def _open_in_browser(report_path: Path) -> None:
    if sys.platform == "darwin":
        opener = "open"
    elif sys.platform == "win32":
        opener = None
    else:
        opener = shutil.which("xdg-open")

    opened = False
    if opener:
        try:
            subprocess.Popen(
                [opener, str(report_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            opened = True
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            os.startfile(str(report_path))
            opened = True
        except Exception:
            pass

    if not opened:
        webbrowser.open(str(report_path))


def open_output_in_browser(content: str, title: str = "Heimdall Report") -> None:
    report_path = _save_html_report(content, title)
    _open_in_browser(report_path)
    print(f"Report saved: {report_path}", file=sys.__stdout__)


_HTML_SEVERITY_COLORS = {
    "critical": "#c0392b",
    "severe": "#e67e22",
    "moderate": "#f1c40f",
    "warning": "#3498db",
}


def _generate_quality_html_report(result) -> str:
    compliance_color = "#27ae60" if result.compliance_rate >= 90 else "#e67e22" if result.compliance_rate >= 70 else "#c0392b"
    status_text = "PASS" if not result.has_violations else "VIOLATIONS FOUND"
    status_color = "#27ae60" if not result.has_violations else "#c0392b"

    violation_rows = []
    by_severity = result.get_violations_by_severity()
    for severity in [SeverityLevel.CRITICAL.value, SeverityLevel.SEVERE.value,
                     SeverityLevel.MODERATE.value, SeverityLevel.WARNING.value]:
        violations = by_severity[severity]
        for v in violations:
            badge_color = _HTML_SEVERITY_COLORS.get(severity, "#7f8c8d")
            violation_rows.append(
                f"<tr>"
                f"<td>{v.relative_path}</td>"
                f"<td>{v.line_count}</td>"
                f"<td>{v.threshold}</td>"
                f"<td>+{v.lines_over}</td>"
                f"<td><span style=\"background:{badge_color};color:#fff;padding:2px 8px;"
                f"border-radius:4px;font-size:0.8em;\">{severity.upper()}</span></td>"
                f"</tr>"
            )

    violations_table = ""
    if violation_rows:
        violations_table = (
            "<h2>Files Exceeding Threshold</h2>"
            "<table>"
            "<thead><tr><th>File</th><th>Lines</th><th>Threshold</th><th>Over</th><th>Severity</th></tr></thead>"
            "<tbody>" + "".join(violation_rows) + "</tbody>"
            "</table>"
        )
    else:
        violations_table = "<p class=\"pass-msg\">All files are within the threshold.</p>"

    html = (
        "<!DOCTYPE html>"
        "<html lang=\"en\">"
        "<head>"
        "<meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        "<title>Heimdall Code Quality Report</title>"
        "<style>"
        "body{font-family:sans-serif;margin:0;padding:0;background:#f5f6fa;color:#2c3e50;}"
        "header{background:#2c3e50;color:#fff;padding:20px 32px;}"
        "header h1{margin:0;font-size:1.5em;}"
        "header p{margin:4px 0 0;opacity:0.7;font-size:0.9em;}"
        "main{padding:24px 32px;}"
        ".summary{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;}"
        ".card{background:#fff;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,.08);min-width:140px;}"
        ".card .label{font-size:0.75em;text-transform:uppercase;letter-spacing:.05em;color:#7f8c8d;}"
        ".card .value{font-size:2em;font-weight:700;margin-top:4px;}"
        ".status-badge{display:inline-block;padding:6px 16px;border-radius:6px;color:#fff;"
        f"background:{status_color};font-weight:700;font-size:1em;margin-bottom:24px;}}"
        "table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;"
        "box-shadow:0 1px 4px rgba(0,0,0,.08);overflow:hidden;}"
        "th{background:#2c3e50;color:#fff;text-align:left;padding:10px 14px;font-size:0.85em;}"
        "td{padding:9px 14px;border-bottom:1px solid #ecf0f1;font-size:0.85em;word-break:break-all;}"
        "tr:last-child td{border-bottom:none;}"
        "tr:nth-child(even) td{background:#f9fafb;}"
        ".pass-msg{color:#27ae60;font-weight:600;font-size:1.1em;}"
        "h2{margin:0 0 12px;font-size:1.1em;color:#2c3e50;}"
        "</style>"
        "</head>"
        "<body>"
        "<header>"
        "<h1>Heimdall Code Quality Report &mdash; File Length Analysis</h1>"
        f"<p>Scan path: {result.scan_path} &nbsp;|&nbsp; "
        f"Generated: {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; "
        f"Duration: {result.scan_duration_seconds:.2f}s</p>"
        "</header>"
        "<main>"
        f"<div class=\"status-badge\">{status_text}</div>"
        "<div class=\"summary\">"
        "<div class=\"card\"><div class=\"label\">Files Scanned</div>"
        f"<div class=\"value\">{result.total_files_scanned}</div></div>"
        "<div class=\"card\"><div class=\"label\">Violations</div>"
        f"<div class=\"value\" style=\"color:{status_color}\">{result.files_exceeding_threshold}</div></div>"
        "<div class=\"card\"><div class=\"label\">Compliance Rate</div>"
        f"<div class=\"value\" style=\"color:{compliance_color}\">{result.compliance_rate:.1f}%</div></div>"
        "</div>"
        f"{violations_table}"
        "</main>"
        "</body>"
        "</html>"
    )
    return html
