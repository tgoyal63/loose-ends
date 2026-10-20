# Transcript support and validation — 20 October 2026

## What failed

The original interface accepted only 12,000 characters through a native
`maxlength`. A longer paste could therefore lose its ending before submission.
Its extractor also required every action, owner, deadline and condition to
occur on one original line. Speaker headers and wrapped speech do not fit that
contract. A completed request could consequently return only rejected proposals.

Actual local-model testing found a second representation problem: the model
sometimes wrote the string `"null"` for missing metadata. Those unknown values
were treated as unsupported source text. Asking the model to generate a
condition summary also discarded valid actions when it mistook completed work
for a prerequisite.

## Implemented behavior

- Notes and transcripts accept up to 60,000 Unicode code points. An oversized
  paste remains intact, with an explicit error; it is not silently truncated.
- A `Speaker Name HH:MM:SS` header followed by speech activates transcript
  extraction automatically. The original multiline turn is retained.
- The model reads the complete supported conversation and selects a turn ID,
  source-matching action text, owner and due date. It does not generate the
  attached quote or a condition summary.
- The server reconstructs the exact original turn, preserves detected conditions
  from the action's sentence, and attaches a contiguous excerpt with up to two
  turns on either side. Nearby context remains available when an optional model
  condition is absent.
- First-person attribution must support the selected action. Quoted speech,
  another person's intervening promise and delegated subactions cannot simply
  inherit the current speaker's name. Ambiguous owners can remain unknown.
- Literal string-null sentinels normalize to unknown only in transcript optional
  metadata. Forged nonempty fields, invented source IDs and unmatched text still
  fail validation. A prerequisite alone cannot become an action.
- The UI displays the speaker, timestamp, complete source and expandable nearby
  conversation. Human edits retain that evidence; Markdown exports retain it too.
- Empty-result messaging distinguishes a completed request with rejected drafts
  from a finding that there is nothing left to do.

The ordinary-note validation path remains intact, including its complete-line
source rule and conditional-context safeguards. No cloud fallback, persistence
or external action was introduced.

## Verification

**73 unit, HTTP and model-client tests passed.** The original multiline regression
and independently discovered ownership failures were reproduced before their
corrections. An independent source reviewer additionally passed 54 focused
checks against the final validator.

The independent browser review passed **52 behavior assertions** and **8
CommonMark export assertions**. These exercised synthetic responses, full paste
retention, Unicode boundaries, exact evidence, edits, undo, stale text,
cancellation, error recovery and legacy notes. Measured widths of 320, 390, 768
and 1,280 pixels had no horizontal overflow. Axe 4.12.1 found zero WCAG A/AA
violations and zero incomplete checks in three tested states.

The [browser fixture receipt](evidence/transcript-browser.json),
[export receipt](evidence/transcript-export.json) and
[independent source checks](evidence/transcript-source-review.json) record those
checks separately.

Native browser automation failed twice with
`Preview automation snapshot timed out after 15000ms.` Testing used an isolated
Playwright CLI browser without changing the application CSP or installing a new
browser. This tooling failure was distinct from the product defect.

### Actual local inference

The final candidate passed all three synthetic transcript cases through the
running application and pinned local Qwen3 model:

| Case | Result | Observed request time |
| --- | --- | ---: |
| Fragmented speech, separate speakers and prerequisites | Four expected actions; owners, dates and adjacent conditions preserved | 28.577 s |
| 21,768-character meeting | Five expected actions, including the final commitment beyond the old input limit | 62.822 s |
| Later cancellation and speculative discussion | No remaining actions | 11.865 s |

The [transcript receipt](evidence/transcript-model.json) combines these three
final individual case executions on the same source. The
[five existing notes cases](evidence/notes-after-transcript.json) also passed
through that candidate. They are separate from mocked browser and HTTP tests.

Earlier development attempts exposed rejected null sentinels, an unsupported
prerequisite task, and a missed conditional commitment. The final prompt and
validator were refined using those failures; the final fixture results are not
an independent model benchmark or a guarantee of accuracy on other meetings.

### Real-model browser flow

A separate fresh browser session used the synthetic meeting fixture with no
mocked responses. It returned all four expected actions in **16.770 seconds**.
**20 browser assertions** and **10 CommonMark export checks** passed. Editing,
completion and export retained the exact source turns and nearby prerequisites.
No runtime errors, external resource requests or browser storage were observed.

See the [actual browser receipt](evidence/transcript-real-browser.json),
[export checks](evidence/transcript-real-export.json),
[downloaded Markdown](demo/transcript-actions.md), and
[desktop](demo/transcript.png) / [mobile](demo/transcript-mobile.png) captures.

Reproduce with both local services running:

```sh
.model-venv/bin/python -m unittest discover -s tests -q
node --check web/app.js
.model-venv/bin/python scripts/evaluate_transcripts.py
.model-venv/bin/python scripts/evaluate_model.py
```

All published fixtures and receipts use synthetic meetings. The user's private
transcript and credentials were not added to the repository or used in demos.

## Limits and recovery

Recognition currently supports the implemented name-plus-24-hour timestamp
format, not every transcript export or numbered speaker label. Up to 20 drafts
are returned. The 60,000-character bound is an input acceptance limit, not a
latency or context-capacity guarantee for every model. Requests retain bounded
timeouts and report failures; there is no silent chunk omission.

Exact text matching establishes provenance, not complete semantic correctness.
The model may miss commitments or misunderstand a distant cancellation,
qualification, owner or date. The attached nearby excerpt may not contain every
relevant earlier or later statement. Review the full conversation where needed;
relative dates remain relative.

After updating from the original interface, reload and paste the full source
again. Text already cut off by the old input limit cannot be recovered from the
truncated text box. Unsaved notes and drafts are cleared by a page reload.

This is local implementation and validation evidence. It does not establish
public deployment, challenge submission or Hacktoberfest credit.
