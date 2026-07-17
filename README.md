# sns-helper

Turn a YouTube video into an **X (Twitter) post** and a **LinkedIn post** — insight-first,
in *your* voice, with a genuine shoutout to the source.

Built for tech / AI / LLM / robotics content. Works on **your** videos or **anyone else's**.

```
youtube url  ──▶  metadata (yt-dlp)
             ──▶  transcript (original-language captions ▸ English ▸ Whisper ▸ ElevenLabs)
             ──▶  agent writer (claude -p  |  codex exec)
             ──▶  x_post.txt + linkedin_post.txt
```

Each post is engineered (via a multi-agent prompt-design pass) to deliver four things:
1. **A hooking first line** — a scroll-stopper, never "In this video…".
2. **Insight, not recap** — the non-obvious "so what".
3. **Your own take** — first person, in the voice from `profile.json`.
4. **A shoutout** — credit + link to the video (placed last on X, where links suppress reach).

---

## Requirements

Already present on this machine:

| Tool | Used for | Notes |
|------|----------|-------|
| `yt-dlp` | metadata + captions + audio | required |
| `ffmpeg` | caption/audio conversion | required (pulled in by yt-dlp) |
| `claude` **or** `codex` | writing the posts | uses your existing login — **no API key needed** |
| `uvx` (uv) | runs Whisper on demand | only if you use `--transcriber whisper`; `large-v3-turbo` model is cached |
| `curl` | ElevenLabs upload | only for `--transcriber elevenlabs` (needs `ELEVENLABS_API_KEY`) |

Python: **stdlib only** — nothing to `pip install`.

---

## Setup (30 seconds)

Edit **`profile.json`** so the posts sound like you. This is what powers "your take":

```jsonc
{
  "name": "Jane Doe",
  "role": "AI engineer",
  "x_handle": "@janedoe",
  "recurring_themes": ["agent reliability", "inference cost/latency"],
  "beliefs": ["eval is the real moat, not the model",
              "most 'autonomous' agents are just retries with extra steps"],
  "tone": ["dry", "specific", "no-hype"],
  "avoid": ["game-changer", "🚀", "engagement-bait questions"],
  "languages": ["English", "Korean"]
}
```

Extra fields the writer also reads: `take_guidance` (tells it to form a fresh opinion each
video instead of recycling `beliefs`), `audience` (tunes jargon level), `format_prefs`
(e.g. "X: single punchy tweet; LinkedIn: short and sharp"), `own_channels` (host-POV
detection for your own videos), and `cohosts` (credited with a "with … at <channel>" line
on own-video posts).

See `profile.example.json` for the full field guide. The writer will **never invent
biography** beyond what's here — `beliefs`/`themes` shape opinions, nothing fabricates a résumé.

---

## Usage

```bash
# default: captions → posts, written by claude, voice from ./profile.json
python3 sns_helper.py "https://youtu.be/VIDEO_ID"

# only one platform
python3 sns_helper.py "<url>" --only x
python3 sns_helper.py "<url>" --only linkedin

# choose the writer
python3 sns_helper.py "<url>" --agent codex
python3 sns_helper.py "<url>" --agent claude --model opus

# language — default is inferred from profile.languages (yours = English + Korean)
python3 sns_helper.py "<url>" --lang en      # English only
python3 sns_helper.py "<url>" --lang ko      # Korean only (keeps English tech terms)
python3 sns_helper.py "<url>" --lang both    # both, side by side

# force a transcript source
python3 sns_helper.py "<url>" --transcriber whisper           # local, free, slower
python3 sns_helper.py "<url>" --transcriber elevenlabs         # API, needs ELEVENLABS_API_KEY
python3 sns_helper.py "<url>" --transcript-file my_notes.txt   # skip fetching entirely

# a different voice / longer transcript window
python3 sns_helper.py "<url>" --profile ./voices/spicy.json --max-transcript-words 16000

# weave in a host note the video can't tell us (e.g. next-episode teaser)
python3 sns_helper.py "<url>" --note "다음 편도 AI Native 얘기가 올라올 예정입니다."

# audience signal from the comments; per-video co-host credit
python3 sns_helper.py "<url>" --comments 50 --cohosts "JB, JC"
```

