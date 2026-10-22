# Release demonstration — 22 October 2026

[Watch the current local-model workflow](release-walkthrough.mp4) ·
[Original recorder output](release-walkthrough.webm) ·
[Browser and model evidence](../evidence/submission-browser.json)

This demonstration uses the public `explicit_actions` synthetic fixture from
`tests/fixtures/notes_cases.json`, the running local application and the actual
Qwen3 4B Instruct model. It shows generating three drafts, reviewing the complete
conditional source, editing one action, marking it done and downloading Markdown.
One additional model proposal was rejected by the validator and that message
remains visible. No inference responses were mocked or replaced.

- [Desktop draft list](release-desktop.png)
- [Desktop after editing and completion](release-desktop-reviewed.png)
- [Mobile layout with source qualification](release-mobile.png)
- [Exact downloaded Markdown](release-action-list.md)

The original WebM and the H.264 MP4 both run for 69.68 seconds at 25 fps.
The MP4 is a format conversion without cuts, retiming or overlays. The recorder
draws an animated pointer. Browser resource timing measured the single demo
request at 5.6244 seconds; this is one observation, not a latency guarantee.
The video is a workflow demonstration, not evidence of time saved.

All five existing synthetic notes cases passed in a separate real local-model
run. The fresh browser review also checked retained notes, edits, completion,
conditional evidence and an identical export after a deliberately offline
browser request. That recovery exercise happened after recording.

The longer natural meeting remains a known accuracy failure: the latest hosted
receipt contains nine of ten expected actions and misses a conditional
commitment. It was not rerun or fixed during this review. Source matching does
not prove semantic correctness or completeness; human review is required.

Only public synthetic text appears in these assets. The October 20 demonstration
and all historical assets remain unchanged. This evidence does not establish
publication, a contest submission, contest acceptance or milestone credit.
