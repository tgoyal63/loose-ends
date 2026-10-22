# Loose Ends

**Historical initial brief — October 20, 2026.** The scope and API limits below
describe the first version. The current app also supports timestamped transcripts
and explicitly selected Groq inference, with a 60,000-character input limit.
See [the README](README.md) and [October 22 release scope](docs/release.md) for
current behavior and known limitations.

New project started October 20, 2026 for Hacktoberfest Week 3, “Slow and Steady.”

Turn scattered notes into a small, editable action list using a locally running
open-weight model. The useful shortcut is finding actionable text and its context,
not inventing commitments. Each proposed task retains an exact source quote.
Users review and edit before exporting; nothing is sent or scheduled.

## Scope

- Paste notes or load a clearly labelled synthetic example.
- Local inference, honest connection/loading/error/empty states.
- Exact-substring validation of task titles and source quotes; attributed owner,
  due text and conditions must also occur in the quoted source.
- Preserve the whole source line as context for detected conditional tasks.
- Conservative rejection of obviously negated, speculative or completed work.
- Editable task cards with original quotes, completion toggles and Markdown export.
- No account, database, analytics, browser persistence, external model service,
  automatic execution or calendar integration.

The model proposes drafts. Verbatim evidence and conservative filters reduce
unsupported output; they do not establish semantic entailment or guarantee that
every real action is found. Ambiguous notes need human review.

## Ownership and contracts

Coordinator owns `server.py`, `loose_ends/`, `tests/`, repository setup and docs.
Frontend specialist owns `web/`. Model specialist owns `.model-venv/`,
`logs/model*` and `docs/model-runtime.md`. Independent reviewers write reports
outside the source tree. No other repository or browser profile is modified.

`GET /api/status`: `{ready, model, message}`.

`POST /api/plan` accepts `{notes}` and returns
`{tasks:[{id,title,owner,due,condition,quote}],rejected_count,model}`.
Errors use `{error:{code,message}}` and appropriate non-success HTTP status.
Notes are limited to 12,000 characters.

Application listens on `127.0.0.1:62140`. The separate local OpenAI-compatible
model server listens on `127.0.0.1:62141`. Neither is exposed publicly.

## Completion evidence

Unit and HTTP behavior tests; actual local open-model inference on synthetic
cases; desktop/mobile and keyboard checks; a real demonstration; two independent
reviews resolved before the local commit. A DEV draft accurately discloses AI
authorship and links only to artifacts that actually exist.

Publishing a reviewed entry and attending three real livestreams remain separate
milestone steps. Local implementation does not itself earn a Hacktoberfest sticker.
