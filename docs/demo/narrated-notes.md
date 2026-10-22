# Narrated walkthrough — 22 October 2026

[Watch the tutorial](https://loose-ends-demo.vercel.app/) ·
[MP4](narrated-walkthrough.mp4) · [Optional captions](narrated-captions.vtt) ·
[Actual Markdown download](narrated-action-list.md) ·
[Evidence and hashes](../evidence/narrated-demo.json)

This 1-minute-58-second walkthrough uses a staged synthetic project handoff and
actual local Qwen3 4B inference. The recorded run returned three drafts and one
rejected suggestion. Mina's complete conditional source remains visible. Priya's
recipient is added by the person editing the draft, and the app marks that change
as “Edited by you.” Checking a task demonstrates list state; it does not perform
the task or establish that a prerequisite was satisfied.

The video combines original-speed recording, labelled screenshot holds,
close-ups, editorial cards and narration. It retains the complete inference wait,
but its edited timeline is not latency evidence. The separate
[original continuous silent recording](release-walkthrough.mp4) is unchanged.
Dialogue captions are not burned into the picture. The public page offers a
Show captions control, ten chapter buttons and an expandable text transcript.
Captions are off by default and are also available as a separate WebVTT file.

Synthetic narration was generated locally with
[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), voice `af_bella`, through
[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx).
Model weights: Apache-2.0; engine code: MIT. No hosted speech inference or paid
voice credits were used. The model and voice weights are not bundled here.
Each scene uses one connected paragraph at speed 1.0, with a shared gain and
short boundary silence. The ten delivered WAVs total 95.590667 seconds; the video
adds time to follow the recorded processing and read the source.

The 47 caption phrases use native model word-duration estimates, refined with
waveform pauses. They are not human-verified exact word boundaries. Each cue uses
at most two lines of 34 characters. All ten WAVs decoded without clipped samples.
Local ASR recovered the script, allowing documented proper-name spelling variants.
The user chose the short Bella audition; no full human listening review is claimed.

The accompanying UI motion is limited to state changes, button feedback and
new-result arrival. Reduced-motion preferences disable the animations. Previous
independent UI reviews covered source, 149 tests, normal/reduced motion, keyboard
editing, source/export preservation, mocked failures, late responses and 66
responsive states. The current revision changes media and its presentation only;
those historical checks are distinct from the real local capture above.

Long meetings remain a known weakness. The latest recorded hosted natural-meeting
test found nine of ten expected actions and failed acceptance; this video update
did not rerun or resolve that failure. Source matching is not a completeness or
semantic-correctness guarantee. See [release evidence](../release.md).

## Narration transcript

### 0:00 — Keep the condition with the task

Here's Loose Ends. It turns notes into a draft action list, with the original words beside each task. That matters when a promise starts with if.

### 0:11 — Paste the handoff notes

Let's use a short example with Priya, Leo and Mina. These notes are made up. Paste them here, keeping each action and its condition on the same line.

### 0:22 — Choose local processing

Choose This Mac to process the notes locally. When the model is ready, click Find actions. This is the actual wait from the recorded run.

### 0:38 — Review drafts and attribution

We got three drafts, and one suggestion didn't pass the checks. Priya's draft is due Friday; Leo's says tomorrow. Those dates stay just as they were written.

### 0:50 — Read the whole condition

Look at Mina's task. She'll archive the old checklist only if the review passes. That whole condition stays here, right beside the original quote.

### 1:02 — Edit with the source attached

Let's make Priya's task clearer. Open Edit, add to the project team, and save. The app marks that change as yours and keeps the original quote.

### 1:14 — Mark done and export

Now mark Priya's task done for the demo, and export. The Markdown file keeps the checkmark, your edit and the original source. Save it before closing the tab.

### 1:26 — Understand hosted processing

You can also choose Groq. That's optional: submitting there sends your notes to Groq, and it may use paid API credit.

### 1:35 — Know what still needs review

You'll still need to review the results. A longer meeting test using Groq missed a conditional commitment. A matching quote doesn't mean the list has everything.

### 1:47 — Explore the open source

The app is open source under the MIT license. The model licenses are separate. You'll find the code and setup instructions on GitHub.
