# sns-helper — agent guide

Toolkit for writing SNS posts (LinkedIn + X) in Jong Hyun Park's voice, plus a local
archive of his real LinkedIn posts that serves as the voice's ground truth. Full usage
lives in `README.md`. Three workflows:

1. **Write a post** (event recap, episode promo, announcement, explainer, quick take) —
   `/write-post`, or follow `linkedin_posts/IMPROVE_PROMPT.md` directly.
2. **YouTube video → X + LinkedIn posts** — `python3 sns_helper.py "<url>"`. Fetches
   original-language captions, comments (`--comments`), writes EN/KO; `--interview`
   runs the SCENE/PEOPLE/CONCRETE elicitation below automatically (see README).
3. **Archive LinkedIn posts** — `/archive-posts`, or
   `python3 linkedin_posts/tools/linkedin_download.py --new` (idempotent).

## Rules for every session

- **Voice source of truth** = `linkedin_posts/IMPROVE_PROMPT.md` + the real posts in
  `linkedin_posts/posts/`. Before drafting anything, read the newest 2–3 posts
  (`linkedin_posts/index.md` lists them). The generator injects a curated subset from
  `voice/linkedin_ko.md` — refresh it from the archive when the voice drifts.
- **Never invent facts** — names, numbers, prizes, quotes, links. Ask for the specifics
  (SCENE / PEOPLE / CONCRETE / HARD_PART / OTHERS) in one short batch, or leave
  `[TODO: ...]` markers. Generic filler prose is the failure mode, not blanks. In the
  generator this is built in: `sns_helper.py --interview` asks the batch, injects the
  answers as authoritative HOST INPUT, and leaves `[TODO]` for anything unanswered.
- Drafts go to `linkedin_posts/drafts/YYYY-MM-DD_<slug>.md`. After he publishes,
  `/post-feedback` diffs draft vs real post and updates `IMPROVE_PROMPT.md` — that
  feedback loop is the product; never skip saving the draft.
- LinkedIn scraping needs a logged-in `li_at` cookie. The downloader seeds it from Chrome
  (first run: macOS Keychain "Chrome Safe Storage" dialog → Allow). Details in
  `linkedin_posts/tools/README.md`.
- Python in this repo is **stdlib-only** — keep it that way.
