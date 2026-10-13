from agents.evaluator import rule_checks

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
