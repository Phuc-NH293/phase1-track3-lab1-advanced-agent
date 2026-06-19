from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from .schemas import FailureMode, ReportPayload, RunRecord

FAILURE_MODES: tuple[FailureMode, ...] = (
    "entity_drift",
    "incomplete_multi_hop",
    "wrong_final_answer",
    "looping",
    "reflection_overfit",
)


def summarize(records: list[RunRecord]) -> dict:
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)
    summary: dict[str, dict] = {}
    for agent_type, rows in grouped.items():
        summary[agent_type] = {
            "count": len(rows),
            "em": round(mean(1.0 if row.is_correct else 0.0 for row in rows), 4),
            "avg_attempts": round(mean(row.attempts for row in rows), 4),
            "avg_token_estimate": round(mean(row.token_estimate for row in rows), 2),
            "avg_latency_ms": round(mean(row.latency_ms for row in rows), 2),
        }
    if "react" in summary and "reflexion" in summary:
        summary["delta_reflexion_minus_react"] = {
            "em_abs": round(summary["reflexion"]["em"] - summary["react"]["em"], 4),
            "attempts_abs": round(
                summary["reflexion"]["avg_attempts"] - summary["react"]["avg_attempts"], 4
            ),
            "tokens_abs": round(
                summary["reflexion"]["avg_token_estimate"]
                - summary["react"]["avg_token_estimate"],
                2,
            ),
            "latency_abs": round(
                summary["reflexion"]["avg_latency_ms"]
                - summary["react"]["avg_latency_ms"],
                2,
            ),
        }
    return summary


def failure_breakdown(records: list[RunRecord]) -> dict:
    """Group by failure type so the report directly exposes each error family."""
    counts: dict[str, Counter] = {mode: Counter() for mode in FAILURE_MODES}
    counts["none"] = Counter()
    for record in records:
        counts[record.failure_mode][record.agent_type] += 1
    return {
        mode: {
            "react": counter.get("react", 0),
            "reflexion": counter.get("reflexion", 0),
            "total": sum(counter.values()),
        }
        for mode, counter in counts.items()
    }


def build_report(records: list[RunRecord], dataset_name: str, mode: str = "mock") -> ReportPayload:
    examples = [
        {
            "qid": record.qid,
            "agent_type": record.agent_type,
            "gold_answer": record.gold_answer,
            "predicted_answer": record.predicted_answer,
            "is_correct": record.is_correct,
            "attempts": record.attempts,
            "failure_mode": record.failure_mode,
            "reflection_count": len(record.reflections),
            "token_estimate": record.token_estimate,
            "latency_ms": record.latency_ms,
        }
        for record in records
    ]
    discussion = (
        "Reflexion is most useful when the first response stops at an intermediate "
        "entity, drifts to a related entity, or chooses a plausible but unsupported "
        "final answer. The evaluator turns that failure into structured evidence, and "
        "the reflector converts it into a short lesson plus a concrete next-step "
        "strategy. The next Actor attempt receives this memory and must still verify it "
        "against the supplied context. This usually improves exact-match accuracy, but "
        "it costs extra model calls, tokens, and latency. Remaining failures may come "
        "from a weak evaluator, ambiguous context, repeated looping, or reflection "
        "overfitting. Therefore the report compares accuracy and cost together rather "
        "than treating more attempts as automatically better."
    )
    return ReportPayload(
        meta={
            "dataset": dataset_name,
            "mode": mode,
            "num_records": len(records),
            "num_questions": len({record.qid for record in records}),
            "agents": sorted({record.agent_type for record in records}),
        },
        summary=summarize(records),
        failure_modes=failure_breakdown(records),
        examples=examples,
        extensions=[
            "structured_evaluator",
            "reflection_memory",
            "memory_compression",
            "benchmark_report_json",
            "mock_mode_for_autograding",
        ],
        discussion=discussion,
    )


def save_report(report: ReportPayload, out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(
        json.dumps(report.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary = report.summary
    react = summary.get("react", {})
    reflexion = summary.get("reflexion", {})
    delta = summary.get("delta_reflexion_minus_react", {})
    extension_lines = "\n".join(f"- {item}" for item in report.extensions)
    markdown = f"""# Lab 16 Benchmark Report

## Metadata

- Dataset: {report.meta['dataset']}
- Mode: {report.meta['mode']}
- Questions: {report.meta['num_questions']}
- Records: {report.meta['num_records']}
- Agents: {', '.join(report.meta['agents'])}

## Summary

| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | {react.get('em', 0)} | {reflexion.get('em', 0)} | {delta.get('em_abs', 0)} |
| Avg attempts | {react.get('avg_attempts', 0)} | {reflexion.get('avg_attempts', 0)} | {delta.get('attempts_abs', 0)} |
| Avg tokens | {react.get('avg_token_estimate', 0)} | {reflexion.get('avg_token_estimate', 0)} | {delta.get('tokens_abs', 0)} |
| Avg latency (ms) | {react.get('avg_latency_ms', 0)} | {reflexion.get('avg_latency_ms', 0)} | {delta.get('latency_abs', 0)} |

## Failure modes

```json
{json.dumps(report.failure_modes, indent=2)}
```

## Extensions implemented

{extension_lines}

## Discussion

{report.discussion}
"""
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path
