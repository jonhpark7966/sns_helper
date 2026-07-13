# sns-helper

My toolkit for writing SNS posts — **LinkedIn first, X second** — in my own voice, fast.

It started as "YouTube video → posts", but the real job is broader: I come back from an
event, a hackathon, a company visit, or I ship something — and I want a good post out
**that day**, sounding like me, not like AI marketing copy.

## Which workflow do I need?

| I want to… | Do this | Docs |
|---|---|---|
| **Write a post** — event I attended, thing I built, episode promo, any notes | `/write-post` in Claude Code, or paste `linkedin_posts/IMPROVE_PROMPT.md` into any LLM | [§1](#1-write-a-new-post) |
| **Turn a YouTube video** into an X + LinkedIn post | `python3 sns_helper.py "<url>"` | [§2](#2-youtube-video-to-posts) |
| **Archive LinkedIn posts** (mine or someone's) locally, with images | `/archive-posts`, or `python3 linkedin_posts/tools/linkedin_download.py --new` | [§3](#3-linkedin-archive) |
| **Recalibrate the voice** after publishing a drafted post | `/post-feedback` | [§4](#4-the-feedback-loop) |

The glue is the **feedback loop** (§4): drafts are saved, real posts are archived, and the
diff between them updates the writing prompt — so drafts keep converging on how I actually
write.

---

## 1. Write a new post

The main workflow. Covers every post type, each with its own shape (defined in
`linkedin_posts/IMPROVE_PROMPT.md`):

| Type | Example |
|---|---|
| A. Episode / video promo | new sudoremove episode — adds the `with JC (Junho Cho) at sudoremove` closing block |
| B. Event / experience recap | hackathon, meetup, company visit — long, narrative, build-log |
| C. Technical explainer / analysis | "어떤 손이 좋은 손일까요" |
| D. Event announcement / invite | ICML open coffee chat — short, functional |
| E. Personal reflection / milestone | first-post milestone |
| F. Quick take / link share | two sentences + link |

### With Claude Code (this repo) — fastest

```
/write-post 어제 XX 해커톤 다녀옴. 영상 편집 에이전트 데모했고 3등.
            주최측 포스트: https://www.linkedin.com/feed/update/urn:li:activity:.../
```

Dump raw context — bullet notes, links, half-Korean-half-English, whatever. Then answer
its questions. What it does:

1. **Loads the voice** — `linkedin_posts/IMPROVE_PROMPT.md` + my most recent real posts
   from the archive.
2. **Scrapes any reference URLs** I gave (logged-in LinkedIn scraping included — see §3).
3. **Asks ONE batch of questions** for the specifics it can't invent: SCENE (the
   funny/surprising opening moment), PEOPLE (names + backgrounds), CONCRETE (exact prize /
   numbers / what the demo did), HARD_PART (what was actually hard + a forward-looking
   take), OTHERS (what other people built).
4. **Writes** Korean + English (+ optional X version) + a changelog of which voice rules
   it applied. Anything still missing becomes `[TODO: ...]` — never generic filler.
5. **Saves the draft** to `linkedin_posts/drafts/YYYY-MM-DD_<slug>.md`.

Then: publish on LinkedIn → `/archive-posts` → `/post-feedback` (§4).

Also handles: "이 LinkedIn 포스트 X용으로 바꿔줘" — paste a finished post, get the X
version only.

### With any LLM (no Claude Code)

Open `linkedin_posts/IMPROVE_PROMPT.md`, paste its system-prompt block into the LLM, fill
the inputs block, attach your notes. The prompt file carries the entire voice — the
Claude command above is just automation around it.

### Why the questions matter

Calibration finding (2026-07-13, Creator Recipe Day — the worked example in
`linkedin_posts/drafts/`): a draft's *skeleton* transfers near-verbatim, but a draft
written without the specifics loses exactly the parts people read for — the opening story,
real names, the exact prize, the honest build-log, the humor. Give SCENE / PEOPLE /
CONCRETE / HARD_PART / OTHERS up front and the draft lands ~90% done.

---

## 2. YouTube video to posts

`sns_helper.py` turns a YouTube video (mine or anyone else's) into an **X post** and a
**LinkedIn post** — insight-first, in the voice from `profile.json`, with a genuine
shoutout + link to the source. Built for tech / AI / LLM / robotics content.

```
youtube url  ──▶  metadata (yt-dlp)
             ──▶  transcript (captions ▸ Whisper ▸ ElevenLabs)
             ──▶  agent writer (claude -p  |  codex exec)
             ──▶  x_post.txt + linkedin_post.txt
```

Each post is engineered to deliver four things: a hooking first line (never "In this
video…"), insight not recap, my own take, and credit + link to the video (placed last on
X, where links suppress reach).

### Requirements

| Tool | Used for | Notes |
|------|----------|-------|
| `yt-dlp` | metadata + captions + audio | required |
| `ffmpeg` | caption/audio conversion | required (pulled in by yt-dlp) |
| `claude` **or** `codex` | writing the posts | uses your existing login — **no API key needed** |
| `uvx` (uv) | runs Whisper on demand | only for `--transcriber whisper`; `large-v3-turbo` model is cached |
| `curl` | ElevenLabs upload | only for `--transcriber elevenlabs` (needs `ELEVENLABS_API_KEY`) |

Python: **stdlib only** — nothing to `pip install`.

### Setup (30 seconds)

Edit **`profile.json`** so the posts sound like you — this is what powers "your take":

```jsonc
{
  "name": "Jane Doe",
  "role": "AI engineer",
  "x_handle": "@janedoe",
  "recurring_themes": ["agent reliability", "inference cost/latency"],
  "beliefs": ["eval is the real moat, not the model"],
  "tone": ["dry", "specific", "no-hype"],
  "avoid": ["game-changer", "🚀", "engagement-bait questions"],
  "languages": ["English", "Korean"]
}
```

Extra fields the writer also reads: `take_guidance` (form a fresh opinion per video instead
of recycling `beliefs`), `audience` (jargon level), `format_prefs`. Full field guide in
`profile.example.json`. The writer never invents biography beyond what's here.

### Usage

```bash
# default: captions → posts, written by claude, voice from ./profile.json
python3 sns_helper.py "https://youtu.be/VIDEO_ID"

# only one platform
python3 sns_helper.py "<url>" --only x
python3 sns_helper.py "<url>" --only linkedin

# choose the writer
python3 sns_helper.py "<url>" --agent codex
python3 sns_helper.py "<url>" --agent claude --model opus

# language — default inferred from profile.languages
python3 sns_helper.py "<url>" --lang en      # English only
python3 sns_helper.py "<url>" --lang ko      # Korean only (keeps English tech terms)
python3 sns_helper.py "<url>" --lang both    # both, side by side

# force a transcript source
python3 sns_helper.py "<url>" --transcriber whisper           # local, free, slower
python3 sns_helper.py "<url>" --transcriber elevenlabs        # API, needs ELEVENLABS_API_KEY
python3 sns_helper.py "<url>" --transcript-file my_notes.txt  # skip fetching entirely

# a different voice / longer transcript window
python3 sns_helper.py "<url>" --profile ./voices/spicy.json --max-transcript-words 16000
```

### Transcript sources (`--transcriber`)

| value | behavior |
|-------|----------|
| `auto` *(default)* | manual captions → auto captions → Whisper fallback |
| `subs` | captions only (manual then auto); error if none |
| `whisper` | always local Whisper (`turbo`) on the downloaded audio |
| `elevenlabs` | always ElevenLabs Scribe API (`ELEVENLABS_API_KEY` required) |

> For *writing posts*, auto-captions are fine and fast/free — Whisper/ElevenLabs are the
> fallback for videos with no captions at all.

### Output

Everything lands in `out/<video_id>/`:

```
x_post.txt              ← the post(s). Threads separate tweets with a line of `---`
linkedin_post.txt       ← (with >1 language, files are suffixed: x_post.en.txt, x_post.ko.txt …)
transcript.txt          ← the transcript that was used
meta.json               ← full yt-dlp metadata
generation_system.txt   ← exact system prompt sent (for debugging/tuning)
generation_*_task.txt   ← exact task prompt per platform
```

The terminal also prints the posts, with a per-tweet character count for X (URLs counted
as 23, the way X does), flagging anything over 280.

### Customizing the writing

The post quality lives in three editable prompt files — tweak freely, no code changes:
`prompts/system.md` (shared persona + grounding rules), `prompts/x_post.md`,
`prompts/linkedin_post.md`. Placeholders filled at runtime: `{{TITLE}}`, `{{CHANNEL}}`,
`{{URL}}`, `{{DESCRIPTION}}`, `{{TRANSCRIPT}}`, `{{PROFILE}}`.

### How it works

1. `yt-dlp --dump-json` → title, channel, url, description.
2. Transcript — tiered as above; captions de-duplicated and stripped to clean prose.
3. Two agent calls in parallel (`claude -p` or `codex exec`), one per platform, each
   getting the persona system prompt + a platform task prompt + the transcript.
4. Output cleaned (preambles / code fences / wrapping quotes removed) and saved.

---

## 3. LinkedIn archive

`linkedin_posts/` holds a local, per-post archive of my real LinkedIn posts — text,
metadata, images. It is the **ground truth for my voice**: drafting reads it (§1), and the
feedback loop diffs against it (§4).

```
linkedin_posts/
  posts/<YYYY-MM-DD>_<activityId>/   post.md · meta.json · img*.jpg / linkthumb*.jpg
  drafts/                            /write-post drafts + their ## Outcome after publishing
  index.md · index.json              rebuilt from disk on every download
  IMPROVE_PROMPT.md                  the writing prompt (§1) — the voice, distilled
  REVIEW.md                          one-time voice review of the first 6 posts
  tools/linkedin_download.py         the downloader (tools/README.md = full docs)
```

### Downloading

```bash
# from the repo root — only what's new (idempotent, keyed by activity id)
python3 linkedin_posts/tools/linkedin_download.py --new

# other modes
python3 linkedin_posts/tools/linkedin_download.py --count 5                    # recent N
python3 linkedin_posts/tools/linkedin_download.py --all                        # everything the feed serves
python3 linkedin_posts/tools/linkedin_download.py --profile <public-id> --count 10   # someone else
python3 linkedin_posts/tools/linkedin_download.py --all --include-reposts      # keep reposts too
```

Or in Claude Code: `/archive-posts`.

**First run:** be logged into LinkedIn in **Chrome**; macOS pops a Keychain dialog
("Chrome Safe Storage") — click **Allow**. That's the downloader decrypting the httpOnly
`li_at` cookie that normal cookie importers can't reach. Details + how the scraping works:
`linkedin_posts/tools/README.md`.

**Limitation:** LinkedIn's activity feed serves a bounded window — `--all` gets what the
feed will serve, not guaranteed lifetime history.

---

## 4. The feedback loop

What keeps drafts converging on how I actually write:

1. `/write-post` → draft saved to `linkedin_posts/drafts/`.
2. I edit to taste and publish on LinkedIn.
3. `/archive-posts` → the real post lands in `linkedin_posts/posts/`.
4. `/post-feedback` → diffs draft vs real post (what transferred, what I dropped, what I
   **added**), proposes + applies edits to `IMPROVE_PROMPT.md`, and appends an
   `## Outcome` section to the draft.

Every publish is a calibration sample. The prompt's current rules — the elicitation
inputs, the specificity pass, the build-log rule, the humor license, length-follows-type —
all came out of one loop iteration (see `linkedin_posts/drafts/2026-07-13_creator-recipe-day.md`).

---

## Repo map

```
sns_helper.py              YouTube → posts CLI (§2)
profile.json               my voice profile for the YouTube flow (profile.example.json = field guide)
prompts/                   system / x / linkedin prompts for the YouTube flow
linkedin_posts/            archive + post-writing toolkit (§1, §3, §4)
.claude/commands/          /write-post · /archive-posts · /post-feedback
CLAUDE.md                  guide for agent sessions in this repo
out/<video_id>/            YouTube flow output (gitignored)
```
