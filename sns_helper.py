#!/usr/bin/env python3
"""
sns_helper — turn a YouTube video into an X post and a LinkedIn post.

Pipeline:
  1. Fetch metadata (title, description, channel, url) with yt-dlp.
  2. Get a transcript (tiered): manual captions -> auto captions -> Whisper -> ElevenLabs.
  3. Generate an X post and a LinkedIn post with an agent CLI (claude -p or codex exec).

Insight-first posts: hooking first line, the poster's own thoughts (from profile.json),
and a shoutout to the source video. Designed for tech / AI / LLM / robotics content.

Stdlib only. External CLIs used: yt-dlp, ffmpeg (via yt-dlp), whisper (via uvx), curl,
and one of: claude, codex.

Usage:
  python3 sns_helper.py "https://youtu.be/VIDEO_ID"
  python3 sns_helper.py "<url>" --agent codex --transcriber whisper
  python3 sns_helper.py "<url>" --only x --profile ./profile.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTS_DIR = HERE / "prompts"


# --------------------------------------------------------------------------- #
# small utilities
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(f"\033[2m[sns]\033[0m {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 1) -> "None":
    print(f"\033[31m[sns:error]\033[0m {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def require_exe(name: str) -> str:
    path = shutil.which(name)
    if not path:
        die(f"Required executable not found on PATH: {name}")
    return path  # type: ignore[return-value]


def run(cmd: list[str], capture: bool = False, check: bool = True,
        env: dict | None = None) -> str:
    """Run a command. Returns stdout (str) when capture=True."""
    if capture:
        proc = subprocess.run(
            cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )
        if check and proc.returncode != 0:
            die(f"command failed ({proc.returncode}): {' '.join(cmd[:3])} ...\n"
                f"{proc.stderr.strip()[-1500:]}")
        return proc.stdout
    proc = subprocess.run(cmd, check=False, env=env)
    if check and proc.returncode != 0:
        die(f"command failed ({proc.returncode}): {' '.join(cmd[:3])} ...")
    return ""


# --------------------------------------------------------------------------- #
# 1. metadata
# --------------------------------------------------------------------------- #
def fetch_metadata(url: str, out_dir: Path) -> dict:
    require_exe("yt-dlp")
    log("fetching metadata (yt-dlp --dump-json) ...")
    out = run(
        ["yt-dlp", "--no-playlist", "--quiet", "--no-warnings",
         "--dump-json", "--skip-download", url],
        capture=True,
    )
    line = out.strip().splitlines()[-1] if out.strip() else ""
    if not line:
        die("yt-dlp returned no metadata (is the URL valid / reachable?)")
    meta = json.loads(line)
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    return meta


def meta_summary(meta: dict) -> dict:
    """Pull the fields the writer actually needs."""
    return {
        "id": meta.get("id", ""),
        "title": meta.get("title", "") or meta.get("fulltitle", ""),
        "channel": meta.get("channel") or meta.get("uploader") or "",
        "channel_url": meta.get("channel_url") or meta.get("uploader_url") or "",
        "url": meta.get("webpage_url") or meta.get("original_url") or "",
        "description": meta.get("description", "") or "",
        "duration": meta.get("duration") or 0,
        "upload_date": meta.get("upload_date", "") or "",
        "tags": meta.get("tags") or [],
    }


# --------------------------------------------------------------------------- #
# 2. transcript
# --------------------------------------------------------------------------- #
_TS_LINE = re.compile(r"^\s*\d\d:\d\d:\d\d[.,]\d{3}\s*-->")
_VTT_TAG = re.compile(r"<[^>]+>")            # <c>, </c>, <00:00:01.000>
_INDEX_LINE = re.compile(r"^\d+\s*$")


def subtitle_to_text(path: Path) -> str:
    """Parse a .srt or .vtt file into clean, de-duplicated plain text.

    Auto-captions roll/repeat lines, so we drop consecutive duplicates and
    timing/markup. Output is paragraph-ish plain prose.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = raw.replace("﻿", "")
    lines_out: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.upper() == "WEBVTT" or s.startswith(("NOTE", "Kind:", "Language:")):
            continue
        if _TS_LINE.search(s) or "-->" in s:
            continue
        if _INDEX_LINE.match(s):
            continue
        s = _VTT_TAG.sub("", s).strip()
        s = re.sub(r"\s+", " ", s)
        if not s:
            continue
        # drop consecutive duplicate lines (auto-caption rolling window)
        if lines_out and lines_out[-1] == s:
            continue
        # drop a line that's a prefix-continuation already covered
        if lines_out and (s in lines_out[-1] or lines_out[-1] in s) and len(s) < 25:
            continue
        lines_out.append(s)
    # collapse word-level dupes at line seams
    text = " ".join(lines_out)
    text = re.sub(r"\b(\w+ \w+ \w+)( \1\b)+", r"\1", text)  # light repeat squash
    return text.strip()


