"""Self-contained HTML dashboard (no external scripts or fonts), ready for GitHub Pages."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"


def build_dashboard(model: dict, path: Path) -> Path:
    payload = json.dumps(model, default=float, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")          # never close the <script> early
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/", payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
