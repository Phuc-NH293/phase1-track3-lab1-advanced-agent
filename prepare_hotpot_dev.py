from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


FAILURE_MODES = (
    None,
    "incomplete_multi_hop",
    "entity_drift",
    "wrong_final_answer",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert HotpotQA distractor data to the lab's QAExample format."
    )
    parser.add_argument(
        "--input",
        default="data/hotpot_dev_distractor_v1.json",
        help="Path to the original HotpotQA JSON file.",
    )
    parser.add_argument(
        "--output",
        default="data/hotpot_dev_100.json",
        help="Path for the converted QAExample JSON file.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of questions to include.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used for deterministic stratified sampling.",
    )
    return parser.parse_args()


def load_hotpot(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("HotpotQA input must be a JSON array.")
    return payload


def stratified_sample(
    rows: list[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("--count must be at least 1.")
    if count > len(rows):
        raise ValueError(
            f"Requested {count} rows, but the input contains only {len(rows)}."
        )

    rng = random.Random(seed)
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (str(row.get("level", "medium")), str(row.get("type", "unknown")))
        buckets[key].append(row)

    for bucket in buckets.values():
        rng.shuffle(bucket)

    selected: list[dict[str, Any]] = []
    keys = sorted(buckets)
    while len(selected) < count:
        made_progress = False
        for key in keys:
            if buckets[key] and len(selected) < count:
                selected.append(buckets[key].pop())
                made_progress = True
        if not made_progress:
            break
    rng.shuffle(selected)
    return selected


def context_chunks(row: dict[str, Any]) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for item in row.get("context", []):
        if not isinstance(item, list) or len(item) != 2:
            continue
        title, sentences = item
        if isinstance(sentences, list):
            text = " ".join(str(sentence).strip() for sentence in sentences).strip()
        else:
            text = str(sentences).strip()
        chunks.append({"title": str(title), "text": text})
    return chunks


def mock_wrong_answer(row: dict[str, Any], gold_answer: str) -> str:
    supporting_titles = [
        str(item[0])
        for item in row.get("supporting_facts", [])
        if isinstance(item, list) and item
    ]
    context_titles = [
        str(item[0])
        for item in row.get("context", [])
        if isinstance(item, list) and item
    ]
    for candidate in supporting_titles + context_titles:
        if candidate.strip().casefold() != gold_answer.strip().casefold():
            return candidate
    return "unknown"


def convert_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    gold_answer = str(row["answer"]).strip()
    converted: dict[str, Any] = {
        "qid": str(row["_id"]),
        "difficulty": str(row.get("level", "medium")),
        "question": str(row["question"]).strip(),
        "gold_answer": gold_answer,
        "context": context_chunks(row),
    }

    failure_mode = FAILURE_MODES[index % len(FAILURE_MODES)]
    if failure_mode is not None:
        converted["mock_wrong_answer"] = mock_wrong_answer(row, gold_answer)
        converted["mock_failure_mode"] = failure_mode
    return converted


def validate_dataset(rows: list[dict[str, Any]]) -> None:
    required = {"qid", "difficulty", "question", "gold_answer", "context"}
    valid_difficulties = {"easy", "medium", "hard"}
    qids: set[str] = set()
    for index, row in enumerate(rows):
        missing = required - row.keys()
        if missing:
            raise ValueError(f"Row {index} is missing fields: {sorted(missing)}")
        if row["difficulty"] not in valid_difficulties:
            raise ValueError(
                f"Row {index} has invalid difficulty: {row['difficulty']!r}"
            )
        if not row["context"]:
            raise ValueError(f"Row {index} has no context chunks.")
        if row["qid"] in qids:
            raise ValueError(f"Duplicate qid: {row['qid']}")
        qids.add(row["qid"])


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    source_rows = load_hotpot(input_path)
    sampled_rows = stratified_sample(source_rows, args.count, args.seed)
    converted_rows = [
        convert_row(row, index) for index, row in enumerate(sampled_rows)
    ]
    validate_dataset(converted_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(converted_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    difficulty_counts: dict[str, int] = defaultdict(int)
    for row in converted_rows:
        difficulty_counts[row["difficulty"]] += 1
    print(
        f"Saved {len(converted_rows)} QAExample records to {output_path} "
        f"(difficulty={dict(sorted(difficulty_counts.items()))})"
    )


if __name__ == "__main__":
    main()
