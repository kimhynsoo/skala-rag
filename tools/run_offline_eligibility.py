"""Apply offline eligibility rules to the scoped system-semiconductor list."""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.eligibility import evaluate_company, load_external_eligibility_results, load_g4_results

COMPANIES_PATH = ROOT / "tools" / "system_semiconductor_companies.json"
OUTPUT_PATH = ROOT / "tools" / "offline_eligibility_results.json"


def main() -> None:
    companies = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))
    g4_results = load_g4_results()
    external_results = load_external_eligibility_results()
    as_of_date = date.today().isoformat()
    results = []
    counts = Counter()

    for company in companies:
        cid = company["company_id"]
        eligibility, evidence = evaluate_company(
            company,
            as_of_date,
            g4_results.get(cid),
            external_results.get(cid),
        )
        counts[eligibility["판정"]] += 1
        results.append({
            "company_id": cid,
            "기업명": company["기업명"],
            "eligibility": eligibility,
            "current_evidence": evidence,
        })

    payload = {
        "as_of_date": as_of_date,
        "scope": "시스템반도체 섹터 45개사",
        "external_api_checks": "G1은 OpenDART 기업코드, G2·G3는 Tavily 외부 결과를 반영; 정확한 법인 매칭이 안 되면 확인불가",
        "counts": dict(counts),
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"저장: {OUTPUT_PATH}")
    print("기업별 최종 상태:", dict(counts))


if __name__ == "__main__":
    main()
