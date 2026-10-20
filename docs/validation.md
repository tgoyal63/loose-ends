# Validation — 20 October 2026

This document records the initial implementation and UI refinement through
`f31d708`. For the later transcript fix and current input behavior, see
[transcript support and validation](transcript-support.md). Historical receipts
below retain their original source fingerprints.

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

Following the UI refinement, an independent reviewer ran
[53 browser assertions](evidence/browser-fixtures.json) through the native T3
preview using explicitly synthetic API responses. They cover keyboard focus and
editing, completion, remove/undo, export, safe text rendering, failed requests,
stale notes, cancellation and late responses, double submission, model
availability, memory-only browser state and responsive widths of 320, 390, 768
and 1,280 pixels. Measurements used the actual browser viewport and scroll width.
With 20 tasks at 1,280 × 800, the primary action's bottom edge was 675 pixels,
so a growing results list did not push the input controls off-screen.

A [focused export regression](evidence/export-regression.json) separately reproduced the original Markdown bug and
verified the correction with a CommonMark renderer. Literal `&amp;`, `&#65;`,
`&copy;`, brackets and a leading list marker now preserve their rendered text.
Browser fixtures do not count as real model inference.

[Axe 4.13.0 checks](evidence/accessibility.json) on the refined UI found
**zero WCAG A/AA violations and zero incomplete checks** in desktop empty,
desktop populated and 320-pixel mobile editing states. The earlier decorative
checkmarks were removed with the empty-state illustration. The desktop and mobile
renders were visually inspected. This is not a full screen-reader audit.

The reviewer also independently rendered the current exported Markdown through
CommonMark: all three source quotes, including compound prerequisites and
literal entities/HTML-looking text, were preserved. A fourth check confirmed
there was no executable script markup. See the
[refinement export receipt](evidence/ui-refinement-export.json).

### Demonstration with actual inference

A [reloaded native-browser run](evidence/browser-real-demo.json) verified that
the fixture harness was absent and called the actual app/model at 07:25 UTC.
Its labelled synthetic garden notes produced four actions in 6.794 seconds.
Full conditional context was retained.
One action was edited, marked done and exported while its original quote stayed
unchanged. No browser errors, external requests or mobile overflow were observed.
The receipt records seven application source hashes: the three UI files match
both independent reviews, and the backend bytes match the previously validated
implementation.

- [Recorded walkthrough, MP4](demo/walkthrough.mp4)
- [Desktop actions](demo/desktop.png), [reviewed actions](demo/desktop-reviewed.png)
  and [mobile layout](demo/mobile.png)
- [Exported Markdown](demo/action-list.md), with only the terminal blank line
  removed; the receipt retains the exact downloaded text.

The video is the unmodified native recorder output of the synthetic demo.
Its encoded duration differs from capture wall time; the cause was not verified,
so it is not used to substantiate latency. No inference result was substituted.
The earlier design's [WebM](demo/archive/initial-walkthrough.webm) is archived
separately. Neither recording establishes a public contest submission.

## Independent review

For the initial implementation, two specialists reviewed the actual source
independently of its authors.
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
application fingerprints matched the initial demo receipt, retained in the
original commit `ddcc5ed`.

### UI refinement review

The interface was subsequently refined into a compact document workspace:
clear sans-serif headings, neutral surfaces, one blue action color and ruled
task entries with visible source annotations. The marketing headline, decorative
empty-state papers and repeated rounded cards were removed. JavaScript changes
are presentation strings; request handling, source validation and export logic
are unchanged.

Two independent reviewers examined this later candidate. The source reviewer
checked the full diff, all DOM bindings, semantics, safe rendering, source
immutability and export behavior. The browser reviewer executed the 53
assertions and accessibility checks above. A potential editor-stretch problem
was corrected and the 20-task geometry was verified. Neither review has an
unresolved material finding. Their final three UI hashes match the current
browser receipts. The 37 backend tests were also rerun and passed.

## Scope of the checks

Source-line matching deliberately rejects cropped quotations and several obvious
uncertainty cues. It cannot recover every cross-line qualification or determine
whether a verbatim phrase is a genuine commitment. Keep an action and its
conditions together on one line, up to 1,200 characters. Relative dates stay
relative; unknown owners and dates remain unknown.

This application and its separately configured model service are intended for
local use. These checks do not turn Python's development HTTP server or MLX-LM's
basic inference server into public internet services.
