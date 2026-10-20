#!/usr/bin/env python3
"""Run synthetic source-fidelity cases against an already-running local app."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:62140")
    parser.add_argument("--output", type=Path, default=ROOT / "logs" / "model-evaluation.json")
    args = parser.parse_args()
    cases = json.loads((ROOT / "tests/fixtures/notes_cases.json").read_text())
    records = []
    for case in cases:
        started = time.monotonic()
        request = Request(
            args.url.rstrip("/") + "/api/plan",
            data=json.dumps({"notes": case["notes"]}).encode(),
            headers={"Origin": args.url.rstrip("/"), "Content-Type": "application/json"},
            method="POST",
        )
        error = None
        try:
            with urlopen(request, timeout=180) as response:
                actual = json.load(response)
        except Exception as exc:
            actual = {}
            error = type(exc).__name__ + ": " + str(exc)
        tasks = actual.get("tasks", [])
        expected = case["expected"]
        expected_by_quote = {item["quote"]: item for item in expected}
        actual_quotes = [task.get("quote") for task in tasks]
        checks = {
            "request_succeeded": error is None,
            "exact_quote_set": set(actual_quotes) == set(expected_by_quote),
            "no_duplicate_tasks": len(actual_quotes) == len(set(actual_quotes)),
            "no_invented_titles": all(task.get("title", "") in task.get("quote", "") for task in tasks),
            "attributes_preserved": all(
                all(task.get(field) == expected_by_quote.get(task.get("quote"), {}).get(field)
                    for field in ("owner", "due", "condition"))
                for task in tasks
            ),
        }
        record = {
            "id": case["id"],
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "checks": checks,
            "passed": all(checks.values()),
            "response": actual,
            "error": error,
        }
        records.append(record)
        print(json.dumps({key: record[key] for key in ("id", "elapsed_seconds", "passed", "checks")}), flush=True)
    output = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Synthetic local-model checks; not a general accuracy guarantee.",
        "cases": records,
        "passed": sum(record["passed"] for record in records),
        "total": len(records),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    raise SystemExit(0 if output["passed"] == output["total"] else 1)


if __name__ == "__main__":
    main()
