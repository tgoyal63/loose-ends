# Narrated walkthrough — 22 October 2026

[Watch the tutorial](https://loose-ends-demo.vercel.app/) ·
[MP4](narrated-walkthrough.mp4) · [Captions](narrated-captions.vtt) ·
[Actual Markdown download](narrated-action-list.md) ·
[Evidence and hashes](../evidence/narrated-demo.json)

This 2-minute-28-second walkthrough uses a staged synthetic project handoff and
actual local Qwen3 4B inference. The recorded run returned three drafts and one
rejected suggestion. Mina's complete conditional source remains visible. Priya's
recipient is added by the person editing the draft, and the app marks that change
as “Edited by you.” Checking a task demonstrates list state; it does not perform
the task or establish that a prerequisite was satisfied.

The video combines original-speed recording, labelled screenshot holds,
close-ups, editorial cards, captions and narration. It retains the complete
inference wait, but its edited timeline is not latency evidence. The separate
[original continuous silent recording](release-walkthrough.mp4) is unchanged.
The public page includes chapter navigation and an expandable text transcript.

Synthetic narration was generated locally with
[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), voice `af_heart`, through
[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx).
Model weights: Apache-2.0; engine code: MIT. No hosted speech inference or paid
voice credits were used. The model and voice weights are not bundled here.
Caption boundaries follow the actual synthesized sentence waveforms.

Audio passed 401 programmatic signal, decoding, caption and reproducibility
checks. Local Vibe transcription recovered the substantive script; it produced
minor name/spelling variants. No human listening review is claimed.

The accompanying UI motion is limited to state changes, button feedback and
new-result arrival. Reduced-motion preferences disable the animations. Two
independent reviewers examined the exact UI files: source review found no
material issue and all 149 tests passed; a separate browser review checked normal
and reduced motion, keyboard editing, source/export preservation, mocked failures
and late responses, and 66 responsive states. Mocked browser tests are distinct
from the real local capture above.

Long meetings remain a known weakness. The latest recorded hosted natural-meeting
test found nine of ten expected actions and failed acceptance; this video update
did not rerun or resolve that failure. Source matching is not a completeness or
semantic-correctness guarantee. See [release evidence](../release.md).

## Narration transcript

### 0:00 — Keep the condition with the task

A task can change meaning when its condition disappears. Loose Ends turns notes into editable action drafts, keeping the original source beside each one for review.

### 0:14 — Paste the handoff notes

Here’s a staged, synthetic project handoff with Priya, Leo and Mina. Paste it into Your notes, keeping each action and its condition on one line.

### 0:27 — Choose local processing

Under Process with, choose This Mac, local. Once Local model ready appears, select Find actions. This example uses the local Qwen model.

### 0:46 — Review drafts and attribution

This recorded run produced three drafts; the checks left one suggestion out. Check Owner and Due: Priya has Friday, and Leo has tomorrow. Relative dates stay as written.

### 1:01 — Read the whole condition

Mina’s source says, “If the review passes, Mina will archive the old checklist.” Archiving depends on that review passing. The complete line stays visible with the condition and source.

### 1:18 — Edit with the source attached

To clarify Priya’s draft, select Edit and change Action to “Send the draft to the project team.” Save changes. “Edited by you” identifies your addition; the original quote stays attached.

### 1:36 — Mark done and export

For this demonstration, mark Priya’s task done, then select Export. The Markdown keeps completion, edits and source evidence. Export before closing the tab.

### 1:50 — Understand hosted processing

Hosted Groq is optional. Selecting Find actions there sends the complete submitted text to Groq and may use paid API credit.

### 2:02 — Know what still needs review

Review is still essential: a longer meeting test using hosted processing missed a conditional commitment. A matching quote doesn’t prove every action is correct or present.

### 2:16 — Explore the open source

Loose Ends is an MIT-licensed app using open-weight models under their own licenses. Explore the source and setup guide on GitHub.

