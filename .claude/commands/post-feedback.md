---
description: Compare my published post against its draft and tighten IMPROVE_PROMPT.md
---

I published a post (usually one drafted via `/write-post`). Close the feedback loop: $ARGUMENTS

1. **Archive it.** Run `python3 linkedin_posts/tools/linkedin_download.py --new` (skip if
   I say it's already archived).

2. **Pair post ↔ draft.** Newest folder in `linkedin_posts/posts/` vs the matching file in
   `linkedin_posts/drafts/` (match by date/topic; if ambiguous, ask). If no draft exists,
   review the post directly against `linkedin_posts/IMPROVE_PROMPT.md`, report compliance
   + anything the prompt should learn, and stop.

3. **Diff for signal, not word-by-word.** What transferred verbatim (that's what the
   prompt already gets right), what I dropped, and above all what I **added** that the
   draft lacked — opening scene/story, named people, exact prizes/numbers, build-log
   honesty, humor (ㅋㅋㅋ), length/structure.

4. **Report, then improve the prompt.** Present the comparison and the concrete
   `linkedin_posts/IMPROVE_PROMPT.md` edits that would have closed each gap — rule-level
   changes tied to evidence from the diff, not vibes. Apply the edits after I confirm (or
   immediately, if my message above already says to apply). Keep rules that the diff
   proves are working.

5. **Record the outcome.** Append an `## Outcome` section to the draft file: permalink,
   archive folder path, and the 2–3 biggest deviations, one line each. See
   `linkedin_posts/drafts/2026-07-13_creator-recipe-day.md` for the reference example.

6. If the diff taught something durable about my voice (not just a prompt tweak), also
   update the voice memory.
