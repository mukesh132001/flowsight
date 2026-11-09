"""GenAI for sales enablement: call-prep briefs + KPI commentary, with guardrails."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config import Settings, month_key
from .briefs import write_briefs
from .commentary import write_commentary
from .llm import LLMClient


def run_ai(engine, settings: Settings, out_dir: Path, log=print) -> dict:
    out_dir = Path(out_dir)
    as_of = month_key(settings.months[-1])
    ai = settings.ai
    client = LLMClient(provider=ai.get("provider", "auto"), model=None)
    log(f"  provider: {client.provider}" + (f" ({client.model})" if client.online else
                                            " - set ANTHROPIC_API_KEY to use Claude"))
    recs = engine.table("ml_nba_recommendations")
    idx = write_briefs(engine, recs, as_of, out_dir / "briefs", client, max_briefs=int(ai.get("max_briefs", 40)))
    idx.drop(columns=["facts_json"]).to_csv(out_dir / "briefs" / "index.csv", index=False)
    engine.load_df("ai_briefs", idx)
    log(f"  briefs: {len(idx)} written, {int(idx.guardrail_ok.sum())} passed guardrails")
    card = pd.read_json(out_dir / "kpi_scorecard.json")
    drivers = json.loads((out_dir / "net_flow_drivers.json").read_text())
    alerts = pd.read_csv(out_dir / "kpi_alerts.csv")
    ml_path = out_dir / "ml_metrics.json"
    ml = json.loads(ml_path.read_text()) if ml_path.exists() else None
    com = write_commentary(engine, card, drivers, alerts, ml, client, out_dir)
    log(f"  commentary: {len(com['bullets'])} bullets, guardrails {'passed' if com['guardrail_ok'] else 'FAILED'}")
    for issue in com["guardrail_issues"]:
        log(f"    guardrail: {issue}")
    return {"briefs": idx, "commentary": com, "client_calls": client.calls, "client_failures": client.failures}
