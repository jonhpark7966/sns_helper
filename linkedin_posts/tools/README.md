# linkedin_download.py

Download original LinkedIn posts (+ images) into per-post folders. Drives the gstack
`browse` headless daemon and reuses your logged-in **Chrome** session.

## Requirements
- macOS with **Google Chrome**, logged into LinkedIn.
- gstack `browse` daemon installed (`~/.claude/skills/gstack/browse/dist/browse`).
- Python 3 (stdlib only — no pip installs).

## First run
The script decrypts your LinkedIn auth cookie (`li_at`) straight from Chrome, because the
browse cookie importer skips httpOnly cookies. macOS will pop a Keychain dialog
**"Chrome Safe Storage"** — click **Allow** (once). If nothing downloads, make sure you're
logged into LinkedIn in Chrome and retry.

## Usage
```bash
cd linkedin_posts/tools

# your most recent 5 original posts
python3 linkedin_download.py --count 5

# only posts you haven't stored yet (stops once it reaches a known post)
python3 linkedin_download.py --new

# everything the activity feed will serve
python3 linkedin_download.py --all

# someone else's recent posts
python3 linkedin_download.py --profile some-public-id --count 10

# include reposts / comments / likes (default: original posts only)
python3 linkedin_download.py --all --include-reposts
```

Flags:
- `--profile <id>` public profile id (default `jonhpark7966`, i.e. you).
- `--count N` | `--all` | `--new` pick one (default `--all`).
- `--out <dir>` output base (default: the `linkedin_posts/` folder).
- `--include-reposts` keep non-original items too.

## Output
```
linkedin_posts/
  posts/<YYYY-MM-DD>_<activityId>/
      post.md      # text + metadata + image refs
      meta.json    # structured record (urn, permalink, text, image lists, ...)
      img1.jpg     # uploaded photos (feedshare)
      linkthumb1.jpg  # link-preview thumbnail (articleshare), if any
  index.md         # rebuilt list of every stored post
  index.json       # aggregate of every meta.json
```

`--new` and re-runs are **idempotent**: posts are keyed by activity id, so existing folders
are reused and the index is rebuilt from whatever is on disk.

## How it works (for future you)
1. Ensures the browse session has `li_at`; if not, decrypts LinkedIn cookies from Chrome
   (`AES-128-CBC`, key = `PBKDF2-HMAC-SHA1(keychain "Chrome Safe Storage", "saltysalt",
   1003, 16)`, strips the `v10` prefix and the 32-byte domain-hash prefix) and imports the
   `.linkedin.com` subset while on a linkedin.com page.
2. Opens `/in/<profile>/recent-activity/all/`, scrolls until the mode's target is met,
   clicks "…더보기" to expand truncated text.
3. Extracts each `div.feed-shared-update-v2`: text, images, author, and whether it's an
   original post (no repost/comment/like context header).
4. Post date comes from the activity URN (`id >> 22` = ms since epoch). Real photos are
   `feedshare-*` URLs; `articleshare-160` are link-preview thumbnails.

## Limitations
- LinkedIn's activity feed serves a bounded window; `--all` gets what it will serve, not
  necessarily your entire lifetime history.
- DOM class names are LinkedIn's; if they change the layout, update the selectors in
  `EXTRACT_JS`.
