"""
HTML reporter: renders an inline self-contained report from session database results.

The HTML is generated via a Jinja2 template embedded as a module-level string — no
external files required.  The report includes a summary panel, per-clone-type stats,
and expandable code-snippet cards for every clone group.

:author: Ron Webb
:since: 1.0.0
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import BaseLoader, Environment

from codeecho.db import SessionDB
from codeecho.models import CloneGroup, Fragment, ScanResult

_logger = logging.getLogger("codeecho.reporter.html")

# ── Jinja2 template ───────────────────────────────────────────────────────────

_TEMPLATE: str = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>codeecho — Clone Detection Report</title>
<style>
  :root{--bg:#0f1117;--surface:#1a1d27;--border:#2e3248;--accent:#7c6af7;
        --t1:#ef4444;--t2:#f59e0b;--t3:#22c55e;--text:#e2e8f0;--muted:#94a3b8}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;
       font-size:14px;line-height:1.6;padding:2rem}
  h1{font-size:1.6rem;font-weight:700;margin-bottom:.25rem}
  .subtitle{color:var(--muted);margin-bottom:2rem}
  .stats{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:2rem}
  .stat{background:var(--surface);border:1px solid var(--border);border-radius:8px;
        padding:1rem 1.5rem;min-width:130px}
  .stat-val{font-size:2rem;font-weight:700}
  .stat-lbl{color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}
  .type-badge{display:inline-block;border-radius:4px;padding:2px 8px;font-size:.75rem;
              font-weight:600;color:#fff}
  .t1{background:var(--t1)}.t2{background:var(--t2)}.t3{background:var(--t3)}
  .group{background:var(--surface);border:1px solid var(--border);border-radius:8px;
         margin-bottom:1rem;overflow:hidden}
  .group-header{display:flex;align-items:center;gap:.75rem;padding:.75rem 1rem;
                cursor:pointer;user-select:none}
  .group-title{flex:1;font-weight:600}
  .group-meta{color:var(--muted);font-size:.8rem}
  .chevron{color:var(--muted);transition:transform .2s}
  details[open] .chevron{transform:rotate(90deg)}
  .member{border-top:1px solid var(--border);padding:.75rem 1rem}
  .member-meta{color:var(--muted);font-size:.8rem;margin-bottom:.5rem}
  .member-meta strong{color:var(--text)}
  pre{background:#0a0c12;border-radius:6px;padding:.75rem;overflow-x:auto;
      font-size:.8rem;line-height:1.5;max-height:320px}
  .section-title{font-size:1.1rem;font-weight:600;margin:1.5rem 0 .75rem;
                 padding-bottom:.4rem;border-bottom:1px solid var(--border)}
  .empty{color:var(--muted);font-style:italic;padding:.5rem 0}
  footer{margin-top:2rem;color:var(--muted);font-size:.8rem}
</style>
</head>
<body>
<h1>&#127381; codeecho</h1>
<div class="subtitle">Clone Detection Report &mdash; {{ generated_at }}</div>

<div class="stats">
  <div class="stat"><div class="stat-val">{{ result.files_scanned }}</div>
    <div class="stat-lbl">Files Scanned</div></div>
  <div class="stat"><div class="stat-val">{{ result.fragments_extracted }}</div>
    <div class="stat-lbl">Fragments</div></div>
  <div class="stat"><div class="stat-val" style="color:var(--t1)">{{ result.type1_groups }}</div>
    <div class="stat-lbl">Type-1 Groups</div></div>
  <div class="stat"><div class="stat-val" style="color:var(--t2)">{{ result.type2_groups }}</div>
    <div class="stat-lbl">Type-2 Groups</div></div>
  <div class="stat"><div class="stat-val" style="color:var(--t3)">{{ result.type3_groups }}</div>
    <div class="stat-lbl">Type-3 Groups</div></div>
</div>

{% for type_num, type_label, css_class in [(1,'Type-1 — Exact Clones','t1'),
                                            (2,'Type-2 — Structural Clones','t2'),
                                            (3,'Type-3 — Near Duplicates','t3')] %}
{% set type_groups = groups_by_type[type_num] %}
<div class="section-title">
  <span class="type-badge {{ css_class }}">Type-{{ type_num }}</span>
  {{ type_label }}
</div>
{% if type_groups %}
{% for entry in type_groups %}
<details class="group">
  <summary class="group-header">
    <span class="chevron">&#9658;</span>
    <span class="group-title">Group {{ loop.index }} &mdash; {{ entry.members | length }} members</span>
    {% if entry.group.similarity_score is not none %}
    <span class="group-meta">similarity {{ "%.0f"|format(entry.group.similarity_score * 100) }}%</span>
    {% endif %}
  </summary>
  {% for frag in entry.members %}
  <div class="member">
    <div class="member-meta">
      <strong>{{ frag.language }}</strong> {{ frag.fragment_type }} &bull;
      <strong>{{ frag.file_path }}</strong>
      lines {{ frag.start_line }}–{{ frag.end_line }}
    </div>
    <pre>{{ frag.source_text | e }}</pre>
  </div>
  {% endfor %}
</details>
{% endfor %}
{% else %}
<div class="empty">No {{ type_label }} found.</div>
{% endif %}
{% endfor %}

<footer>Scan path: {{ result.scan_path }} &bull; Session: {{ result.session_id }}</footer>
</body>
</html>"""


def write(
    session_db: SessionDB,
    result: ScanResult,
    output_path: Path,
) -> Path:
    """Render all clone groups for *result.session_id* to an HTML file at *output_path*.

    :param session_db: Open :class:`~codeecho.db.SessionDB` context.
    :param result: Summary statistics from the scan.
    :param output_path: Destination HTML file path.
    :returns: The resolved path of the written file.
    """
    groups = session_db.get_clone_groups(result.session_id)
    groups_by_type: dict[int, list[dict]] = {1: [], 2: [], 3: []}
    for group in groups:
        members = session_db.get_fragments_for_group(group)
        entry = {"group": group, "members": members}
        groups_by_type.setdefault(group.clone_type, []).append(entry)

    env = Environment(loader=BaseLoader(), autoescape=True)  # type: ignore[call-arg]
    tmpl = env.from_string(_TEMPLATE)
    html = tmpl.render(
        result=result,
        groups_by_type=groups_by_type,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        CloneGroup=CloneGroup,
        Fragment=Fragment,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    _logger.info("HTML report written to %s", output_path)
    return output_path.resolve()
