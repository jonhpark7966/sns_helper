---
description: Draft a LinkedIn (+ X) post in my voice — event recap, episode promo, announcement, explainer, or rough notes
---

Draft a new SNS post for me (Jong Hyun Park, LinkedIn `jonhpark7966`). My raw context — notes, links, or a topic:

$ARGUMENTS

Follow this exact workflow:

1. **Load the voice.** Read `linkedin_posts/IMPROVE_PROMPT.md` and treat its system-prompt
   block as your writing instructions (post-type taxonomy A–F, universal voice rules,
   specificity pass, output format). Then read the 2–3 most recent posts under
   `linkedin_posts/posts/` (newest first — see `linkedin_posts/index.md`) to calibrate
   against how I actually write today.

2. **Gather facts.** If I gave URLs above, fetch/scrape them for concrete facts (event
   name, host, venue, people, claims to relay with 전언). A LinkedIn URL hits an authwall
   for logged-out sessions — seed the browse session with the `li_at` cookie the way
   `linkedin_posts/tools/linkedin_download.py` does (see `linkedin_posts/tools/README.md`,
   "How it works"), then open the post URL and extract text/author. Facts you cannot
   confirm do not go in the draft.

3. **Ask me for the specifics you can't invent — in ONE short batch.** Only the ones that
   apply and are missing: SCENE (a surprising/funny opening moment), PEOPLE (names +
   backgrounds to mention or thank), CONCRETE (exact prize / numbers / what the demo did,
   input → output), HARD_PART (what was actually hard + one forward-looking take), OTHERS
   (other people's builds to describe generously), LINKS, solo or `with JC`. If I already
   said "just draft" or I don't answer, draft anyway — with `[TODO: ...]` markers, never
   generic filler.

4. **Write** exactly in IMPROVE_PROMPT's output format: `## Korean (LinkedIn)`,
   `## English (LinkedIn)`, `## X (optional)`, `## What I changed`, `## Missing specifics`.

5. **Save the draft** to `linkedin_posts/drafts/<YYYY-MM-DD>_<slug>.md` (today's date,
   short kebab slug). Record at the top the inputs I gave (plus your elicited answers),
   then the draft sections. This file is what `/post-feedback` diffs against the real post
   later — see `linkedin_posts/drafts/README.md`.

6. **Close with the loop reminder:** I publish on LinkedIn → `/archive-posts` →
   `/post-feedback`.

Special case: if my context above is an already-written LinkedIn post and I just want the
X version, skip steps 3/5/6 and produce only the `## X` section (one tweet, or a short
thread if the substance needs it), following the same voice rules.
