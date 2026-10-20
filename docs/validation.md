# Validation — 20 October 2026

This is local development evidence for a new Hacktoberfest Week 3 project.
It does not establish hosted checks, public deployment, contest acceptance,
sticker credit, or general model accuracy.

## Backend behavior

On Python 3.13.16, **37 unit, HTTP and model-client tests passed**:

```sh
.model-venv/bin/python -m unittest discover -s tests -v
node --check web/app.js
```

The tests cover source matching, compound conditions, unknown attribution,
negated/speculative/completed lines, duplicate limits, malformed output,
unpaired Unicode, Python's JSON integer limit, local-origin/Host restrictions,
model outages, concurrent requests, response headers and static-file boundaries.
HTTP tests use a fake model and ephemeral loopback server. They are distinct
from the real inference checks below.

## Real local model

The final five-case evaluation ran through the application and the actual pinned
Qwen3 model on 20 October at 06:43 UTC. **5/5 cases passed** after the independent
review corrections. The [receipt](evidence/model-evaluation.json) contains
responses and checks; the [fixtures](../tests/fixtures/notes_cases.json) contain
the synthetic inputs and expected attribution.

| Case | Outcome | Request time |
| --- | --- | ---: |
| Explicit commitments, a condition and prohibited/completed work | Three expected tasks; one extra proposal rejected | 5.250 s |
| Conditional commitment plus speculative/prohibited text | One expected task with complete conditional context; one extra proposal rejected | 2.140 s |
| No remaining actions | Empty list | 0.287 s |
| Action without owner/date | One task, attribution remains unknown | 1.085 s |
| Action mixed with instruction-injection text | Only the expected action accepted | 1.234 s |

These are single-run observations from a small synthetic set. They measure the
model-plus-validator path, including prompt-cache effects. They do not prove
semantic correctness, comprehensive injection resistance, recall or a latency
guarantee. Raw model proposals are not always acceptable: the validator rejected
extra proposals in two cases. Every resulting task still needs human review.

Reproduce with the services described in [model-runtime.md](model-runtime.md):

```sh
.model-venv/bin/python scripts/evaluate_model.py \
  --output logs/model-evaluation-new-run.json
```

The earlier development runtime smoke test is historical evidence, predating
the full-condition-context correction. It is not substituted for this final run.

## Browser behavior

The frontend specialist ran [46 browser assertions](evidence/browser-fixtures.json) using explicitly synthetic
API responses. They cover keyboard focus and editing, completion, remove/undo,
export, safe text rendering, failed requests, stale notes, cancellation and late
responses, double submission, model availability, memory-only browser state and
responsive widths of 320, 390, 768 and 1,280 pixels.

A [focused export regression](evidence/export-regression.json) separately reproduced the original Markdown bug and
verified the correction with a CommonMark renderer. Literal `&amp;`, `&#65;`,
`&copy;`, brackets and a leading list marker now preserve their rendered text.
Browser fixtures do not count as real model inference.

[Axe 4.13.0 checks](evidence/accessibility.json) found **zero WCAG A/AA violations**
in desktop empty, desktop populated and mobile editing states after correcting
step-number contrast. Two decorative, aria-hidden checkmarks retain an automated
contrast review notice. The desktop and mobile renders were visually inspected.
This is not a full accessibility or screen-reader audit.

### Demonstration with actual inference

A [fresh-context browser run](evidence/browser-real-demo.json) installed no mocks
and called the actual app/model at 06:44 UTC. Its labelled synthetic garden notes
produced four actions in 5.799 seconds. Full conditional context was retained.
One action was edited, marked done and exported while its original quote stayed
unchanged. No browser errors, external requests or mobile overflow were observed.
The receipt records the SHA-256 hashes of the seven application source files.

- [Recorded walkthrough, MP4](demo/walkthrough.mp4) and [original WebM](demo/walkthrough.webm)
- [Desktop actions](demo/desktop.png), [reviewed actions](demo/desktop-reviewed.png)
  and [mobile layout](demo/mobile.png)
- [Actual exported Markdown](demo/action-list.md)

The video is a continuous browser recording of the synthetic demo; the MP4 is a
format conversion of the original WebM. No inference result was substituted.
Neither file establishes a public contest submission.

## Independent review

Two specialists reviewed the actual implementation independently of its authors.
Their initial findings identified incomplete compound conditions, malformed
JSON/Unicode exceptions escaping the API contract, and Markdown export changing
literal source text. Corrections preserve full conditional context, normalize
malformed data to documented responses, and escape literal Markdown punctuation.
Regression tests reproduce the original failures and verify the corrections.

The security/source-fidelity reviewer independently confirmed all 37 tests,
reproduced the corrected failure paths, and recalculated all five final inference
receipts against the current validator. The product reviewer independently
verified seven export-to-CommonMark source-text comparisons, ran 23 extraction
and client tests, and checked the final mobile image, export and browser receipt.
Both reviewers found their material issues resolved. The product review's seven
application fingerprints match the final real-demo receipt.

## Scope of the checks

Source-line matching deliberately rejects cropped quotations and several obvious
uncertainty cues. It cannot recover every cross-line qualification or determine
whether a verbatim phrase is a genuine commitment. Keep an action and its
conditions together on one line, up to 1,200 characters. Relative dates stay
relative; unknown owners and dates remain unknown.

This application and its separately configured model service are intended for
local use. These checks do not turn Python's development HTTP server or MLX-LM's
basic inference server into public internet services.
