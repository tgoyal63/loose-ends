#!/usr/bin/env python3
"""Exercise synthetic meeting transcripts through the running local application."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def cases():
    meeting = (ROOT / "tests/fixtures/meeting_transcript.txt").read_text()
    expected = [
        ("Mira Shah", "09:10:25", "Friday", "create the sample listing"),
        ("Mira Shah", "09:10:42", None, "notify Lee"),
        ("Lee Park", "09:11:02", "Monday", "review the sample"),
        ("Lee Patel", "09:11:14", "Monday", "review the sample"),
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
    natural_meeting = (ROOT / "tests/fixtures/natural_meeting.txt").read_text()
    return [
        ("fragmented-speakers-and-conditions", meeting, expected),
        ("long-meeting-tail-preserved", long_meeting,
         expected + [("Mira Shah", "11:20:00", "Tuesday", "send the final checklist")]),
        ("later-cancellation-and-speculation",
         "Mira Shah 09:00:00\nI will send the sample on Friday.\n"
         "Lee Park 09:01:00\nDo not send the sample. The client cancelled it.\n"
         "Mira Shah 09:02:00\nUnderstood, I won't send it. That task is cancelled.\n"
         "Lee Patel 09:03:00\nMaybe we could redesign the catalogue someday.\n", []),
        ("natural-meeting-with-demos-and-corrections", natural_meeting, [
            ("Nora Ellis", "10:01:45", "Thursday", "circulate the pilot agenda"),
            ("June Park", "10:05:45", "Friday", "replace the placeholder dates"),
            ("Ravi Mehta", "10:10:00", None, "verify Priya's preview account"),
            ("Omar Bell", "10:14:15", "Monday", "test the recording controls"),
            ("Priya Cole", "10:18:45", None, "reserve the east room"),
            ("Tessa Wynn", "10:21:30", "Wednesday", "prepare the large-print task cards"),
            ("Ravi Mehta", "10:24:15", "Tuesday", "add a screen-reader confirmation"),
            ("June Park", "10:27:00", None, "check the two donor-credit lines"),
            ("Nora Ellis", "10:29:00", "16:00", "send the final action summary"),
            ("Priya Cole", "10:29:45", "Friday", "update the volunteer contact sheet"),
        ]),
    ]


def expected_actions_match(tasks, expected):
    """Match every expected action once, including its meaningful source words.

    Matching only an owner, timestamp and date can accept an acknowledgement or
    a deadline as the task title. Extra source words are fine, but the action's
    verb and object must remain present in the corresponding title.
    """
    if not isinstance(tasks, list) or len(tasks) != len(expected):
        return False
    remaining = list(expected)
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("source"), dict):
            return False
        title = task.get("title")
        if not isinstance(title, str):
            return False
        title = " ".join(title.split())
        observed = (task.get("owner"), task["source"].get("timestamp"), task.get("due"))
        match = next((index for index, item in enumerate(remaining)
                      if observed == item[:3] and item[3] in title), None)
        if match is None:
            return False
        remaining.pop(match)
    return not remaining


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:62140")
    parser.add_argument("--mode", choices=("local", "hosted"), default="local", help="Explicit processing destination; hosted sends synthetic cases to Groq and may use API credit.")
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
            data=json.dumps({"notes": notes, "mode": args.mode}).encode(),
            headers={"Origin": args.url.rstrip("/"), "Content-Type": "application/json"},
        )
        error = None
        try:
            with urlopen(request, timeout=175) as response:
                actual = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            actual = {}
            error = type(exc).__name__ + (f": {exc.code}" if isinstance(exc, HTTPError) else "")
            if isinstance(exc, HTTPError):
                # Keep the app's safe diagnostics for synthetic failures so a
                # second paid request is not needed just to recover its category.
                try:
                    with exc:
                        raw = exc.read(65_537)
                except (OSError, HTTPException):
                    raw = b""
                if len(raw) <= 65_536:
                    try:
                        failure = json.loads(raw)
                    except (ValueError, RecursionError):
                        failure = None
                    if isinstance(failure, dict) and isinstance(failure.get("error"), dict):
                        actual = {"error": failure["error"]}
        tasks = actual.get("tasks", [])
        checks = {
            "request_succeeded": error is None and actual.get("input_kind") == "transcript",
            "expected_actions_and_attribution": expected_actions_match(tasks, expected),
            "source_and_context_match": all(
                t["quote"] in notes and t["source"]["context"] in notes
                and t["quote"] in t["source"]["context"]
                and t["title"] in " ".join(t["quote"].split()) for t in tasks
            ),
            "no_duplicate_ids": len({t["id"] for t in tasks}) == len(tasks),
        }
        if expected and name != "natural-meeting-with-demos-and-corrections":
            primary = next((t for t in tasks if t.get("source", {}).get("timestamp") == "09:10:25"), None)
            checks["cross_turn_prerequisites_preserved"] = bool(primary) and all(
                text in primary["source"]["context"]
                for text in ("Once account access works and the sample is ready", "Only after finance approves")
            )
        if name == "natural-meeting-with-demos-and-corrections":
            checks["conditional_commitments_preserved"] = all(
                any(t.get("source", {}).get("timestamp") == timestamp and condition in (t.get("condition") or "")
                    for t in tasks)
                for timestamp, condition in [
                    ("10:10:00", "After the pilot administrator restores collection access"),
                    ("10:18:45", "If the building coordinator confirms the east room is available"),
                ]
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
        "scope": "Synthetic model transcript cases; not a general accuracy or completeness guarantee.",
        "mode": args.mode,
        "cases": records, "passed": sum(r["passed"] for r in records), "total": len(records),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    raise SystemExit(0 if result["passed"] == result["total"] else 1)


if __name__ == "__main__":
    main()
