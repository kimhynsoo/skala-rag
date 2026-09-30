"""E 레인 개발용 가짜 데이터 — CONTRACTS.md 3장 스키마를 따른다 (투자 적격 2, 보류 1)."""

from agents.investment import decide, total_score

ITEM_IDS = "A1 A2 A3 B1 B2 B3 C1 C2 C3 D1 D2 D3 E1 E2 E3".split()


def evidence(prefix: str, cid: str, n: int = 1, **kw) -> dict:
    base = {
        "근거ID": f"{prefix}-{cid}-{n:02d}",
        "출처명": "IRDS 2024 More Moore",
        "publisher": "IEEE",
        "pub_year": 2024,
        "source_type": "기관 보고서",
        "url": "https://irds.ieee.org/",
        "source_page": 17,
        "확인일": "2026-09-30",
        "원문발췌": "발췌",
        "chunk_id": None,
    }
    base.update(kw)
    return base


def company(cid: str, name: str, sales: dict | None = None, history: list | None = "default") -> dict:
    if history == "default":
        history = [{"일자": "2024-05-01", "단계": "Series A", "금액": 5_000_000, "투자자": ["A벤처", "B인베"], "확정": True}]
    return {
        "company_id": cid,
        "기업명": name,
        "설립일": "2019-03-01",
        "직원수": 23,
        "업종": "시스템반도체 설계",
        "기술분야": "AI 가속기",
        "sub_domain": "ai_computing",
        "메인아이템": "엣지 NPU",
        "주요구성원": [{"이름": "홍길동", "직책": "CEO", "학력": "서울대 전자공학 박사", "경력": "삼성전자 12년"}],
        "매출액": sales or {"연도": 2024, "국내": 1_200_000, "해외": 300_000, "상태": "공개"},
        "투자유치이력": history,
        "지식재산권": {"등록": [{"번호": "10-2532099", "명칭": "NPU"}], "출원": []},
        "인증수상": ["과기부 장관상"],
        "주요거래처": ["삼성전자"],
        "개발진척도": "시제품",
        "TRL": 6,
        "혁신성": "기존 대비 전력 효율 향상",
        "사업Point": "엣지 AI 수요 대응",
        "source_page": 12,
    }


def record(cid: str, name: str, decision: str, scores: dict[str, int], unknown: list[str] | None = None, **co) -> dict:
    ev = [
        evidence("DIR", cid, source_type="기관 보고서", 출처명="2025 초격차 스타트업 1000+ 디렉토리북", publisher="창업진흥원", pub_year=2025, url=None),
        evidence("ELG", cid, source_type="웹페이지", 출처명="DART 기업개황", publisher="금융감독원", pub_year="2026-09-30", url="https://dart.fss.or.kr/x", source_page=None),
        evidence("TEC", cid),
        evidence("MKT", cid, 출처명="WSTS Spring 2026 Forecast", publisher="WSTS", pub_year=2026, url="https://www.wsts.org/", source_page=2),
        evidence("CMP", cid, source_type="웹페이지", 출처명="경쟁사 제품 데이터시트", publisher="Hailo", pub_year="2026-08-01", url="https://hailo.ai/product", source_page=None),
    ]
    full = {i: scores.get(i, 3) for i in ITEM_IDS}
    unknown = unknown or []
    averages, total = total_score(full)
    return {
        "company_id": cid,
        "current_company": company(cid, name, **co),
        "eligibility": {"판정": "적격", "G1": {"결과": "충족", "사유": "종목코드 없음", "근거ID": [f"ELG-{cid}-01"]},
                        "G2": {"결과": "충족", "사유": "Series A", "근거ID": [f"ELG-{cid}-01"]},
                        "G3": {"결과": "충족", "사유": "M&A 뉴스 없음", "근거ID": [f"ELG-{cid}-01"]},
                        "G4": {"결과": "충족", "사유": "엣지 NPU", "근거ID": [f"DIR-{cid}-01"]},
                        "사유": "G1~G4 모두 충족", "근거ID": [f"ELG-{cid}-01"]},
        "checklist": {f"Q{i}": {"판정": "YES", "근거": "디렉토리북 기재", "근거ID": [f"DIR-{cid}-01"]} for i in range(1, 12)}
        | {"Q7": {"판정": "NO", "근거": "매출 1억 미만", "근거ID": [f"DIR-{cid}-01"]}},
        "technology_analysis": {"핵심기술": "엣지 NPU", "제품성숙도": {"TRL": 6, "단계": "시제품"},
                                "성능지표": [{"지표명": "TOPS/W", "값": "12", "측정조건": "INT8", "검증수준": "자체 발표", "근거ID": [f"DIR-{cid}-01"]}],
                                "기준대조": [], "강점": ["전력 효율"], "한계": ["양산 이력 없음"], "미확인정보": [],
                                "근거ID": [f"TEC-{cid}-01", f"DIR-{cid}-01"], "근거충분": True},
        "market_analysis": {"목표고객": ["엣지 기기 업체"], "시장규모": {"값": "USD 60B", "기준연도": 2026, "근거ID": [f"MKT-{cid}-01"]},
                            "성장률": {"값": "CAGR 25%", "기간": "2026-2030", "근거ID": [f"MKT-{cid}-01"]},
                            "사업모델": "칩 공급", "글로벌확장성": "해외 매출 일부", "성장요인": ["엣지 AI"], "위험": ["경쟁 심화"],
                            "미확인정보": [], "근거ID": [f"MKT-{cid}-01"], "근거충분": True},
        "competitor_analysis": {"경쟁제품": [{"기업명": "Hailo", "제품": "Hailo-8", "핵심지표값": {"TOPS/W": "10"}, "근거ID": [f"CMP-{cid}-01"]}],
                                "비교표": [{"지표": "TOPS/W", "대상기업": "12", "Hailo": "10"}], "우위": ["전력 효율"], "열위": ["생태계"],
                                "비교조건": "공개 스펙 기준", "비교한계": "측정 조건 상이", "근거ID": [f"CMP-{cid}-01"]},
        "scorecard": {"items": {i: {"점수": full[i], "채점이유": "사유", "근거ID": [f"DIR-{cid}-01"]} for i in ITEM_IDS},
                      "averages": averages, "total": total, "unknown_items": unknown},
        "decision": decision,
        "decision_details": {"판단사유": "기술력 우수", "주요위험": ["양산 이력 없음", "거래처 편중"],
                             "추가확인사항": ["양산 계약 여부"], "재검토조건": ["양산 계약 체결"]},
        "route_reason": "",
        "current_evidence": ev,
    }


def fake_results() -> list[dict]:
    hi = {i: 4 for i in ITEM_IDS} | {"C1": 5, "C2": 4, "C3": 5}
    mid = {i: 4 for i in ITEM_IDS}
    low = {i: 2 for i in ITEM_IDS}
    r = [
        record("C03", "알파칩스", "투자 적격", mid),
        record("C07", "베타실리콘", "투자 적격", hi, unknown=["B1"]),
        record("C09", "감마반도체", "보류", low),
    ]
    for rec in r:  # decide()와 일치하도록 재계산
        sc = rec["scorecard"]
        rec["decision"] = decide("적격", sc["total"], sc["averages"]["제품/기술력"])
    return r
