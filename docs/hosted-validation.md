# Hosted acceptance checkpoint — 22 October 2026

**Groq works for the tested notes and short meeting. Full-length meeting
extraction remains unresolved.** A successful connection or schema-valid response
does not establish that the user's long-transcript problem is fixed.

The user connected a Groq API key through the local password field. The backend
reported the selected `openai/gpt-oss-120b` model ready. All recorded requests in
this report explicitly used hosted mode. The original expected actions and
source checks were retained.

## Actual hosted results

| Case | Result | Seconds |
| --- | --- | ---: |
| Five ordinary-note cases | All passed; titles and metadata independently inspected | 1.047–2.868 each |
| Fragmented speakers and conditions | All four expected actions, distinct owners and conditions retained | 6.189 |
| Later cancellation and speculation | Correctly returned no remaining actions | 2.976 |
| Long meeting with a commitment at the end | HTTP failure; no extraction returned | 0.119 |
| Natural 120-turn meeting with ten outstanding actions | HTTP failure; no extraction returned | 0.123 |

See [the notes receipt](evidence/hosted-notes.json) and
[the original four-transcript receipt](evidence/hosted-transcripts-initial.json).
The transcript result is **two of four passed**, not a completed acceptance gate.
A [separate natural-meeting diagnostic](evidence/hosted-natural-diagnostic-initial.json)
returned the generic HTTP 503 after 0.400 seconds, following an interval longer
than a minute. The original suite receipt records only `HTTPError`, without the
status code. The source was never
silently shortened or replaced with keyword guesses.

After the user reconnected, a full natural-meeting request through the updated
diagnostics returned application HTTP 502 after **36.133 seconds**. Groq's actual
status was **400**, with a token-per-minute limit of **8,000** and remaining-token
header of **728**. See the [captured diagnostic](evidence/hosted-natural-diagnostic-updated.json).
This was not an observed HTTP 413 size rejection or HTTP 429 rate-limit response.
The status and elapsed time alone do not establish the provider's underlying
failure or how many output tokens were generated.

The subsequent [error-code diagnostic](evidence/hosted-natural-diagnostic-code.json)
returned HTTP 400 with **`json_validate_failed` after 35.100 seconds**. This
establishes the provider-reported structured-generation failure category. It
does not establish why generation failed, whether the output budget was exhausted,
or that the account's TPM limit caused the failure.

The [medium-reasoning candidate at temperature 0](evidence/hosted-medium-natural.json)
also failed: application HTTP 502 after **35.056 seconds**, with no draft. That
receipt does not retain the provider's code, so it cannot independently establish
another `json_validate_failed`. The evaluator now preserves bounded application
error JSON for future synthetic failures; its action expectations and checks
have not changed.

The [medium-reasoning run with recommended sampling](evidence/hosted-sampling-natural.json)
returned a usable draft in **6.472 seconds**: nine accepted actions and zero
source rejections. It still **failed** completeness. The missing commitment is
Ravi Mehta at 10:10:00, to verify Priya's preview account after collection access
is restored, with no deadline. The other nine actions are meaningful and correctly
attributed; the room prerequisite survives and the distant cancelled/completed
work is excluded. Both source and independent reviews retain the ten-action gate.

High reasoning with the same sampling first received
[HTTP 413](evidence/hosted-high-sampling-natural.json) after 0.242 seconds, with
limit/remaining headers both 8,000 and a 12-second retry hint. One manual retry
after 67.6 seconds [returned a draft](evidence/hosted-high-sampling-natural-retry.json)
in **25.074 seconds**, again with nine accepted actions and zero rejections.
Both conditional actions were now present, but Tessa Wynn's 10:21:30 commitment
to prepare large-print task cards by Wednesday was missing. The later completed
pronunciation guide was correctly excluded; the output does not establish why
the distinct pending card task was omitted. This run also failed acceptance.

The [compact-input coverage candidate](evidence/hosted-coverage-natural.json)
returned nine accepted actions with zero rejections in **21.828 seconds**.
The large-print cards were present, but the conditional account-verification
commitment was again missing. The other nine actions, room prerequisite and
completed/cancelled exclusions were correct. The generic internal-inventory
instruction therefore did not establish complete extraction. The frozen
ten-action gate remains failed; the separate holdout has not been invoked.

