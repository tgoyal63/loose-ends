# Draft recovery investigation — 22 October 2026

**Historical recovery checkpoint.** This report preserves the results and release
boundary at that stage. The subsequent hosted runs are in
[hosted validation](hosted-validation.md); the narrower notes-workflow release
is described in [the release report](release.md). Its publication does not resolve
the long-meeting failure recorded here.

**Request handling and source-parser defects are repaired. Long-meeting
extraction accuracy remains unresolved.** A successful response is not evidence
that the model found all the commitments or understood their final status.

## Implemented repairs

- The local client consumes a bounded SSE stream and accepts only a complete
  final answer. Missing stream terminators, output-length stops, malformed
  packets and interrupted connections cannot masquerade as finished drafts.
- One 150-second deadline covers the request and an optional format retry.
  A watchdog interrupts blocked headers and stalled body reads. Only a completed
  empty or malformed document is retried, once, with the original source and
  rules. Valid empty results and source-rejected proposals are not fabricated
  into successful actions.
- The API distinguishes unavailable service, timeout, output limit, empty
  response, invalid JSON and invalid stream responses. Error text does not
  expose upstream content or blame the user for the model's failure.
- Failure and cancellation preserve notes, prior actions, edits and export.
  A late response from a cancelled request cannot overwrite model readiness.
  An initial failure has its own empty state instead of implying there were
  no actions in the notes.
- Transcript checks reject common acknowledgement-only titles and quoted third-party
  promises, including straight/curly single quotes and contractions. Malformed
  quotation handling is bounded rather than quadratic on long input.
- “I'll have to…” can identify the speaker's own commitment. “I'll have Jordan…”
  still cannot attribute Jordan's delegated action to the speaker.
- Model input retains explicit named turn fields, original IDs, complete speech
  and any preamble. The complete supported conversation is still submitted.

No section-processing, automatic status-removal or keyword-candidate fallback
was integrated. A subsequent explicitly selected hosted option is described in
[hosted processing](hosted-processing.md); it does not replace the source checks.

## Verified behavior

The project Python runtime passed **107 unit and HTTP tests**. Real fake-service
tests exercise stream boundaries, total deadlines, retry limits and failure
types; these are distinct from actual language-model accuracy checks.

The independent browser review passed **42 behavior assertions**, including
recovery from 502/503/504 responses, retained edits and exports, cancellation and
stale responses. Accessibility checks found zero violations or incomplete
checks in three tested states, with no horizontal overflow at 320, 390, 768 and
1,280 pixels. These browser response fixtures are explicitly synthetic. See
the [behavior receipt](evidence/recovery-browser.json) and
[accessibility receipt](evidence/recovery-accessibility.json).

All **five ordinary-note cases** passed against the actual restored Qwen3 4B
runtime through the updated local API. Their measured request times were
10.171, 3.882, 1.734, 2.696 and 3.018 seconds. The titles were also inspected;
the result is not inferred merely from task counts. The
[actual notes receipt](evidence/recovery-notes.json) preserves the responses.

A fresh isolated browser also called the actual API with ordinary synthetic
notes: **17 assertions passed**, with three meaningful actions returned in
9.412 seconds. Editing, completion, source preservation and Markdown export
worked. One rejected model suggestion was correctly shown as informational
feedback. See [the actual browser receipt](evidence/recovery-real-browser.json).

The strengthened transcript evaluator checks meaningful action words as well
as owner, timestamp and deadline. Its new synthetic natural meeting includes
ten outstanding commitments, two distant status changes, conditional promises,
demonstrations and conversational filler. Its acceptance checks remain intact.

A final run on the restored Qwen3 4B runtime returned a completed response in
54.748 seconds, but failed the expected-action and conditional-commitment checks.
The [current-runtime failure receipt](evidence/recovery-natural-current.json)
preserves that result. Passing source checks did not establish correct extraction.

## What the model experiments established

Experiments used public model weights and local inference. Private diagnostics
used a credential-redacted, name-anonymized meeting. No private transcript or
private model response belongs in public fixtures, screenshots or evidence.

| Experiment | Observed result | Decision |
| --- | --- | --- |
| Qwen3.5 9B, direct full-meeting extraction | Three of four synthetic transcript cases passed; the natural meeting missed a conditional commitment and retained a cancelled one | Not an accuracy fix |
| Qwen3.5 9B, redacted meeting | Five accepted drafts, seven rejected proposals, 98.601 seconds; important follow-ups still missed | Usable partial output, not completion evidence |
| Qwen3.5 4B, direct extraction | Seven of ten natural-meeting actions; redacted meeting produced one accepted draft and two rejected proposals | Not adopted |
| Reasoning-enabled variants | Repeated total-deadline failures; an extended 9B trial also failed to finish | Not adopted |
| Section extraction | Improved recall in the synthetic meeting; other runs still missed real commitments or proposed demonstration text | Prototype only |
| Subsequent status audit | Could drop a pending conditional action or cite unrelated evidence as cancellation | Automatic removal not integrated |

The 9B model also slowed under repeated requests on the tested 16 GB Mac.
Larger download size or a model appearing in `/v1/models` does not establish
reliable generation. The restored default remains the original pinned Qwen3 4B
instruction model, with the runtime limits documented in
[model-runtime.md](model-runtime.md).

The earlier generic 502 response did not retain enough safe diagnostic detail
to identify its exact historical cause. A terminated background command alone
does not prove why that particular draft failed. The new typed responses and
stream checks make subsequent failures distinguishable.

The [four-case 9B experiment receipt](evidence/recovery-transcript-experiment.json)
retains its failing case. It is experimental evidence, not a successful gate
for the restored runtime. Earlier successful receipts remain historical and
were not overwritten to imply that the new natural-meeting case passed.

## Remaining acceptance work at this checkpoint

The long-meeting accuracy check is still failing, so this report does not mark
the user's full transcript problem resolved or the project ready for publication.
Human review remains necessary, and missed actions are still a material limit.

The user approved optional hosted inference, including provider transmission and
possible API-credit usage. Groq-hosted GPT-OSS 120B is implemented as a separate,
explicit mode. Live hosted notes and short transcripts passed after credential
setup, but full-length synthetic inputs were rejected before extraction.
[The hosted validation report](hosted-validation.md) records the partial success
and remaining failure. The local failure above is not reclassified as a pass.
A strict structured-output
contract can improve format reliability, but the unchanged semantic and
provenance checks must still pass. See [the hosted guide](hosted-processing.md)
for current setup and acceptance status.

All changes and diagnostics remain local. No push, deployment, public post or
Hacktoberfest milestone claim was made.
