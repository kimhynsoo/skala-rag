"""45개 후보 G4 AI 관련성 사전 스크리닝. 결과를 입력 데이터별로 캐시한다."""

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from llm import get_llm
from tools.eligibility_cache import company_hash

ROOT = Path(__file__).resolve().parents[1]
COMPANIES_PATH = ROOT / "data" / "processed" / "companies.json"
PROMPT_PATH = ROOT / "prompts" / "eligibility.md"
OUTPUT_PATH = ROOT / "data" / "processed" / "g4_screening_results.json"


class G4Result(BaseModel):
    판정: Literal["통과", "불통과", "확인필요"]
    사유: str
    근거표현: list[str] = Field(default_factory=list)


def _company_input(company: dict) -> str:
    fields = ("기업명", "메인아이템", "업종", "기술분야", "사업Point", "혁신성")
    return "\n".join(f"{key}: {company.get(key) or '정보 없음'}" for key in fields)


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
        temp_path = Path(f.name)
    temp_path.replace(path)


def screen(companies_path: Path = COMPANIES_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    load_dotenv(ROOT / ".env")
    companies = json.loads(companies_path.read_text(encoding="utf-8"))
    if not isinstance(companies, list) or not companies:
        raise ValueError(f"기업 목록은 비어 있지 않은 JSON 배열이어야 합니다: {companies_path}")

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    model_name = os.getenv("LLM_MODEL", "gpt-4.1-mini")
    g4_inputs = [
        {key: company.get(key) for key in ("company_id", "기업명", "메인아이템", "업종", "기술분야", "사업Point", "혁신성")}
        for company in companies
    ]
    source_hash = hashlib.sha256(
        json.dumps(g4_inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache = {}
    if output_path.exists():
        old = json.loads(output_path.read_text(encoding="utf-8"))
        if old.get("source_hash") == source_hash and old.get("prompt_hash") == prompt_hash and old.get("model") == model_name:
            cache = {row["company_id"]: row for row in old.get("results", [])}

    llm = None
    results = []
    for i, company in enumerate(companies, start=1):
        company_id = company.get("company_id") or f"ROW{i:02d}"
        if company_id in cache:
            result = {
                **cache[company_id],
                "기업명": company.get("기업명", ""),
                "source_page": company.get("source_page"),
            }
        else:
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY가 없습니다. skala-rag/.env에 설정하세요.")
            if llm is None:
                llm = get_llm().with_structured_output(G4Result, method="json_schema", strict=True)
            response = llm.invoke([
                ("system", prompt),
                ("human", f"다음 기업을 G4 기준으로 판정하세요.\n\n{_company_input(company)}"),
            ])
            result = {
                "company_id": company_id,
                "기업명": company.get("기업명", ""),
                "source_page": company.get("source_page"),
                **response.model_dump(),
            }
            # 호출 직후 저장해 중단되더라도 이미 처리한 기업의 API 비용을 반복하지 않는다.
            cache[company_id] = result
            _write_json_atomic(output_path, {
                "source_hash": source_hash,
                "prompt_hash": prompt_hash,
                "model": model_name,
                "results": list(cache.values()),
            })
        result["company_hash"] = company_hash(company)
        results.append(result)
        print(f"[{i}/{len(companies)}] {company_id}: {result['판정']}")

    counts = {label: sum(row["판정"] == label for row in results) for label in ("통과", "불통과", "확인필요")}
    payload = {
        "as_of_date": date.today().isoformat(),
        "source_hash": source_hash,
        "prompt_hash": prompt_hash,
        "model": model_name,
        "counts": counts,
        "results": results,
    }
    _write_json_atomic(output_path, payload)
    print(f"G4 통과: {counts['통과']}/{len(results)} (불통과 {counts['불통과']}, 확인필요 {counts['확인필요']})")
    print(f"저장: {output_path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--companies", type=Path, default=COMPANIES_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    screen(args.companies, args.output)


if __name__ == "__main__":
    main()
