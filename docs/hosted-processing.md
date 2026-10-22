# Optional hosted processing

The user approved optional hosted inference on 22 October 2026, including sending
submitted notes to the provider and possible paid API-credit usage. This adds
Groq-hosted `openai/gpt-oss-120b` alongside the existing local model. Actual hosted
inference passed all five ordinary-note cases, the short transcript checks, and
a real browser flow. **Long-meeting acceptance remains unresolved: the latest
natural-meeting run returned nine of ten expected actions.** See
[the live validation report](hosted-validation.md). Local long-meeting failures
remain documented in [the recovery report](draft-recovery.md).

## Setup and use

1. Run the local application with Python 3.11+: `python3 server.py`. A local
   model process is needed only when using local inference.
2. Create a dedicated API key in [Groq Console](https://console.groq.com/keys).
   Review that account's model access, usage limits and data controls.
3. Open `http://127.0.0.1:62140`, select **Hosted · Groq**, and enter the key in
   the local password field. Never put a real key in chat, a command argument,
   source control, a screenshot or a shared artifact.
4. Check readiness, then submit notes using **Find actions**. Setup and readiness
   checks do not submit notes. Hosted processing sends the entire supported input
   to Groq and may consume API credit.
5. Switch to local processing when desired. There is no automatic fallback.
   Disconnect hosted setup to remove the stored key, or stop the app process.

The password field is cleared on submission. The backend holds the key only in
process memory; it is not returned by the API, stored in browser storage or files,
or included in application logs and exports. Restarting the app clears an
in-app key. A local trusted process/user can still access this local service;
loopback restrictions are not operating-system user isolation.

For launchers that already supply a key securely through the process environment,
`python3 server.py --hosted-groq` reads `GROQ_API_KEY`. No environment files are
loaded. Without this flag, an inherited key is ignored. Requests still default
to local mode even when a hosted key is configured.

Keep unsaved work in the existing tab until exported: refreshing clears it.
Open a fresh tab for the updated interface. Modes and API keys are not stored in
the browser; every fresh page starts in local mode. A result keeps the model
label from its actual extraction when you switch modes or export it later.

## Provider contract

The separate hosted client uses only
`https://api.groq.com/openai/v1/chat/completions`, with normal certificate
verification and server-side Bearer authentication. It does not follow redirects,
use environment proxies, accept arbitrary destinations, or share the key with
the local model. Readiness queries the provider's `/models` endpoint; it does
not prove that the account has enough quota for a particular transcript.

Requests use `stream:false`, strict JSON schema, `reasoning_effort:high`,
`temperature:1.0`, `top_p:1.0`,
`include_reasoning:false`, and `max_completion_tokens:16384`. Groq does not
support streaming combined with Structured Outputs, and GPT-OSS does not support
its general `reasoning_format` parameter. These choices follow the
[structured-output contract](https://console.groq.com/docs/structured-outputs),
[GPT-OSS reasoning guide](https://console.groq.com/docs/reasoning), and
[API reference](https://console.groq.com/docs/api-reference). The model's
[published limits](https://console.groq.com/docs/model/openai/gpt-oss-120b) are
separate from account-level quota.

Live acceptance of this combination is pending. The prior high setting returned
`json_validate_failed` on the full natural meeting despite strict mode; medium
reasoning alone also failed with HTTP 502 and no draft. Both used temperature 0.
Medium reasoning with [OpenAI's recommended GPT-OSS sampling](https://github.com/openai/gpt-oss#recommended-sampling-parameters)
of temperature 1.0 and top_p 1.0 returned a valid draft in 6.472 seconds, but missed
one of ten actions: account verification after an access repair. The current
high-reasoning run with those settings also returned nine actions, recovering
the account action but omitting another pending task. The current candidate
uses a more compact hosted-only input: an ordered map from parsed turn IDs to
exact original source blocks, plus the preamble. Concatenating these reconstructs
every source character. The prompt adds a generic inventory and final-status
check for each distinct work item, including blocked conditional commitments.
Sampling, strict schema, output budget, validators and the local path remain
unchanged. No source is removed and no second paid pass is added. This is not
yet evidence of a long-meeting fix or proof of why prior actions were omitted.

The input is never silently shortened. A 150-second request deadline and a
512,000-byte response bound apply. DNS, TCP and TLS setup run in a bounded
connection-only worker; a stalled resolver cannot retain the inference slot past
the deadline. At most four setup workers may remain outstanding. A late worker
closes its connection and never sends HTTP headers, credentials or notes.
Only a single completed `stop` response is
eligible for JSON parsing and the existing source validator. Truncated, refused,
empty, malformed or interrupted responses fail explicitly. Authentication and
rate-limit failures have safe messages. A provider HTTP 413 is distinguished
from temporary unavailability; HTTP 400/422 identifies request rejection.
Error details may include the provider HTTP status and three strictly bounded
numeric headers: token limit, remaining tokens and retry delay. For HTTP 400/422
only, the client may read at most 64 KiB plus one overflow byte and parse complete
JSON for a recognized error code. This optional read has a three-second cap within
the total request deadline. Only exact allowlisted code values are returned;
messages, generated content and unknown fields are discarded. Malformed,
oversized or interrupted diagnostics preserve the original HTTP status.
Other error bodies remain unread, and arbitrary headers are not exposed.
There are no automatic hosted retries or provider fallbacks. Stopping browser
waiting does not guarantee that provider computation or billing stops.

Strict schemas address format, not semantic accuracy. Owners, deadlines,
conditions, later cancellations and omissions still need checking against the
full conversation. Source validation is unchanged for either processing mode.

## Provider data handling

Groq's [data controls](https://console.groq.com/docs/your-data) describe limited
retention exceptions for reliability and abuse investigations, generally up to
30 days, with longer periods possible when legally required. Organization admins
can enable Zero Data Retention. This app does not inspect or change that setting
and does not promise unconditional zero retention. The
[services agreement](https://console.groq.com/docs/legal/services-agreement)
requires explicit customer permission for training on customer data. Review the
current provider terms and account settings for your intended notes.

## Acceptance checks

The local implementation passed **149 unit, HTTP and transport tests**, including
31 isolated hosted transport cases using synthetic credentials and a loopback
fake service. These cover the fixed destination, no redirects/proxies/fallback,
strict response completion, output bounds, safe errors, total deadlines and late
connection cleanup. They do not establish real provider acceptance.

Two independent source/backend reviewers found no remaining material
implementation issue after the DNS/TLS deadline correction. The reviewer who
authored earlier transcript-parser changes excluded those from their independent
verdict; the other reviewer separately verified them. Both kept live provider and
meeting-quality acceptance unresolved.

The interface passed [24 hosted-mode behavior checks](evidence/hosted-browser.json)
and [42 existing recovery checks](evidence/hosted-recovery-browser.json).
[Accessibility checks](evidence/hosted-accessibility.json) found zero violations
and incomplete checks across four tested states, with no horizontal overflow
at 320, 390, 768 and 1,280 pixels. These browser responses were mocked.

An independent UI reviewer reran both suites and passed
[31 additional edge cases](evidence/hosted-independent-browser.json), for
97 distinct browser checks. Their separate
[accessibility/viewport checks](evidence/hosted-independent-a11y.json) also passed.
The [initial implementation receipt](evidence/hosted-implementation.json) preserves
the earlier source hashes and 142-test result before live hosted testing and the
diagnostics correction. Its credential-pending state is historical. See the
[current validation checkpoint](hosted-validation.md) for the 149-test result and
partial live acceptance.

All [five ordinary-note cases](evidence/hosted-change-local-notes.json) also passed
through the actual restored Qwen3 4B service and the updated app's explicit local
mode. This verifies local regression behavior, not hosted extraction quality.

The [actual hosted notes](evidence/hosted-notes.json) passed all five cases with
independent inspection of meaningful titles, owners, dates and conditions.
The [actual browser run](evidence/hosted-real-browser.json) returned all four
expected short-meeting actions in 4.388 seconds; 22 browser and six export
checks passed. Eight [mocked input-limit recovery checks](evidence/hosted-input-limit-browser.json)
also passed. Full-length inputs remain an open acceptance failure, rather than
an inferred semantic or account-limit diagnosis.

After configuring the key in the app, reproduce the unchanged synthetic cases:

```sh
.model-venv/bin/python scripts/evaluate_model.py --mode hosted \
  --output logs/hosted-notes.json
.model-venv/bin/python scripts/evaluate_transcripts.py --mode hosted \
  --output logs/hosted-transcripts.json
```

The transcript cases include all ten outstanding actions in a 120-turn natural
meeting, explicit conditional promises, distinct speakers, a long input tail,
and distant cancellations/completions. Passing transport or mock tests does not
establish that these real-model checks pass. Private diagnostic transcripts and
outputs must remain under ignored `logs/`; public fixtures and receipts use
synthetic content only.