An isolated real browser submitted the short synthetic meeting and returned all
four expected actions in **4.388 seconds**, with zero rejected proposals.
**22 browser checks and six export checks passed**: meaningful action text,
speaker attribution, dates, qualifications, exact original source, nearby
conversation, human edits, completion and actual Markdown download. Switching
back to local mode retained the hosted result's original model attribution.
See [the live browser receipt](evidence/hosted-real-browser.json).
The user's Zen tab and key configuration were not changed by browser testing.

All published sources and receipts are synthetic. No private meeting transcript
or private output is included. The approved redacted private diagnostic has not
yet been submitted to Groq while the full-length request rejection is unresolved.

## Diagnosis and correction

The previous client collapsed provider failures other than authentication and
rate-limit errors into a generic unavailable response. Therefore the observed
HTTP 503 does **not** establish which status Groq actually returned.

The corrected client distinguishes provider HTTP 413 (request too large),
400/422 (request rejected), 401/403 (authentication/permission), and 429 (rate
limit). It retains the provider status and only three numeric rate-limit headers.
Keys, request IDs, organization IDs and arbitrary headers are never reflected.
The interface preserves notes, edits, export and
readiness after a size rejection. Eight additional mocked browser checks verify
that behavior in [this receipt](evidence/hosted-input-limit-browser.json).

The full test suite now passes **149 tests**. Two independent reviewers examined
the diagnostics change and tested the header filter, error classification and
unchanged privacy boundaries. The earlier
[implementation receipt](evidence/hosted-implementation.json) is a historical
checkpoint from before live hosted testing and the diagnostics correction; its
142-test count and credential-pending state are not the current result.
The provider behavior follows
[Groq's documented error codes](https://console.groq.com/docs/errors).

The user supplied the account's current limits: 30 requests/minute, 1,000
requests/day, 8,000 tokens/minute and 200,000 tokens/day for GPT-OSS 120B. The
provider header independently confirms 8,000 TPM. An account-limit cause is
still unproven: the captured failure was HTTP 400. See
[Groq's rate-limit documentation](https://console.groq.com/docs/rate-limits)
and [organization limits](https://console.groq.com/settings/limits).

## Remaining work

The implemented diagnostic adds a narrow exception to the previous no-body-read policy:
read at most 64 KiB plus one overflow byte for HTTP 400/422, parse complete JSON
and return only a recognized `error.code` from a fixed allowlist. The read has a
three-second cap within the request deadline; any diagnostic failure preserves
the original HTTP status. Messages, generated content and unknown values are
never logged, returned or attached to exceptions. Other error bodies remain
unread.

The next candidate keeps high reasoning, temperature 1.0 and top_p 1.0. These sampling settings match the
[model maintainer's recommended sampling parameters](https://github.com/openai/gpt-oss#recommended-sampling-parameters).
The hosted input now maps each parsed turn ID to an exact original source block,
with a separate preamble. Rejoining the preamble and blocks reproduces every
source character, including whitespace, empty-header gaps and the final text.
The hosted prompt extends the existing rules with a general chronological
commitment inventory and a final-status check tied to each distinct action/object.
Completing one item does not complete other work by its speaker; unmet
prerequisites do not cancel conditional promises. No fixture-specific names,
counts or targeted examples were added. Strict JSON, the 16,384-token output
budget, validators, local processing and frozen acceptance expectations remain
unchanged. The change adds no second model call. Its first live result is the
failed nine-action coverage run above. The app remains connected; no further
restart or provider call has been made for a new approach at this checkpoint.

Evaluate the candidate and rerun all four frozen transcript cases. The natural meeting still requires
exactly ten meaningful actions and both conditional commitments. Then run the
separate synthetic holdout, repeat the natural case through the real browser,
and run the approved redacted private diagnostic. Assess the actual follow-ups against
the full conversation. No final commit, publication or deployment is claimed
at this checkpoint.
