---
description: Download my new LinkedIn posts (+ images) into the local archive
---

Sync my LinkedIn archive. Extra flags from me (optional): $ARGUMENTS

1. From the repo root, run:

   ```bash
   python3 linkedin_posts/tools/linkedin_download.py --new
   ```

   If I passed flags above, use them instead of `--new` — e.g. `--count 5`, `--all`,
   `--profile <public-id> --count 10`, `--include-reposts`. Reference:
   `linkedin_posts/tools/README.md`.

2. If it fails to authenticate: I must be logged into LinkedIn in **Chrome**, and the
   first run pops a macOS Keychain dialog ("Chrome Safe Storage") that I need to click
   **Allow** on — tell me to approve it, then retry.

3. Report: how many new posts were stored (dates + first lines), how many images, and the
   new total in `linkedin_posts/index.md`. Re-runs are idempotent (keyed by activity id) —
   no duplicates.
