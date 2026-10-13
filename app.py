"""실행: uv run python app.py [--as-of YYYY-MM-DD] [--only C03,C11] [--pdf] | --graph (mermaid 출력)"""

import argparse
import json
import uuid
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from config import DATA_DIR, EVALUATION_CRITERIA, MAX_CONCURRENCY, OUTPUT_DIR  # noqa: E402
from graph import build_graph  # noqa: E402
from obs import summarize  # noqa: E402
from agents._report_pdf import export_pdf, report_meta  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--graph", action="store_true", help="그래프 mermaid만 출력")
    p.add_argument("--pdf", action="store_true", help="5쪽 이내 PDF도 생성")
    p.add_argument("--only", default="", help="쉼표로 구분한 company_id만 평가 (예: C03,C11)")
    args = p.parse_args()

    app = build_graph(checkpointer=MemorySaver())  # 단계별 State 스냅샷 → 실패 지점 확인·재개
    if args.graph:
        print(app.get_graph().draw_mermaid())
        return

    trace_id = uuid.uuid4().hex[:12]
    print(f"trace_id: {trace_id}  (결정 로그: outputs/logs/{trace_id}.jsonl)", flush=True)
    config = {
        "recursion_limit": 3000,  # 45개사 × (Supervisor 왕복 포함) 노드 수
        "max_concurrency": MAX_CONCURRENCY,  # 병렬 노드 동시 실행 상한
        "configurable": {"thread_id": trace_id},  # checkpointer 키 = 상관 키
        "run_name": f"skala-agent-{trace_id}",
        "metadata": {"trace_id": trace_id},  # LangSmith에서 trace_id로 검색
        "tags": ["supervisor"],
    }
    result = {}
    for mode, update in app.stream(
        {
            "source_document": str(DATA_DIR / "raw" / "01_기업정보.pdf"),
            "as_of_date": args.as_of,
            "evaluation_criteria": EVALUATION_CRITERIA,
            "trace_id": trace_id,
            "company_filter": [c.strip() for c in args.only.split(",") if c.strip()],
        },
        config,
        stream_mode=["updates", "values"],
    ):
        if mode == "values":
            result = update
        else:
            for stage, values in update.items():
                company = (values or {}).get("current_company") or {}
                label = f" {company['company_id']} {company['기업명']}" if company else ""
                print(f"[{stage}]{label}", flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "report.md"
    out.write_text(result["final_report"], encoding="utf-8")
    print(f"saved: {out}")
    (OUTPUT_DIR / "evaluation_results.json").write_text(
        json.dumps({key: result.get(key) for key in ("trace_id", "as_of_date", "ranking", "selected_company_id",
                                                 "eval_result", "report_attempts", "evaluation_results", "errors")},
                   ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print("dynamic summary:", json.dumps(summarize(trace_id), ensure_ascii=False))
    if args.pdf:
        pdf = OUTPUT_DIR / "report.pdf"
        export_pdf(result["final_report"], report_meta(result), pdf)
        print(f"saved: {pdf}")


if __name__ == "__main__":
    main()
