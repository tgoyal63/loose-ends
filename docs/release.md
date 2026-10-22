# October 22, 2026 release

This release demonstrates editable action drafts from ordinary notes, with
original quotations, review, completion and Markdown export. It adds bounded
local-response recovery and optional, explicitly selected Groq processing.
Long-meeting extraction remains incomplete and is not a release claim.

## Current checks

- Two independent source/behavior reviewers each ran the 149-test unit and HTTP
  suite successfully. JavaScript syntax and diff checks also passed.
- A fresh isolated browser used actual local Qwen3 inference on synthetic
  project-handoff notes. It returned the three expected actions and rejected
  one additional proposal. The conditional checklist task kept its full source
  line. Editing, completion and an actual Markdown download were demonstrated.
- The browser measured that request at 5.6244 seconds. The recording is about
  70 seconds and includes review and editing; its duration is not model latency.
- The real local five-case notes suite passed again. A separate browser-offline
  check preserved notes, edited drafts, completion state and the exact export.
  Desktop and 390-/320-pixel layouts had no horizontal overflow.

See the [browser receipt](evidence/submission-browser.json),
[demo and screenshots](demo/README.md) and [video](demo/release-walkthrough.mp4).
The recording contains synthetic notes and no provider credentials. It shows
local processing, not hosted inference. Historical October 20 media remain
available under their original names.

## What remains unresolved

The latest saved hosted natural-meeting run found nine of ten expected actions
in a 120-turn synthetic fixture. It missed a conditional account-verification
commitment and failed the unchanged acceptance checks. The local model also
failed the long-meeting case. These are limited observations, not a general
accuracy percentage. Neither the private diagnostic nor the independent
holdout has a passing acceptance result.

Earlier hosted notes and short-meeting runs succeeded, but their receipts do not
certify the exact final running Python bytes. The fresh release demo is local.
Source matching alone does not prove semantic correctness, final commitment
status or completeness. Always compare the drafts with the original notes.

The [hosted validation report](hosted-validation.md) preserves successful and
failed runs. The [recovery investigation](draft-recovery.md) is an earlier
checkpoint, not the current publication boundary.

## Processing and licensing

Fresh pages default to local processing. Optional Groq-hosted GPT-OSS 120B sends
the complete submitted source to Groq and may consume paid credit. Keys stay in
server process memory; there is no automatic local/hosted fallback. See
[hosted processing](hosted-processing.md) for the exact behavior.

Application code is MIT licensed. Model weights are downloaded separately and
retain their own licenses. See [model provenance](model-runtime.md). AI agents
implemented, tested and documented the project. Publication of the source and
demo does not establish contest acceptance or milestone credit.
