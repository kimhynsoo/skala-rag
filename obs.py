"""결정 로그는 State가 아니라 외부 JSONL로 (State 무한 증식 방지). trace_id로 State·LangSmith와 연결."""

import json
import time

from config import OUTPUT_DIR

LOG_DIR = OUTPUT_DIR / "logs"


def log_decision(state: dict, node: str, decision, reason: str) -> None:
    """{trace_id, company_id, node, decision, reason, ts}를 outputs/logs/{trace_id}.jsonl에 한 줄 추가."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    trace_id = state.get("trace_id") or "no-trace"
    rec = {
        "trace_id": trace_id,
        "company_id": (state.get("current_company") or {}).get("company_id"),
        "node": node,
        "decision": decision,
        "reason": reason,
        "ts": time.time(),
    }
    with open(LOG_DIR / f"{trace_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def summarize(trace_id: str) -> dict:
    """동적 동작 실증용 집계: Supervisor 라우팅 수, 에이전트별 실행 수, 재작업 수, 품질 평가 결과."""
    path = LOG_DIR / f"{trace_id}.jsonl"
    if not path.exists():
        return {}
    recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    runs: dict[str, int] = {}
    for r in recs:
        if r["node"] in ("technology", "market", "competitor"):
            runs[r["node"]] = runs.get(r["node"], 0) + 1
    firsts = {(r["company_id"], r["node"]) for r in recs if r["node"] in runs}
    return {
        "supervisor_routes": sum(r["node"] == "supervisor" for r in recs),
        "agent_runs": runs,
        "reworks": sum(runs.values()) - len(firsts),
        "evaluations": [r["decision"] for r in recs if r["node"] == "evaluator"],
    }
