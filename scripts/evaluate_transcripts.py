#!/usr/bin/env python3
"""Exercise synthetic meeting transcripts through the running local application."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def cases():
    meeting = (ROOT / "tests/fixtures/meeting_transcript.txt").read_text()
    expected = [
        ("Mira Shah", "09:10:25", "Friday"),
        ("Mira Shah", "09:10:42", None),
        ("Lee Park", "09:11:02", "Monday"),
        ("Lee Patel", "09:11:14", "Monday"),
    ]
    filler = "\n".join(
        f"Robin Chen 08:{i // 60:02}:{i % 60:02}\n"
        "The catalogue contains reference photographs and historical entries. "
        "This describes its display colors, labels and archive layout."
        for i in range(140)
    )
    long_meeting = filler + "\n" + meeting + (
        "\nMira Shah 11:20:00\nI will send the final checklist on Tuesday."
    )
    return [
        ("fragmented-speakers-and-conditions", meeting, expected),
        ("long-meeting-tail-preserved", long_meeting, expected + [("Mira Shah", "11:20:00", "Tuesday")]),
        ("later-cancellation-and-speculation",
         "Mira Shah 09:00:00\nI will send the sample on Friday.\n"
         "Lee Park 09:01:00\nDo not send the sample. The client cancelled it.\n"
         "Mira Shah 09:02:00\nUnderstood, I won't send it. That task is cancelled.\n"
         "Lee Patel 09:03:00\nMaybe we could redesign the catalogue someday.\n", []),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:62140")
    parser.add_argument("--output", type=Path, default=ROOT / "logs/transcript-evaluation.json")
    parser.add_argument("--case", choices=[case[0] for case in cases()], help="Run one case while investigating a failure.")
    args = parser.parse_args()
    records = []
    for name, notes, expected in cases():
        if args.case and name != args.case:
            continue
        started = time.monotonic()
        request = Request(
            args.url.rstrip("/") + "/api/plan",
            data=json.dumps({"notes": notes}).encode(),
            headers={"Origin": args.url.rstrip("/"), "Content-Type": "application/json"},
        )
        error = None
        try:
            with urlopen(request, timeout=150) as response:
                actual = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            actual = {}
            error = type(exc).__name__
        tasks = actual.get("tasks", [])
        observed = [(t.get("owner"), t.get("source", {}).get("timestamp"), t.get("due")) for t in tasks]
        checks = {
            "request_succeeded": error is None and actual.get("input_kind") == "transcript",
            "expected_actions_and_attribution": sorted(observed, key=str) == sorted(expected, key=str),
            "source_and_context_match": all(
                t["quote"] in notes and t["source"]["context"] in notes
                and t["quote"] in t["source"]["context"]
                and t["title"] in " ".join(t["quote"].split()) for t in tasks
            ),
            "no_duplicate_ids": len({t["id"] for t in tasks}) == len(tasks),
        }
        if expected:
            primary = next((t for t in tasks if t.get("source", {}).get("timestamp") == "09:10:25"), None)
            checks["cross_turn_prerequisites_preserved"] = bool(primary) and all(
                text in primary["source"]["context"]
                for text in ("Once account access works and the sample is ready", "Only after finance approves")
            )
        record = {
            "id": name, "input_characters": len(notes),
            "input_sha256": hashlib.sha256(notes.encode()).hexdigest(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "checks": checks, "passed": all(checks.values()), "response": actual, "error": error,
        }
        records.append(record)
        print(json.dumps({k: record[k] for k in ("id", "input_characters", "elapsed_seconds", "passed", "checks")}), flush=True)
    result = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Synthetic local-model transcript cases; not a general accuracy or completeness guarantee.",
        "cases": records, "passed": sum(r["passed"] for r in records), "total": len(records),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    raise SystemExit(0 if result["passed"] == result["total"] else 1)


if __name__ == "__main__":
    main()
