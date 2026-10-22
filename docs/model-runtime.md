# Local open-model runtime

The local runtime uses
[`mlx-community/Qwen3-4B-Instruct-2507-4bit`](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit),
a community MLX conversion of
[`Qwen/Qwen3-4B-Instruct-2507`](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
The upstream model is Apache-2.0 licensed. This is a text-only instruction model.

The pinned conversion revision is
`50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`, a roughly 2.28 GB snapshot.
This is an optional local model download, separate from the application source.
Local mode uses no API key or paid inference service. The separately selected
[optional hosted mode](hosted-processing.md) uses Groq and requires an API key.

The 2026-10-22 investigation found that this model is not reliable on every
long natural meeting. Qwen3.5 4B and 9B variants also missed actions; the 9B
variant's repeated-request latency was unsuitable on the tested 16 GB Mac.
They were not adopted as a validated upgrade. See [the recovery report](draft-recovery.md).

## Tested environment

The local checks on 2026-10-22 used an Apple Silicon Mac with 16 GB of unified
memory, macOS 27.0.1, and a project-local Python 3.13.16 virtual environment.

| Package | Tested version |
| --- | --- |
| `mlx-lm` | `0.32.2` |
| `mlx` / `mlx-metal` | `0.32.4` |
| `transformers` | `5.20.2` |
| `huggingface-hub` | `2.2.0` |
| `numpy` | `2.5.4` |
| `safetensors` | `0.8.0` |
| `tokenizers` | `0.23.3` |

These versions describe the tested runtime, rather than a claim that other
versions or hardware have been validated. MLX uses Apple Silicon acceleration;
this procedure is for a compatible Mac.

## Install and download

From the project root, create an isolated environment with
[`uv`](https://docs.astral.sh/uv/):

```sh
uv venv --python 3.13 .model-venv
uv pip install --python .model-venv/bin/python \
  'mlx-lm==0.32.2' 'mlx==0.32.4' 'mlx-metal==0.32.4' \
  'transformers==5.20.2' 'huggingface-hub==2.2.0' \
  'numpy==2.5.4' 'safetensors==0.8.0' 'tokenizers==0.23.3'
```

Download the public model revision and retain the returned cache path:

```sh
LOOSE_ENDS_MODEL_PATH="$(
  HF_HUB_DISABLE_IMPLICIT_TOKEN=1 .model-venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download(
    repo_id="mlx-community/Qwen3-4B-Instruct-2507-4bit",
    revision="50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b",
    token=False,
))
PY
)"
export LOOSE_ENDS_MODEL_PATH
```

The first download needs internet access and approximately 2.3 GB of disk space,
plus the Python runtime and packages. Model files are stored in the ordinary
Hugging Face cache. The `token=False` argument avoids sending an existing Hub
credential for this public download.

## Start inference

Check that the chosen port is free before starting a new process:

```sh
lsof -nP -iTCP:62141 -sTCP:LISTEN
```

If a listener exists, identify its owner; reuse the intended model service or
choose another port instead of terminating an unrelated process.

Run the model server in a dedicated terminal:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  .model-venv/bin/mlx_lm.server \
  --model "$LOOSE_ENDS_MODEL_PATH" \
  --host 127.0.0.1 --port 62141 \
  --allowed-origins http://127.0.0.1:62140 \
  --decode-concurrency 1 --prompt-concurrency 1 \
  --prefill-step-size 256 \
  --prompt-cache-size 0 --prompt-cache-bytes 128MB \
  --max-tokens 4800 --temp 0
```

The downloaded snapshot is loaded by path so this run remains on the pinned
revision. Offline flags prevent model-library downloads during inference.
One concurrent request and no retained completed prompt caches reduce memory
demand between meetings. Long active requests still use a KV cache; these settings
do not constitute a total process-memory limit. Disabling retained caches also
avoids copying a previous long meeting's cache before trimming it for the next
request. It trades cross-request reuse for more predictable memory use.

The API base URL is `http://127.0.0.1:62141/v1`. In this configuration
`GET /v1/models` advertises the resolved snapshot path as its model ID. Supply
that path to the application's model option, and use
`Qwen3 4B Instruct · local` as its separate display label. The server also recognizes the
`default_model` request alias, but does not list that alias in `/v1/models`;
the advertised path works with the application's exact readiness check.

```sh
curl --fail http://127.0.0.1:62141/health
curl --fail http://127.0.0.1:62141/v1/models
```

Stop a foreground server with Control-C. For the supervised development run,
the ignored `logs/model-qwen3-chunk-runtime.json` records its PID and command.
Verify that PID still belongs to this model server before sending
it `SIGTERM`; process IDs can be reused.

## API behavior and validation

MLX-LM provides an OpenAI-compatible chat-completions shape:
`POST /v1/chat/completions`, a `messages` array, and generated text under
`choices[0].delta.content` in streamed responses. The application assembles the
stream internally and returns a complete validated list to the browser.
Temperature remains zero, with a 2,400-token output cap for ordinary notes and
4,800 for transcripts. It requires both a successful stop and the final stream
marker; truncated results are never presented as completed drafts.

The total deadline is 150 seconds, including at most one format retry for a
completed malformed or empty response. A watchdog closes the upstream socket
when the deadline expires, including while waiting for headers or a slow stream.
Connection failures, truncated output and valid empty action lists are not
retried. The browser has a separate 180-second waiting limit.

The app accepts up to 60,000 input characters. Every transcript turn is included
as a named JSON object with its ID, speaker, timestamp and complete text.
A format retry retains that entire source. The input bound is not a
guarantee of processing latency or model accuracy at that length.

MLX logs HTTP 200 when it accepts generation, before completion. With nonstream
requests, an abandoned client can leave generation running until the final body
write. Stream closure lets MLX detect disconnection at a subsequent write; it
does not guarantee immediate cancellation of queued GPU work. The status endpoint
confirms the selected model is listed, not that every request will finish.

Inspection of the installed 0.32.2 server and its
[tagged source](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/server.py)
found no `response_format` or JSON-schema generation enforcement. Loose Ends
therefore requests JSON in the prompt, parses the returned document, and
validates its task fields against the original notes. Schema conformance and
correct source attribution must not be assumed from a successful HTTP response.

The upstream
[server documentation](https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/SERVER.md)
describes this as a basic local server rather than a production-hardened service.
Keep it bound to loopback. The application communicates with it from the local
backend; no public model endpoint or authentication layer was deployed.

## Initial 4B inference evidence (historical)

The initial 2026-10-20 checks below used
[`mlx-community/Qwen3-4B-Instruct-2507-4bit`](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit),
revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b` (a 2.28 GB snapshot).
Later long-meeting checks exposed missed commitments and incorrect action
selection with that runtime. Further local model experiments are recorded
in [draft-recovery.md](draft-recovery.md). Successful transport alone
does not establish extraction quality.

Before the review corrections, three synthetic cases were submitted to the running model, with the resulting
JSON passed through the application's validator. All three produced the expected
accepted source-line set:

| Case | Accepted result | Additional observation | Request time |
| --- | --- | --- | --- |
| Two explicit commitments plus completed work | Two tasks, original owners, one explicit Friday deadline | Completed work omitted | 5.264 s |
| Conditional commitment, unassigned action, speculative idea | Conditional task retained with its condition; unassigned task kept without invented owner/date | Model proposed the speculative idea; validator rejected that third proposal | 2.952 s |
| Instruction-injection text, question, completed work and prohibition | Empty task list | No invented commitments accepted | 0.288 s |

The first request used 328 prompt tokens and generated 103 tokens. Later requests
benefited from prompt-cache reuse. These timings are measurements from this
development machine, not performance guarantees.

The cases confirm real local inference and exercise the model-plus-validator
path. They are a small smoke test, not a comprehensive accuracy, security or
model-comparison benchmark. The model's speculative proposal demonstrates why
human review and validation remain necessary. Literal source matching cannot
prove semantic correctness; wording, conditional scope and implied assignments
can still be misunderstood.

Development evidence is retained under ignored `logs/model*` files:

- `model-runtime.json`: service command, local paths and PID.
- `model-download.json`: revision, downloaded sizes and SHA-256 hashes.
- `model-versions.json` and `model-requirements.txt`: installed runtime versions.
- `model-models-response.json`: actual model-list response.
- `model-smoke.json`: synthetic requests, raw responses, accepted tasks,
  rejection counts, prompt hash and timings.
- `model-server.log`: local server diagnostics.

These files are development receipts and are not required to run the application.
They contain machine-specific paths; publish a reviewed summary rather than
copying local runtime logs wholesale.

The later review changed accepted conditional metadata to preserve the entire
original source line as context. The three-case smoke receipt above describes
the earlier validator. See [validation.md](validation.md) and its final five-case
receipt for the corrected application.
