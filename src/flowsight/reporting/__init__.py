"""Stakeholder outputs: Excel KPI pack, PowerPoint review, web dashboard, BI extracts."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..config import Settings, month_key
from .bi_export import write_bi_extracts
from .dashboard import build_dashboard
from .data import build_report_model
from .excel_pack import build_excel
from .ppt_deck import build_deck


def run_reports(engine, settings: Settings, out_dir: Path, log=print) -> dict:
    out_dir = Path(out_dir)
    as_of = month_key(settings.months[-1])
    model = build_report_model(engine, out_dir, as_of)
    tag = settings.months[-1].strftime("%Y-%m")
    xlsx = build_excel(model, out_dir / f"FlowSight_KPI_Pack_{tag}.xlsx")
    pptx = build_deck(model, out_dir / f"FlowSight_Distribution_Review_{tag}.pptx")
    html = build_dashboard(model, out_dir / "dashboard" / "index.html")
    bi = write_bi_extracts(engine, out_dir / "bi")
    log(f"  {xlsx.name}, {pptx.name}, dashboard/index.html, {len(bi)} BI extracts")
    # small committed copies for GitHub readers (data/ and outputs/ are git-ignored)
    if settings.scale == "full":
        samples = settings.path("samples")
        samples.mkdir(parents=True, exist_ok=True)
        for p in (xlsx, pptx):
            shutil.copy2(p, samples / p.name)
        shutil.copy2(html, ROOT_DOCS_SITE() / "index.html")
        for f in ("commentary.md",):
            shutil.copy2(out_dir / f, samples / f)
        briefs = sorted((out_dir / "briefs").glob("*.md"))[:3]
        (samples / "briefs").mkdir(exist_ok=True)
        for b in briefs:
            shutil.copy2(b, samples / "briefs" / b.name)
        log(f"  samples/ and site/index.html refreshed")
    return {"model": model, "xlsx": xlsx, "pptx": pptx, "html": html, "bi": bi}


def ROOT_DOCS_SITE() -> Path:
    from ..config import ROOT
    site = ROOT / "site"
    site.mkdir(exist_ok=True)
    return site