def _find_sub(out_dir: Path, video_id: str, prefixes: list[str]) -> Path | None:
    """Find a downloaded subtitle file, trying language prefixes in priority order."""
    for pref in prefixes:
        for ext in ("srt", "vtt"):
            matches = sorted(out_dir.glob(f"{video_id}.{pref}*.{ext}"))
            if matches:
                return matches[0]
    return None


def try_captions(url: str, out_dir: Path, video_id: str, sub_langs: list[str],
                 match_prefixes: list[str], auto: bool) -> str | None:
    require_exe("yt-dlp")
    kind = "auto" if auto else "manual"
    log(f"trying {kind} captions [{','.join(sub_langs)}] ...")
    flag = "--write-auto-subs" if auto else "--write-subs"
    template = str(out_dir / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp", "--no-playlist", "--skip-download", flag,
        "--sub-lang", ",".join(sub_langs),
        "--sub-format", "vtt/srt/best",
        "--convert-subs", "srt",
        "-o", template, url,
    ]
    run(cmd, capture=True, check=False)
    sub = _find_sub(out_dir, video_id, match_prefixes)
    if not sub:
        return None
    text = subtitle_to_text(sub)
    if len(text) < 80:
        return None
    log(f"got {kind} captions ({len(text.split())} words) from {sub.name}")
    return text


def _caption_plan(src: str | None) -> list[tuple[str, bool, list[str], list[str]]]:
    """Ordered caption attempts: (label, is_auto, sub_langs, match_prefixes).

    Prefers the video's ORIGINAL source language over English. `<lang>-orig` is
    YouTube's original ASR track (not a machine translation). English is only
    attempted when the source is English or unknown.
    """
    plan: list[tuple[str, bool, list[str], list[str]]] = []
    if src and src != "en":
        plan.append((f"manual:{src}", False, [src, f"{src}.*"], [src]))
        plan.append((f"auto:{src}", True, [f"{src}-orig", src], [f"{src}-orig", src]))
    if src == "en" or not src:
        plan.append(("manual:en", False, ["en", "en.*"], ["en"]))
        plan.append(("auto:en", True, ["en-orig", "en"], ["en-orig", "en"]))
    return plan


def download_audio(url: str, out_dir: Path, video_id: str) -> Path:
    require_exe("yt-dlp")
    log("downloading audio (yt-dlp -x) ...")
    template = str(out_dir / f"{video_id}.%(ext)s")
    run(["yt-dlp", "--no-playlist", "-x", "--audio-format", "mp3",
         "-o", template, url])
    audio = out_dir / f"{video_id}.mp3"
    if not audio.exists():
        cands = sorted(out_dir.glob(f"{video_id}.*"))
        cands = [c for c in cands if c.suffix.lower() in
                 (".mp3", ".m4a", ".wav", ".opus", ".webm")]
        if not cands:
            die("audio download finished but no audio file found")
        audio = cands[0]
    return audio


def whisper_prefix() -> list[str]:
    w = shutil.which("whisper")
    if w:
        return [w]
    if shutil.which("uvx"):
        # openai-whisper is the package, `whisper` is its console script.
        return ["uvx", "--from", "openai-whisper", "whisper"]
    die("Whisper not available: install `openai-whisper` or `uv` (for uvx).")
    return []  # unreachable


def try_whisper(url: str, out_dir: Path, video_id: str, model: str,
                language: str | None) -> str | None:
    audio = download_audio(url, out_dir, video_id)
    log(f"transcribing with Whisper ({model}) — this can take a few minutes ...")
    srt_path = out_dir / f"{audio.stem}.srt"
    if not srt_path.exists():
        cmd = whisper_prefix() + [
            str(audio), "--output_dir", str(out_dir),
            "--output_format", "srt", "--model", model,
        ]
        if language:
            cmd += ["--language", language]
        run(cmd)
    if not srt_path.exists():
        die(f"Whisper finished but SRT not found: {srt_path}")
    text = subtitle_to_text(srt_path)
    log(f"Whisper transcript: {len(text.split())} words")
    return text


def try_elevenlabs(url: str, out_dir: Path, video_id: str) -> str | None:
    key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")
    if not key:
        die("ElevenLabs requested but ELEVENLABS_API_KEY (or ELEVEN_API_KEY) is not set.")
    require_exe("curl")
    audio = download_audio(url, out_dir, video_id)
    log("transcribing with ElevenLabs Scribe ...")
    resp_path = out_dir / "elevenlabs_response.json"
    cmd = [
        "curl", "-sS", "-X", "POST",
        "https://api.elevenlabs.io/v1/speech-to-text",
        "-H", f"xi-api-key: {key}",
        "-F", "model_id=scribe_v1",
        "-F", f"file=@{audio}",
        "-o", str(resp_path),
    ]
    run(cmd, capture=True)
    try:
        data = json.loads(resp_path.read_text(encoding="utf-8"))
    except Exception:
        die(f"ElevenLabs returned non-JSON; see {resp_path}")
    if "text" not in data:
        die(f"ElevenLabs response had no transcript; see {resp_path}: "
            f"{json.dumps(data)[:400]}")
    text = re.sub(r"\s+", " ", data["text"]).strip()
    log(f"ElevenLabs transcript: {len(text.split())} words")
    return text


