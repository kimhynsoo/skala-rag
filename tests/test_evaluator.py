from agents import evaluator
from agents.evaluator import EvaluationResult, rule_checks

EV = [
    {"근거ID": "TEC-02-0008", "publisher": "IRDS"},
    {"근거ID": "MKT-12-0001", "publisher": "SIA"},
    {"근거ID": "DIR-C03-01", "publisher": "창업진흥원"},
    {"근거ID": "CMP-C03-01", "publisher": "IEEE"},
]
GOOD = "기술 [TEC-02-0008] 시장 [MKT-12-0001] 경쟁 [CMP-C03-01] 기업 [DIR-C03-01]"


def _report(body: str) -> str:
    return f"## SUMMARY\n{body}\n\n## REFERENCE\n- 목록"


def test_all_rules_pass():
    assert all(c.passed for c in rule_checks(_report(GOOD), EV).values())


def test_groundedness_fails_on_unknown_or_no_citation():
    assert not rule_checks(_report("근거 없음"), EV)["groundedness"].passed
    assert not rule_checks(_report("[TEC-99-9999]"), EV)["groundedness"].passed


def test_neutrality_flags_banned_phrase():
    r = rule_checks(_report("압도적인 기술 " + GOOD), EV)
    assert not r["neutrality"].passed and "압도적" in r["neutrality"].reason


def test_bias_control_single_source():
    assert not rule_checks(_report("[TEC-02-0008] 또 [TEC-02-0008]"), EV)["bias_control"].passed


def test_bias_control_ignores_company_directory():
    body = "[DIR-C03-01] " * 10 + "[TEC-02-0008] [MKT-12-0001] [CMP-C03-01]"  # 기업 자체 소개는 편중 계산 제외
    assert rule_checks(_report(body), EV)["bias_control"].passed


def test_judge_prompt_built_from_schema():
    p = evaluator.build_judge_prompt()
    assert "1. groundedness" in p and "3. bias_control" in p and "issues" not in p.split("[평가 기준]")[1]


def _judge(ok: bool):
    return EvaluationResult(groundedness=ok, neutrality=True, bias_control=True,
                            issues=[] if ok else ["SUMMARY 2문장 수치 원문 없음"])


def _state(body: str):
    return {"final_report": _report(body), "report_attempts": 0,
            "evaluation_results": [{"company_id": "C03", "current_evidence": EV}]}


def test_run_passes_when_rules_and_judge_pass(monkeypatch):
    monkeypatch.setattr(evaluator, "structured_call", lambda *a: _judge(True))
    out = evaluator.run(_state(GOOD))
    assert out["eval_result"]["passed"] and out["eval_result"]["score"] == 1.0 and out["report_attempts"] == 1


def test_run_fails_when_judge_fails(monkeypatch):
    monkeypatch.setattr(evaluator, "structured_call", lambda *a: _judge(False))
    out = evaluator.run(_state(GOOD))
    assert not out["eval_result"]["passed"] and any("SUMMARY" in i for i in out["eval_result"]["issues"])
    assert out["eval_result"]["groundedness"]["rule"].startswith("인용 4건")


def test_eval_loop_terminates():
    assert evaluator.route({"eval_result": {"passed": True}, "report_attempts": 1}) == "__end__"
    assert evaluator.route({"eval_result": {"passed": False}, "report_attempts": 1}) == "report"
    assert evaluator.route({"eval_result": {"passed": False}, "report_attempts": 3}) == "end_with_warning"
    out = evaluator.end_with_warning({"eval_result": {"score": 0.67, "issues": ["x"]}})
    assert out["route_reason"].startswith("[경고]")


def test_report_receives_feedback_on_regeneration(monkeypatch, tmp_path):
    import json

    from agents import report
    from tests.test_report import _state as report_state

    seen = []
    monkeypatch.setattr(report, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(report, "export_pdf", lambda *a, **k: None)
    monkeypatch.setattr(report, "load_prompt", lambda n: "p")

    def fake(schema, system, user):
        seen.append(json.loads(user).get("품질평가피드백"))
        return report.ReportProse(summary="요약 [DIR-C07-01]", risks="- 위험 [DIR-C07-01]")

    monkeypatch.setattr(report, "structured_call", fake)
    report.run(report_state())  # 첫 생성
    report.run(report_state(eval_result={"passed": False, "issues": ["neutrality: 금지 표현 ['완벽한']"]}))
    report.run(report_state(eval_result={"passed": True, "issues": []}))
    assert seen == [None, ["neutrality: 금지 표현 ['완벽한']"], None]
