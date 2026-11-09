import json

from flowsight.ai.briefs import write_briefs
from flowsight.ai.guardrails import FOOTER, review
from flowsight.ai.llm import LLMClient


def test_guardrails_block_promissory_language():
    bad = f"This fund is guaranteed to outperform and is risk-free. {FOOTER}"
    issues = review(bad, {}).issues
    assert any("guarantee" in i for i in issues) and any("risk-free" in i for i in issues)


def test_standard_disclaimer_is_allowed():
    ok = f"Past performance does not guarantee future results. {FOOTER}"
    assert review(ok, {}).ok


def test_number_grounding_catches_made_up_figures():
    facts = {"aum": "$12.4M", "growth": 0.034, "fee_bps": 55}
    assert review(f"Assets of $12.4M, growth 3.4%, fee 55 bps. {FOOTER}", facts).ok
    res = review(f"Assets of $19.0M and a 9% yield. {FOOTER}", facts)
    assert not res.ok and len([i for i in res.issues if "ungrounded" in i]) == 2


def test_offline_client_never_calls_out(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = LLMClient()
    assert c.provider == "offline" and c.complete("s", "p") is None


def test_all_generated_briefs_pass_guardrails(built):
    idx = built.ai["briefs"]
    assert len(idx) > 0 and idx.guardrail_ok.all()
    text = (built.settings.path("outputs") / "briefs" / idx.file.iloc[0]).read_text(encoding="utf-8")
    assert FOOTER in text and "**Why now**" in text


def test_llm_output_with_invented_numbers_falls_back_to_template(built, tmp_path):
    class FakeLLM:
        online, model, calls, failures = True, "fake-model", 0, 0

        def complete(self, system, prompt, **kw):
            return "**Why now**\n- This fund will outperform: it returned 42.0% last year and is guaranteed."

    recs = built.engine.table("ml_nba_recommendations").head(2)
    idx = write_briefs(built.engine, recs, built.as_of, tmp_path, FakeLLM(), per_wholesaler=1, max_briefs=1)
    assert idx.provider.iloc[0] == "template"
    assert "compliance" in idx.guardrail_issues.iloc[0] and "ungrounded" in idx.guardrail_issues.iloc[0]
    assert idx.guardrail_ok.iloc[0] == 1


def test_commentary_is_grounded(built):
    com = built.ai["commentary"]
    assert com["guardrail_ok"] and len(com["bullets"]) >= 4
    saved = json.loads((built.settings.path("outputs") / "commentary.json").read_text())
    assert saved["text"].strip().endswith(f"*{FOOTER}*")