def detect_source_lang(meta: dict, override: str | None) -> str | None:
    """The video's original language (ISO base code), for caption selection."""
    raw = override or (meta.get("language") if meta else None) or ""
    return raw.split("-")[0].strip().lower() or None


def get_transcript(url: str, out_dir: Path, video_id: str, transcriber: str,
                   whisper_model: str, language: str | None,
                   transcript_file: str | None, meta: dict) -> tuple[str, str]:
    """Returns (transcript_text, source_label). Captions are fetched in the
    video's ORIGINAL source language first, then English, then Whisper."""
    if transcript_file:
        p = Path(transcript_file).expanduser()
        if not p.exists():
            die(f"--transcript-file not found: {p}")
        txt = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".srt", ".vtt"):
            txt = subtitle_to_text(p)
        return txt.strip(), f"file:{p.name}"

    src = detect_source_lang(meta, language)
    log(f"source language: {src or 'unknown'}")

    if transcriber == "elevenlabs":
        return try_elevenlabs(url, out_dir, video_id) or "", "elevenlabs"
    if transcriber == "whisper":
        return (try_whisper(url, out_dir, video_id, whisper_model, src) or "",
                f"whisper({src or 'auto'})")

    # captions: original source language first, then English, in priority order
    for label, auto, sub_langs, prefixes in _caption_plan(src):
        t = try_captions(url, out_dir, video_id, sub_langs, prefixes, auto)
        if t:
            return t, f"captions:{label}"

    if transcriber == "subs":
        die(f"No captions available (source={src or 'unknown'}); "
            "try --transcriber whisper.")

    log("no captions found; falling back to Whisper")
    t = try_whisper(url, out_dir, video_id, whisper_model, src)
    if not t:
        die("Could not obtain a transcript by any method.")
    return t, f"whisper({src or 'auto'})"