### Transcript sources (`--transcriber`)

| value | behavior |
|-------|----------|
| `auto` *(default)* | captions → Whisper fallback |
| `subs` | captions only; error if none |
| `whisper` | always local Whisper (`turbo`) on the downloaded audio |
| `elevenlabs` | always ElevenLabs Scribe API (`ELEVENLABS_API_KEY` required) |

**Captions are fetched in the video's *original source language first*, then English, then
Whisper.** The source language is auto-detected from the video's metadata (`--language ko`
to override). For a Korean video you get the real Korean transcript (`ko-orig` = YouTube's
original ASR track), not a machine-translated English caption — then the writer produces your
EN/KO posts from it. Transcript text is de-duplicated and stripped to clean prose.

> For *writing posts*, auto-captions are perfectly fine and fast/free — Whisper/ElevenLabs
> are the fallback for videos with no captions at all.

---

## Interview mode — write more like *you* (`--interview`)

The title, transcript, description, and comments can't tell the tool the things that make a post
yours: the scene you walked into, your real reaction, which moment stuck, who to tag (by their
LinkedIn names, not the transcript's), who to thank, what you built. So instead of smoothing those
gaps into generic prose (or inventing them), it **asks you**.

```bash
# phase 1 — writes out/<id>/interview.md with questions tailored to THIS video
python3 sns_helper.py "<url>" --only linkedin --lang ko --interview

# ...fill in the answers under each question (leave unknowns blank), then re-run the same command:
python3 sns_helper.py "<url>" --only linkedin --lang ko --interview
# (or pass answers directly: --answers-file path/to/answers.md)
```

Your answers become the **authoritative backbone** of the post (weighted above the transcript).
Anything still unknown is left as a visible `[TODO: ...]` for you to fill — the writer never
fabricates a name, number, or detail to paper over a gap.

The tool also matches your voice from your **real published posts** in `voice/linkedin_ko.md`
(refresh it by pasting in newer posts).

## Output

Everything lands in `out/<video_id>/`:

```
x_post.txt              ← the post(s). Threads separate tweets with a line of `---`
linkedin_post.txt       ← (with >1 language, files are suffixed: x_post.en.txt, x_post.ko.txt …)
transcript.txt          ← the transcript that was used
meta.json               ← full yt-dlp metadata
generation_system.txt   ← exact system prompt sent (for debugging/tuning)
generation_*_task.txt   ← exact task prompt per platform
```

The terminal also prints the posts, and for X shows a **per-tweet character count**
(URLs counted as 23, the way X does), flagging anything over 280.

---

## Customizing the writing

The post quality lives in three editable prompt files — tweak them freely, no code changes:

- `prompts/system.md` — shared persona + grounding rules (`{{PROFILE}}`)
- `prompts/x_post.md` — X post instructions
- `prompts/linkedin_post.md` — LinkedIn post instructions

Placeholders filled at runtime: `{{TITLE}}`, `{{CHANNEL}}`, `{{URL}}`, `{{DESCRIPTION}}`,
`{{TRANSCRIPT}}`, `{{PROFILE}}`.

---

## How it works

1. **`yt-dlp --dump-json`** → title, channel, url, description.
2. **Transcript** — tiered as above; captions are de-duplicated and stripped to clean prose.
3. **Two agent calls in parallel** (`claude -p` or `codex exec`), one per platform, each
   getting the persona system prompt + a platform task prompt + the transcript.
4. Output is **cleaned** (preambles / code fences / wrapping quotes removed) and saved.

The prompts themselves were designed by a panel of drafting agents (growth, authority, and
anti-cringe lenses) plus an adversarial pass that enumerated ~90 AI-slop "tells" to ban.
