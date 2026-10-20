# Local open-model runtime

Loose Ends was exercised with real inference from
[`mlx-community/Qwen3-4B-Instruct-2507-4bit`](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit),
a community MLX conversion of
[`Qwen/Qwen3-4B-Instruct-2507`](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
Both model cards identify the license as Apache-2.0. The upstream model is a
4-billion-parameter, non-thinking instruction model; the conversion stores its
weights at 4-bit precision.

The pinned conversion revision is
`50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`. Its weight file is
2,263,022,417 bytes; the complete downloaded snapshot is 2,278,972,236 bytes.
This is an optional local model download, separate from the application source.
No API key or paid inference service is used.

## Tested environment

The local checks on 2026-10-20 used an Apple Silicon Mac with 16 GB of unified
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
  --prompt-cache-size 1 --prompt-cache-bytes 128MB \
  --max-tokens 2400 --temp 0
```

The downloaded snapshot is loaded by path so this run remains on the pinned
revision. Offline flags prevent model-library downloads during inference.
One concurrent request and a bounded retained prompt cache reduce memory demand;
these settings do not constitute a total process-memory limit.

The API base URL is `http://127.0.0.1:62141/v1`. In this configuration
`GET /v1/models` advertises the resolved snapshot path as its model ID. Supply
that path to the application's model option, and use
`Qwen3 4B · local` as its separate display label. The server also recognizes the
`default_model` request alias, but does not list that alias in `/v1/models`;
the advertised path works with the application's exact readiness check.

```sh
curl --fail http://127.0.0.1:62141/health
curl --fail http://127.0.0.1:62141/v1/models
```

Stop a foreground server with Control-C. For the supervised development run,
the ignored `logs/model-runtime.json` records its PID, start time, command and
stop command. Verify that PID still belongs to this model server before sending
it `SIGTERM`; process IDs can be reused.

## API behavior and validation

MLX-LM provides an OpenAI-compatible chat-completions shape:
`POST /v1/chat/completions`, a `messages` array, and generated text under
`choices[0].message.content`. The application uses non-streamed requests,
temperature zero and a 2,400-token output cap for ordinary notes. Transcript
requests use a 4,800-token output cap and the same 120-second client timeout.
The app accepts up to 60,000 input characters; the whole transcript is included
in one request. The retained cache setting above is not an input-context limit.

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

## Initial real inference evidence

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
