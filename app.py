"""실행: uv run python app.py [--as-of YYYY-MM-DD] | --graph (mermaid 출력)"""

import argparse
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from config import DATA_DIR, EVALUATION_CRITERIA, OUTPUT_DIR  # noqa: E402
from graph import build_graph  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--graph", action="store_true", help="그래프 mermaid만 출력")
    args = p.parse_args()

    app = build_graph()
    if args.graph:
        print(app.get_graph().draw_mermaid())
        return

    result = app.invoke(
        {
            "source_document": str(DATA_DIR / "raw" / "01_기업정보.pdf"),
            "as_of_date": args.as_of,
            "evaluation_criteria": EVALUATION_CRITERIA,
        },
        {"recursion_limit": 1000},  # 45개사 × 노드 수
    )
    out = OUTPUT_DIR / "report.md"
    out.write_text(result["final_report"], encoding="utf-8")
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
