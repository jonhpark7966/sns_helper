# Drafts

Working drafts produced by `/write-post` (or by hand) — one file per post:

```
YYYY-MM-DD_<slug>.md        e.g. 2026-07-13_creator-recipe-day.md
```

Each file contains, top to bottom:

1. **Inputs** — the raw context given + elicited specifics (SCENE, PEOPLE, CONCRETE,
   HARD_PART, OTHERS, links, solo/co-host). Recorded so the later diff is meaningful.
2. **The draft sections** — `## Korean (LinkedIn)`, `## English (LinkedIn)`,
   `## X (optional)`, plus any `[TODO: ...]` markers still open.
3. **`## Outcome`** — appended by `/post-feedback` after publishing: permalink, the
   archived folder in `../posts/`, and the biggest deviations between draft and real post.

Drafts are the **before**; `../posts/` (downloaded real posts) are the **after**. The diff
between them is what keeps `../IMPROVE_PROMPT.md` calibrated — never delete a draft after
posting; it's a calibration sample.

`2026-07-13_creator-recipe-day.md` is the reference example of the full loop.
