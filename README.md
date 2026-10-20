# Loose Ends

Turn scattered notes into an editable action list, with the source kept beside
every task. Loose Ends uses an open-weight language model running on your own
machine. It does not send messages, schedule tasks or act on your behalf.

Built for Hacktoberfest 2026 Week 3, **Slow and Steady**.

![Loose Ends showing source-backed action drafts](docs/demo/desktop.png)

[Watch the local-model demo](docs/demo/walkthrough.mp4) ·
[See validation evidence](docs/validation.md)

## Run

The web application needs Python 3.11 or later and no third-party Python packages.
The model service is a separate local process.

1. Start the pinned local model using [the runtime instructions](docs/model-runtime.md).
2. Use the exact model ID returned by that service's `GET /v1/models` endpoint:

   ```bash
   .model-venv/bin/python server.py \
     --model-base-url http://127.0.0.1:62141/v1 \
     --model 'YOUR_ADVERTISED_MODEL_ID' \
     --model-label 'Qwen3 4B Instruct · local'
   ```

3. Open **http://127.0.0.1:62140**.

The command uses the Python environment created by the MLX runtime instructions;
an existing Python 3.11+ installation also works for the application.

Use a note with each action and its conditions on one line. Load the labelled
synthetic example to try it without personal data. Review the draft, edit or
remove tasks, then export Markdown. Editing a card keeps the original source
quote and marks the task as human-edited.

An OpenAI-compatible local model server is required. This project does not use
the OpenAI service, require an API key or silently fall back to a cloud provider.
The example runtime uses MLX on Apple silicon; other compatible loopback servers
can be configured explicitly. Verify their response format and model IDs.

## What the checks establish

The model identifies potential actions and returns structured text. A separate
validator rejects invented quotations, rewritten titles, cross-line attribution,
duplicates and several obvious negated, completed or speculative phrases.
Quoted evidence must be an entire original source line, at most 1,200 characters.
For detected conditional tasks, the condition/context field preserves that whole
line so a shortened model phrase cannot drop another prerequisite.

These checks reduce unsupported output. They do **not** prove every task follows
from its source, detect every form of negation, recover context from every earlier
paragraph, or find every valid action. Relative dates remain relative. A missing
owner or date stays unknown. Human review is part of the workflow.

## Privacy and boundaries

- The app and model listen on loopback only; no public deployment is required.
- Notes, drafts and edits stay in browser/request memory until you export.
- The application does not store notes, use analytics, load a CDN or write request
  contents to access logs.
- Export creates a local file. Closing/reloading the page clears the unsaved draft.
- The separately configured model service has its own behavior; inspect its
  logging and settings before using sensitive material.
- Model output and pasted content render as text, not HTML.
- Requests from another website are rejected; the local model client rejects
  remote URLs, credentials, redirects and environment proxy routing.

## Validate

```bash
python3 -m unittest discover -s tests -v
node --check web/app.js
```

With both local services running, evaluate five synthetic source-fidelity cases:

```bash
python3 scripts/evaluate_model.py --output logs/model-evaluation.json
```

This is a small reproducible check, not a universal model benchmark. Real model
results and browser evidence are recorded separately from tests using a fake
model. See [validation](docs/validation.md) for the final measured results.

## Open development

Application code is MIT licensed. The selected model retains its own license;
model provenance, revision and runtime package versions belong in
[model-runtime.md](docs/model-runtime.md). The weights are not bundled here.

AI agents assisted with implementation, tests and documentation. The contest
article must disclose its actual authorship separately. No claimed personal
experience, performance result or milestone credit should be inferred from this
repository.
