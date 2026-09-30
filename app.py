"""실행: uv run python app.py [--as-of YYYY-MM-DD] | --graph (mermaid 출력)"""

import argparse
import json
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from config import DATA_DIR, EVALUATION_CRITERIA, OUTPUT_DIR  # noqa: E402
from graph import build_graph  # noqa: E402
from agents._report_pdf import export_pdf, report_meta  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--graph", action="store_true", help="그래프 mermaid만 출력")
    p.add_argument("--pdf", action="store_true", help="5쪽 이내 PDF도 생성")
    args = p.parse_args()

    app = build_graph()
    if args.graph:
        print(app.get_graph().draw_mermaid())
        return

    result = {}
    for mode, update in app.stream(
        {
            "source_document": str(DATA_DIR / "raw" / "01_기업정보.pdf"),
            "as_of_date": args.as_of,
            "evaluation_criteria": EVALUATION_CRITERIA,
        },
        {"recursion_limit": 1000},  # 45개사 × 노드 수
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
        json.dumps({key: result.get(key) for key in ("as_of_date", "ranking", "selected_company_id", "evaluation_results", "errors")},
                   ensure_ascii=False, indent=2), encoding="utf-8",
    )
    if args.pdf:
        pdf = OUTPUT_DIR / "report.pdf"
        export_pdf(result["final_report"], report_meta(result), pdf)
        print(f"saved: {pdf}")


if __name__ == "__main__":
    main()