# --------------------------------------------------------------------------- #
# 3. generation
# --------------------------------------------------------------------------- #
def fetch_comments(url: str, out_dir: Path, max_comments: int) -> list[dict]:
    """Fetch top comments (cached). Returns [{text, likes}], sorted by likes."""
    cache = out_dir / "comments.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    require_exe("yt-dlp")
    log(f"fetching up to {max_comments} top comments ...")
    out = run(
        ["yt-dlp", "-J", "--write-comments", "--no-warnings", "--skip-download",
         "--extractor-args",
         f"youtube:max_comments={max_comments},all,0;comment_sort=top", url],
        capture=True, check=False)
    try:
        meta = json.loads(out.strip().splitlines()[-1])
    except Exception:
        log("could not fetch comments (skipping)")
        return []
    simplified = [
        {"text": " ".join((c.get("text") or "").split()), "likes": c.get("like_count") or 0}
        for c in (meta.get("comments") or []) if (c.get("text") or "").strip()
    ]
    simplified.sort(key=lambda c: c["likes"], reverse=True)
    cache.write_text(json.dumps(simplified, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"got {len(simplified)} comments")
    return simplified


def comments_directive(comments: list[dict], n: int = 12) -> str:
    if not comments:
        return ""
    lines = "\n".join(f"- ({c['likes']}♥) {c['text'][:200]}" for c in comments[:n])
    return (
        "\n\n# TOP VIEWER COMMENTS (audience signal — context only)\n"
        "These are top comments on the video. Use them ONLY to sense what resonated or what "
        "viewers care about, and let that lightly inform your emphasis. Do NOT quote them, "
        "attribute them, treat them as facts, or address commenters. Ignore links/spam.\n" + lines)


def load_voice_samples() -> str:
    f = HERE / "voice" / "linkedin_ko.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def voice_directive(platform: str, lang: str) -> str:
    """Inject the poster's REAL posts as a voice reference (KO LinkedIn = strongest signal)."""
    if platform != "linkedin" or lang != "ko":
        return ""
    samples = load_voice_samples()
    if not samples:
        return ""
    return (
        "\n\n# HOW YOU ACTUALLY WRITE — voice reference (match rhythm, NOT content)\n"
        "Below are REAL posts you published. Match their register, humor (ㅋㅋㅋ ok), how they "
        "OPEN (a concrete/funny/self-deprecating scene or spoken reaction — not a summary), how "
        "they name+tag real people, the honest build-log, and the plain close. Do NOT reuse their "
        "topic or sentences — only the voice.\n\n" + samples)


def generate_questions(summ: dict, transcript: str, comments: list[dict], own: bool,
                       agent: str, model: str | None, out_dir: Path,
                       qlang: str, profile: dict) -> str:
    name = profile.get("name") or "the poster"
    ctext = "\n".join(f"- {c['text'][:160]}" for c in comments[:8]) or "(none)"
    ask_lang = "Korean" if qlang == "ko" else "English"
    task = (
        f"You are helping {name} write a social post about a video, in their voice. Before "
        "writing, generate a SHORT list of questions to ask THEM — only about things the title, "
        "description, transcript, and comments CANNOT tell you, but that would make the post "
        "specific and true.\n\n"
        "Focus your questions on:\n"
        "- The OPENING SCENE / their real reaction (recaps live or die on this): what surprised "
        "them, a funny/self-deprecating moment, why they went.\n"
        "- PEOPLE to tag and EXACTLY how each name should appear (LinkedIn tags are romanized real "
        "names, not the transcript's Korean names) — guest(s), interviewees, and the organizer to "
        "thank.\n"
        "- The single MOMENT or idea that mattered most to them personally.\n"
        "- Anything THEY built/demoed (the honest build-log: what was actually hard).\n"
        "- OTHER people's builds/work worth crediting generously.\n"
        "- The exact CREDIT / closing line and co-host(s) for THIS post.\n"
        "- Any likely-mis-transcribed name/number/product to correct (auto-captions are messy).\n\n"
        "Rules: 4-8 questions max, each grounded in THIS video's actual content (name the people/"
        f"segments you saw), each answerable in one line, written in {ask_lang}. Output ONLY a "
        "numbered list of questions, nothing else.\n\n"
        "VIDEO\n"
        f"Title: {summ['title']}\n"
        f"Channel: {summ['channel']}  (this is the poster's own video: {'yes' if own else 'no'})\n"
        f"Description:\n{(summ['description'] or '')[:1500]}\n\n"
        f"Transcript (messy auto-captions possible):\n{cap_words(transcript, 3000)}\n\n"
        f"Top comments:\n{ctext}\n"
    )
    return generate_post("interview", "You write sharp, specific, non-generic interview questions.",
                         task, agent, model, out_dir).strip()


def write_interview_file(path: Path, questions_text: str, url: str) -> None:
    qs = [q.strip() for q in re.split(r"(?m)^\s*\d+[.)]\s*", questions_text) if q.strip()]
    lines = [
        "# 인터뷰 — 각 질문 아래 '> ' 다음에 답을 적고, 같은 명령을 다시 실행하세요.",
        f'#   python3 sns_helper.py "{url}" --interview ...(같은 옵션)',
        "# 빈 답은 무시됩니다. 모르면 비워두세요 — 지어내지 않고 [TODO]로 남깁니다.",
        "",
    ]
    for i, q in enumerate(qs, 1):
        lines += [f"## Q{i}. {q}", "> ", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_answers(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    qa: list[tuple[str, str]] = []
    for block in re.split(r"(?m)^##\s*Q\d+\.\s*", text)[1:]:
        blines = block.splitlines()
        q = blines[0].strip() if blines else ""
        ans = [ln.strip()[1:].strip() for ln in blines[1:]
               if ln.strip().startswith(">") and ln.strip()[1:].strip()]
        qa.append((q, " ".join(ans).strip()))
    return qa


def host_input_directive(qa: list[tuple[str, str]]) -> str:
    filled = [(q, a) for q, a in qa if a.strip()]
    if not filled:
        return ""
    body = "\n".join(f"- {q}\n  → {a}" for q, a in filled)
    return (
        "\n\n# HOST INPUT — the poster's own answers (AUTHORITATIVE)\n"
        "The poster answered these about their real experience. Treat this as the BACKBONE of the "
        "post — more authoritative than the transcript. Use their scene, their names (spell/tag "
        "EXACTLY as given), and their details faithfully; never override or contradict them. For "
        "anything still unknown that would strengthen the post, write [TODO: ...] rather than "
        "inventing it.\n" + body)


def load_profile(path: str | None) -> dict:
    candidates = [path] if path else []
    candidates += [str(HERE / "profile.json"), str(HERE / "profile.example.json")]
    for c in candidates:
        if c and Path(c).expanduser().exists():
            log(f"profile: {c}")
            return json.loads(Path(c).expanduser().read_text(encoding="utf-8"))
    return {}


def fill(template: str, values: dict) -> str:
    out = template
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", str(val))
    return out


def cap_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    head = " ".join(words[: int(max_words * 0.7)])
    tail = " ".join(words[-int(max_words * 0.3):])
    return f"{head}\n\n[... transcript trimmed for length ...]\n\n{tail}"


def build_values(summ: dict, profile: dict, transcript: str,
                 max_words: int) -> dict:
    return {
        "TITLE": summ["title"],
        "CHANNEL": summ["channel"],
        "URL": summ["url"],
        "DESCRIPTION": (summ["description"] or "").strip()[:2500],
        "TRANSCRIPT": cap_words(transcript, max_words),
        "PROFILE": json.dumps(profile, ensure_ascii=False, indent=2) if profile
                   else "(no profile provided — write as a thoughtful, opinionated "
                        "AI/tech practitioner; use a neutral first-person voice)",
    }


_PREAMBLE_WORDS = ("post", "thread", "tweet", "here", "sure", "version", "draft")


def clean_output(text: str) -> str:
    """Strip preambles / code fences / wrapping quotes a model sometimes adds."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    lines = t.splitlines()
    if lines:
        first = lines[0].strip().lower()
        if first.endswith(":") and len(first) <= 60 and \
                any(w in first for w in _PREAMBLE_WORDS):
            rest = lines[1:]
            while rest and not rest[0].strip():
                rest = rest[1:]
            t = "\n".join(rest).strip()
    if len(t) >= 2 and t[0] in "\"'“" and t[-1] in "\"'”" \
            and t.count("\n") == 0:
        t = t[1:-1].strip()
    return t


def _is_wide(o: int) -> bool:
    """X weighted-count: CJK / Hangul / Kana code points count as 2."""
    return (0x1100 <= o <= 0x115F or 0x2E80 <= o <= 0x303E or 0x3041 <= o <= 0x33FF
            or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF or 0xA000 <= o <= 0xA4CF
            or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF or 0xFE30 <= o <= 0xFE4F
            or 0xFF00 <= o <= 0xFF60 or 0xFFE0 <= o <= 0xFFE6)


def x_char_count(tweet: str) -> int:
    """X weighted character count: URLs = 23, CJK/Hangul/Kana = 2, else 1."""
    urls = re.findall(r"https?://\S+", tweet)
    text = re.sub(r"https?://\S+", "", tweet)
    n = sum(2 if _is_wide(ord(ch)) else 1 for ch in text)
    return n + 23 * len(urls)


LANG_NAMES = {"en": "English", "ko": "Korean"}


def resolve_langs(arg_lang: str | None, profile: dict) -> list[str]:
    if arg_lang == "both":
        return ["en", "ko"]
    if arg_lang in ("en", "ko"):
        return [arg_lang]
    # infer from profile.languages / profile.language
    raw = profile.get("languages") or profile.get("language") or []
    if isinstance(raw, str):
        raw = [raw]
    text = " ".join(raw).lower()
    out = []
    if "en" in text or "english" in text:
        out.append("en")
    if "ko" in text or "korea" in text or "한국" in text:
        out.append("ko")
    return out or ["en"]


def lang_directive(lang: str, platform: str) -> str:
    if lang == "ko":
        base = (
            "\n\n# OUTPUT LANGUAGE (override — highest priority)\n"
            "Write the ENTIRE post in natural, fluent Korean (한국어), the way a thoughtful Korean "
            "engineer actually writes — not a translation. Keep established English technical and "
            "product/brand/model names in English (LLM, GPU, VLA, agent, fine-tuning, transformer, "
            "RLHF, Codex, Claude Code, Cursor, Anthropic, ...). Do not translate the creator's name "
            "or the video title; keep {{URL}} exactly as-is.\n"
            "REGISTER: friendly 존댓말 (-습니다 / -죠 / -네요 / 해요체). Warm and conversational, like "
            "talking to smart peers — NOT blunt 반말, NOT stiff corporate boilerplate.\n"
            "TEXTURE: keep a clear opinion, but soften absolutes with light hedges where it reads "
            "naturally (\"~인 것 같습니다\", \"~겠죠\", \"~기도 합니다\"). A short parenthetical aside or a "
            "little self-deprecation about your own take is welcome (e.g. \"(물론 완벽하진 않습니다.)\"). "
            "Stay no-hype.\n"
            "ATTRIBUTION: report the video's/guest's claims with reportative endings (~라고 합니다, "
            "~한답니다, ~라고 하더라고요); keep plain assertions and ~인 것 같아요/~겠죠 for YOUR own "
            "take, so readers can tell which is which. Avoid absolute intensifiers (바닥까지, 아무도, "
            "전부, 절대, 무조건) unless the video literally says so. Describe the episode's content "
            "with calm verbs (살펴봤습니다, 이야기했습니다) — save playful slang for parenthetical asides "
            "about yourself. No dramatic setup lines like \"핵심은 이거였습니다\" — just say the thing.")
        if platform == "x":
            base += ("\nThis is X: keep it to one tight breath — compressed and tweet-like even in "
                     "존댓말.")
        else:
            base += ("\nThis is LinkedIn: short paragraphs with breathing room, comfortable to "
                     "read; don't over-compress. A bit longer than the X version.")
        return base
    return ("\n\n# OUTPUT LANGUAGE (override — highest priority)\n"
            "Write the entire post in English.")


def is_own_video(summ: dict, profile: dict) -> bool:
    """True when the video's channel belongs to the poster (host point of view)."""
    chan = (summ.get("channel") or "").strip().lower().lstrip("@")
    if not chan:
        return False
    owns = [str(c).strip().lower().lstrip("@")
            for c in (profile.get("own_channels") or [])]
    return any(o and (o == chan or o in chan) for o in owns)


def ownership_directive(summ: dict, profile: dict) -> str:
    chan = summ.get("channel") or "this channel"
    if is_own_video(summ, profile):
        cohosts = [str(c) for c in (profile.get("cohosts") or []) if str(c).strip()]
        cohost_rule = ""
        if cohosts:
            names = ", ".join(cohosts)
            cohost_rule = (
                f"- Credit your co-host(s) on a plain final line, e.g. \"with {names} at {chan}\" "
                f"or \"{names}, {chan}\" — placed after the link. If HOST INPUT gives an exact "
                "credit line, use that verbatim instead. Don't invent additional collaborators.\n")
        return (
            "\n\n# THIS IS YOUR OWN VIDEO — host point of view\n"
            f"'{chan}' is YOUR own channel/show — you are the host, NOT a viewer who found someone "
            "else's video. (This framing is true, not fabrication.) So:\n"
            "- Frame the post as you sharing your NEW episode — never \"I watched a great video\".\n"
            "- If there's a guest, introduce them by name + background using ONLY facts from the "
            "{{DESCRIPTION}}/{{TRANSCRIPT}} (past roles, what they build now). Refer to them as your "
            "guest.\n"
            "- Close by warmly and a little humbly inviting people to watch your episode, with a "
            "genuine reason it's worth it (a sharp segment, the guest's humor) — not a dry citation.\n"
            + cohost_rule +
            "- Never invent or guess a social handle, and never output a placeholder like @null or "
            "@handle. If you don't know someone's handle, use their plain name.")
    return (
        "\n\n# THIS IS SOMEONE ELSE'S VIDEO\n"
        f"You are a viewer, not the creator of '{chan}'. Credit {chan} genuinely and recommend the "
        "video as a real find — don't imply you made it. Never invent a handle or output a "
        "placeholder like @null/@handle; use plain names if unsure.")


def split_tweets(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"(?m)^\s*-{3,}\s*$", text) if t.strip()]


def x_over_limit(text: str) -> list[int]:
    return [i for i, tw in enumerate(split_tweets(text)) if x_char_count(tw) > 280]


def repair_x(post: str, system: str, agent: str, model: str | None,
             out_dir: Path, lang: str = "en", max_attempts: int = 2) -> str:
    """Re-ask the agent to split/tighten any X tweet that exceeds 280 chars."""
    for attempt in range(max_attempts):
        over = x_over_limit(post)
        if not over:
            return post
        tweets = split_tweets(post)
        detail = "; ".join(f"tweet {i + 1} is {x_char_count(tweets[i])} chars" for i in over)
        log(f"X[{lang}] over limit ({detail}); repairing "
            f"(attempt {attempt + 1}/{max_attempts}) ...")
        task = (
            "The X post below breaks the 280-character-per-tweet limit "
            f"({detail}; X counts each URL as 23 chars and each Korean/CJK character as 2). "
            "Rewrite it so EVERY tweet is <= 280 characters. Split it into a thread (2-5 tweets) "
            "if needed, with tweets separated by a line containing exactly three hyphens (---). "
            "Keep the same voice, the hook in tweet 1 (no link in tweet 1), the insight, the "
            "personal take, and the creator shoutout + link on the LAST tweet only. Tighten "
            "wording; do not add fluff. Output ONLY the post text.\n\nCURRENT POST:\n" + post
        ) + lang_directive(lang, "x")
        post = clean_output(generate_post(f"x_{lang}", system, task, agent, model, out_dir))
    return post


def generate_with_claude(system: str, task: str, model: str | None) -> str:
    cmd = ["claude", "-p", task, "--output-format", "text",
           "--append-system-prompt", system]
    if model:
        cmd += ["--model", model]
    out = run(cmd, capture=True)
    return out.strip()


def generate_with_codex(system: str, task: str, model: str | None,
                        out_dir: Path, tag: str) -> str:
    last = out_dir / f".codex_{tag}.txt"
    prompt = f"{system}\n\n----\n\n{task}"
    cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only",
           "-o", str(last)]
    if model:
        cmd += ["--model", model]
    cmd += [prompt]
    run(cmd, capture=True, check=False)  # codex prints warnings to stderr
    if last.exists():
        return last.read_text(encoding="utf-8").strip()
    die("codex exec produced no output file")
    return ""


def generate_post(platform: str, system: str, task: str, agent: str,
                  model: str | None, out_dir: Path) -> str:
    if agent == "codex":
        return generate_with_codex(system, task, model, out_dir, platform)
    return generate_with_claude(system, task, model)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="sns_helper",
        description="Turn a YouTube video into an X post and a LinkedIn post.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", help="YouTube URL")
    p.add_argument("--agent", choices=["claude", "codex"], default="claude",
                   help="Which agent CLI writes the posts (default: claude)")
    p.add_argument("--model", default=None,
                   help="Override the agent model (else the CLI default)")
    p.add_argument("--transcriber",
                   choices=["auto", "subs", "whisper", "elevenlabs"], default="auto",
                   help="Transcript source. auto = captions -> whisper (default)")
    p.add_argument("--whisper-model", default="turbo", help="Whisper model")
    p.add_argument("--language", default=None,
                   help="Source language override (ISO code, e.g. ko) for caption "
                        "selection + Whisper. Default: auto-detect from the video.")
    p.add_argument("--transcript-file", default=None,
                   help="Use an existing transcript (.txt/.srt/.vtt), skip fetching")
    p.add_argument("--profile", default=None,
                   help="Path to profile.json (voice/identity)")
    p.add_argument("--only", choices=["x", "linkedin"], default=None,
                   help="Generate only one platform")
    p.add_argument("--lang", choices=["en", "ko", "both"], default=None,
                   help="Output language(s). Default: from profile.languages, else en")
    p.add_argument("--note", default=None,
                   help="Extra host note to weave in near the end, e.g. a "
                        "next-episode teaser (things the video itself can't tell us)")
    p.add_argument("--comments", type=int, default=0, metavar="N",
                   help="Fetch N top comments as audience-signal context (0 = off)")
    p.add_argument("--cohosts", default=None,
                   help="Override profile.cohosts credit for this run, e.g. 'JB, JC'")
    p.add_argument("--interview", action="store_true",
                   help="Phase 1: ask you tailored questions (writes out/<id>/interview.md); "
                        "fill the answers and re-run to write the post from them")
    p.add_argument("--answers-file", default=None,
                   help="Interview answers file to inject directly (skip the phase-1 prompt)")
    p.add_argument("--out-dir", default=None,
                   help="Output dir (default: ./out/<video_id>)")
    p.add_argument("--max-transcript-words", type=int, default=16000,
                   help="Cap transcript words sent to the writer (default 16000)")
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse_args(argv)

    for name in ("system.md", "x_post.md", "linkedin_post.md"):
        if not (PROMPTS_DIR / name).exists():
            die(f"missing prompt template: prompts/{name}")
    system_tmpl = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")
    x_tmpl = (PROMPTS_DIR / "x_post.md").read_text(encoding="utf-8")
    li_tmpl = (PROMPTS_DIR / "linkedin_post.md").read_text(encoding="utf-8")

    # resolve video id early for the output dir
    require_exe("yt-dlp")
    vid_out = run(["yt-dlp", "--no-playlist", "--quiet", "--no-warnings",
                   "--print", "%(id)s", "--skip-download", args.url],
                  capture=True).strip().splitlines()
    video_id = vid_out[-1].strip() if vid_out else "video"

    out_dir = Path(args.out_dir).expanduser() if args.out_dir \
        else HERE / "out" / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"output dir: {out_dir}")

    meta = fetch_metadata(args.url, out_dir)
    summ = meta_summary(meta)
    log(f"title: {summ['title']!r}  |  channel: {summ['channel']!r}")

    transcript, source = get_transcript(
        args.url, out_dir, video_id, args.transcriber,
        args.whisper_model, args.language, args.transcript_file, meta)
    (out_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
    log(f"transcript source: {source}  ({len(transcript.split())} words)")

    profile = load_profile(args.profile)
    if args.cohosts is not None:
        profile = {**profile,
                   "cohosts": [s.strip() for s in args.cohosts.split(",") if s.strip()]}
    values = build_values(summ, profile, transcript, args.max_transcript_words)
    # The system prompt refers to {{TITLE}}/{{TRANSCRIPT}}/... as named concepts that
    # the task prompt delivers — so only the concrete PROFILE is substituted here.
    system = fill(system_tmpl, {"PROFILE": values["PROFILE"]})
    (out_dir / "generation_system.txt").write_text(system, encoding="utf-8")

    langs = resolve_langs(args.lang, profile)
    platforms = []
    if args.only != "linkedin":
        platforms.append("x")
    if args.only != "x":
        platforms.append("linkedin")

    # build (platform, lang, task) jobs
    own_note = ownership_directive(summ, profile)
    log(f"video ownership: {'OWN (host POV)' if is_own_video(summ, profile) else 'other'}")
    note_directive = ""
    if args.note:
        note_directive = (
            "\n\n# HOST NOTE TO INCLUDE\n"
            "Weave the following note in near the end of the post (just before the link), "
            "in the post's language and voice. Keep its meaning exactly; don't expand it "
            "or add claims to it:\n" + args.note)
    comments = fetch_comments(args.url, out_dir, args.comments) if args.comments > 0 else []
    com_note = comments_directive(comments)
    own = is_own_video(summ, profile)

    # --- interview: ask the poster for what the video can't tell us ---
    host_input = ""
    if args.answers_file:
        host_input = host_input_directive(parse_answers(Path(args.answers_file).expanduser()))
    elif args.interview:
        ipath = out_dir / "interview.md"
        qa = parse_answers(ipath) if ipath.exists() else []
        if any(a.strip() for _, a in qa):
            host_input = host_input_directive(qa)
            log(f"interview: using {sum(1 for _, a in qa if a.strip())} answers from {ipath.name}")
        else:
            if not ipath.exists():
                qlang = "ko" if "ko" in langs else "en"
                log("interview: generating questions ...")
                qtext = generate_questions(summ, transcript, comments, own,
                                           args.agent, args.model, out_dir, qlang, profile)
                write_interview_file(ipath, qtext, args.url)
            print(f"\n\033[1m인터뷰 질문을 작성했습니다:\033[0m {ipath}")
            print("답을 채운 뒤 같은 명령을 다시 실행하세요 (모르는 항목은 비워두면 [TODO]로 남깁니다).")
            print(f"\n{(ipath).read_text(encoding='utf-8')}")
            return

    jobs: list[tuple[str, str, str]] = []
    base = {"x": fill(x_tmpl, values), "linkedin": fill(li_tmpl, values)}
    for platform in platforms:
        for lang in langs:
            task = (base[platform] + own_note + note_directive + com_note
                    + voice_directive(platform, lang) + host_input
                    + lang_directive(lang, platform))
            jobs.append((platform, lang, task))
            (out_dir / f"generation_{platform}_{lang}_task.txt").write_text(
                task, encoding="utf-8")

    log(f"generating {', '.join(f'{p}/{l}' for p, l, _ in jobs)} with {args.agent}"
        f"{(' ('+args.model+')') if args.model else ''} ...")

    results: dict[tuple[str, str], str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(jobs))) as ex:
        futs = {
            ex.submit(generate_post, f"{platform}_{lang}", system, task,
                      args.agent, args.model, out_dir): (platform, lang)
            for platform, lang, task in jobs
        }
        for fut in concurrent.futures.as_completed(futs):
            key = futs[fut]
            results[key] = clean_output(fut.result())

    for (platform, lang) in list(results):
        if platform == "x":
            results[(platform, lang)] = repair_x(
                results[(platform, lang)], system, args.agent, args.model,
                out_dir, lang=lang)

    multi = len(langs) > 1
    suffix = (lambda l: f".{l}") if multi else (lambda l: "")

    out_files = []
    for platform in ("x", "linkedin"):
        for lang in langs:
            if (platform, lang) not in results:
                continue
            stem = "x_post" if platform == "x" else "linkedin_post"
            fname = f"{stem}{suffix(lang)}.txt"
            (out_dir / fname).write_text(results[(platform, lang)] + "\n",
                                         encoding="utf-8")
            out_files.append(out_dir / fname)

    # pretty print
    print()
    for platform in ("x", "linkedin"):
        for lang in langs:
            if (platform, lang) not in results:
                continue
            name = "X / TWITTER POST" if platform == "x" else "LINKEDIN POST"
            header = f"{name}  ·  {LANG_NAMES[lang]}" if multi else name
            bar = "═" * len(header)
            print(f"\n\033[1m{header}\033[0m\n{bar}\n")
            text = results[(platform, lang)]
            if platform == "x":
                tweets = [t.strip() for t in re.split(r"(?m)^\s*-{3,}\s*$", text)
                          if t.strip()]
                for i, tw in enumerate(tweets, 1):
                    n = x_char_count(tw)
                    flag = "  \033[31m⚠ over 280\033[0m" if n > 280 else ""
                    tag = f"tweet {i}/{len(tweets)}" if len(tweets) > 1 else "single tweet"
                    print(f"\033[2m[{tag} — {n} chars]{flag}\033[0m")
                    print(tw)
                    print()
            else:
                print(text)
                print()
    print("\033[2m" + "─" * 60 + "\033[0m")
    print(f"saved to: {out_dir}")
    for f in out_files:
        print(f"  • {f.name}")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        die("interrupted", code=130)
