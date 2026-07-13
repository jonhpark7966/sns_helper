#!/usr/bin/env python3
"""
linkedin_download.py — download original LinkedIn posts + images into per-post folders.

Drives the gstack `browse` headless daemon and reuses your logged-in Chrome session
(it decrypts the httpOnly `li_at` auth cookie straight from Chrome, because the browse
cookie importer skips httpOnly cookies).

Examples
--------
  # your own most recent 5 original posts
  python3 linkedin_download.py --count 5

  # only posts you haven't stored yet (stops when it hits a known post)
  python3 linkedin_download.py --new

  # everything the activity feed will serve
  python3 linkedin_download.py --all

  # someone else's recent posts
  python3 linkedin_download.py --profile some-public-id --count 10

  # include reposts / comments / likes too (default: original posts only)
  python3 linkedin_download.py --all --include-reposts

Output layout (default base ./linkedin_posts):
  linkedin_posts/posts/<YYYY-MM-DD>_<activityId>/post.md, meta.json, img1.jpg, ...
  linkedin_posts/index.md, linkedin_posts/index.json   (rebuilt from every stored post)

Notes
-----
- macOS + Chrome only for the cookie step. First run pops a Keychain dialog
  ("Chrome Safe Storage") — click Allow. Log into LinkedIn in Chrome first.
- Original vs repost/comment is detected from the grey context header on each item.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

HOME = os.path.expanduser("~")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# ---------------------------------------------------------------- browse daemon


def find_browse():
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True).stdout.strip()
    cand = []
    if root:
        cand.append(os.path.join(root, ".claude/skills/gstack/browse/dist/browse"))
    cand.append(os.path.join(HOME, ".claude/skills/gstack/browse/dist/browse"))
    for c in cand:
        if os.access(c, os.X_OK):
            return c
    sys.exit("browse daemon not found. Install gstack, then retry.")


def b(browse, *args, timeout=120):
    return subprocess.run([browse, *args], capture_output=True, text=True,
                          timeout=timeout).stdout


def run_js(browse, expr, timeout=120):
    """Eval JS in the page and return the JSON payload the expression yields.

    The expression must evaluate to a value; we wrap it so the payload survives
    any wrapper lines the daemon prints around external content.
    """
    wrapped = "'<<<S>>>'+JSON.stringify((()=>{return (%s);})())+'<<<E>>>'" % expr
    out = b(browse, "js", wrapped, timeout=timeout)
    m = re.search(r"<<<S>>>(.*?)<<<E>>>", out, re.S)
    if not m:
        raise RuntimeError("no JS payload returned:\n" + out[:500])
    return json.loads(m.group(1))


# ---------------------------------------------------------------- chrome cookies


def chrome_safe_storage_key():
    pw = subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"]).strip()
    return hashlib.pbkdf2_hmac("sha1", pw, b"saltysalt", 1003, 16)


def decrypt_value(enc, key):
    if not enc:
        return None
    if enc[:3] in (b"v10", b"v11"):
        enc = enc[3:]
    iv = b" " * 16
    p = subprocess.run(
        ["openssl", "enc", "-aes-128-cbc", "-d", "-K", key.hex(), "-iv", iv.hex(), "-nopad"],
        input=enc, capture_output=True)
    out = p.stdout
    if not out:
        return None
    pad = out[-1]
    if 1 <= pad <= 16:
        out = out[:-pad]
    try:
        v = out.decode("utf-8")
        if v.isprintable():
            return v
    except Exception:
        pass
    try:
        return out[32:].decode("utf-8")   # newer Chrome prepends 32-byte domain hash
    except Exception:
        return None


def linkedin_cookies_from_chrome():
    src = os.path.join(HOME, "Library/Application Support/Google/Chrome/Default/Cookies")
    if not os.path.exists(src):
        sys.exit("Chrome cookie DB not found. Log into LinkedIn in Chrome first.")
    import sqlite3
    dst = "/tmp/li_dl_cookies.db"
    shutil.copy(src, dst)
    for ext in ("-wal", "-shm"):
        if os.path.exists(src + ext):
            shutil.copy(src + ext, dst + ext)
    con = sqlite3.connect(dst)
    rows = con.execute(
        "SELECT name, host_key, path, encrypted_value, is_secure, is_httponly, "
        "expires_utc, samesite FROM cookies WHERE host_key LIKE '%linkedin%'").fetchall()
    key = chrome_safe_storage_key()
    ss = {0: "None", 1: "Lax", 2: "Strict", -1: "None"}
    keep_domains = (".linkedin.com", ".www.linkedin.com", "www.linkedin.com")
    cookies = []
    for name, host, path, enc, secure, httponly, expires, samesite in rows:
        if host not in keep_domains:
            continue
        val = decrypt_value(enc, key)
        if val is None:
            continue
        exp = -1
        if expires and expires > 0:
            exp = expires / 1_000_000 - 11644473600
        cookies.append({"name": name, "value": val, "domain": host, "path": path or "/",
                        "expires": exp, "httpOnly": bool(httponly),
                        "secure": bool(secure), "sameSite": ss.get(samesite, "None")})
    for ext in ("", "-wal", "-shm"):
        try:
            os.remove(dst + ext)
        except OSError:
            pass
    return cookies


def ensure_auth(browse):
    have = '"name": "li_at"' in b(browse, "cookies")
    if have:
        return
    print("Importing LinkedIn session from Chrome "
          "(approve the macOS Keychain dialog if it appears)...")
    cookies = linkedin_cookies_from_chrome()
    if not any(c["name"] == "li_at" for c in cookies):
        sys.exit("Could not decrypt li_at from Chrome. Are you logged into LinkedIn there?")
    b(browse, "goto", "https://www.linkedin.com")
    tmp = "/tmp/li_dl_cookies.json"
    json.dump(cookies, open(tmp, "w"))
    b(browse, "cookie-import", tmp)
    os.remove(tmp)
    if '"name": "li_at"' not in b(browse, "cookies"):
        sys.exit("Cookie import did not stick. Retry, or re-login in Chrome.")


# ---------------------------------------------------------------- extraction

EXTRACT_JS = r"""
(() => {
  const items = [...document.querySelectorAll('div.feed-shared-update-v2')];
  const RE = /reposted|reshared|commented|likes this|celebrates|loves this|퍼감|재게시|댓글|좋아합니다|추천|축하/i;
  return items.map(el => {
    const urn = el.getAttribute('data-urn') || '';
    const actorEl = el.querySelector('.update-components-actor__title');
    const actor = actorEl ? actorEl.innerText.replace(/\s+/g,' ').trim() : '';
    const hdrEl = el.querySelector('.update-components-header__text-view, .update-components-header');
    const hdr = hdrEl ? hdrEl.innerText.replace(/\s+/g,' ').trim() : '';
    const isOriginal = !RE.test(hdr) && (actor.includes('• 나') || !hdr);
    const textEl = el.querySelector('.update-components-text, .feed-shared-update-v2__description, .update-components-update-v2__commentary');
    const text = textEl ? textEl.innerText : '';
    const imgs = [...el.querySelectorAll('.update-components-image img, img.update-components-image__image, .feed-shared-image img, [class*=carousel] img')]
      .map(i => i.getAttribute('src') || i.getAttribute('data-delayed-url') || '').filter(Boolean);
    const posters = [...el.querySelectorAll('video')].map(v => v.getAttribute('poster') || '').filter(Boolean);
    return { urn, actor, header: hdr, isOriginal, text,
             images: [...new Set(imgs)], videoPosters: [...new Set(posters)] };
  });
})()
"""


def load_posts(browse):
    return run_js(browse, EXTRACT_JS.strip())


def expand_see_more(browse):
    js = r"""(() => { let n=0;
      document.querySelectorAll('div.feed-shared-update-v2 button').forEach(x=>{
        const t=(x.innerText||x.getAttribute('aria-label')||'');
        if(/더 보기|더보기|see more|…\s*more/i.test(t)){try{x.click();n++;}catch(e){}}});
      return n; })()"""
    run_js(browse, js)


def scroll_and_collect(browse, mode, count, existing_urns):
    """Scroll the activity feed until we have what `mode` needs, then return raw items."""
    prev, stable = -1, 0
    for _ in range(80):
        b(browse, "js", "window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        n = run_js(browse, "document.querySelectorAll('div.feed-shared-update-v2').length")
        items = load_posts(browse)
        originals = [it for it in items if it["isOriginal"]]
        if mode == "count" and len(originals) >= count:
            break
        if mode == "new" and any(it["urn"].split(":")[-1] in existing_urns for it in items):
            break
        if n == prev:
            stable += 1
            # nudge a load-more button if present
            run_js(browse, r"""(()=>{const btn=[...document.querySelectorAll('button')]
                .find(x=>/더 보기|Show more|load/i.test(x.textContent));
                if(btn){btn.click();return 1;}return 0;})()""")
            time.sleep(2)
            if stable >= 2:
                break
        else:
            stable = 0
        prev = n
    expand_see_more(browse)
    time.sleep(1)
    return load_posts(browse)


# ---------------------------------------------------------------- storage


def urn_to_date(urn):
    act_id = int(urn.split(":")[-1])
    ms = act_id >> 22
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")


def classify_images(images):
    feed = [u for u in images if "feedshare" in u]
    thumb = [u for u in images if "articleshare" in u]
    return feed, thumb


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Referer": "https://www.linkedin.com/"})
    with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
        f.write(r.read())


def existing_urn_set(posts_dir):
    urns = set()
    if not os.path.isdir(posts_dir):
        return urns
    for d in os.listdir(posts_dir):
        mp = os.path.join(posts_dir, d, "meta.json")
        if os.path.exists(mp):
            try:
                urns.add(json.load(open(mp))["urn"].split(":")[-1])
            except Exception:
                pass
    return urns


def store_post(posts_dir, profile, it):
    urn = it["urn"]
    date = urn_to_date(urn)
    folder = os.path.join(posts_dir, f"{date}_{urn.split(':')[-1]}")
    os.makedirs(folder, exist_ok=True)
    feed, thumb = classify_images(it["images"])
    img_files, thumb_files = [], []
    for j, u in enumerate(feed):
        fn = f"img{j+1}.jpg"
        try:
            download(u, os.path.join(folder, fn)); img_files.append(fn)
        except Exception as e:
            print(f"  ! image failed ({fn}): {e}")
    for j, u in enumerate(thumb):
        fn = f"linkthumb{j+1}.jpg"
        try:
            download(u, os.path.join(folder, fn)); thumb_files.append(fn)
        except Exception as e:
            print(f"  ! thumb failed ({fn}): {e}")
    meta = {
        "urn": urn, "profile": profile, "date": date,
        "permalink": f"https://www.linkedin.com/feed/update/{urn}/",
        "actor": it["actor"], "header": it["header"], "is_original": it["isOriginal"],
        "text": it["text"], "images": img_files, "link_thumbnails": thumb_files,
        "image_urls": feed, "thumb_urls": thumb,
    }
    json.dump(meta, open(os.path.join(folder, "meta.json"), "w"),
              ensure_ascii=False, indent=2)
    md = [f"# {date} — {urn.split(':')[-1]}", "",
          f"- Permalink: {meta['permalink']}",
          f"- Author: {it['actor']}",
          f"- Original post: {it['isOriginal']}"]
    if img_files:
        md.append(f"- Images: {', '.join(img_files)}")
    if thumb_files:
        md.append(f"- Link thumbnail: {', '.join(thumb_files)}")
    md.append("")
    for fn in img_files:
        md.append(f"![{fn}]({fn})")
    if img_files:
        md.append("")
    md += ["```text", it["text"].rstrip(), "```", ""]
    open(os.path.join(folder, "post.md"), "w").write("\n".join(md))
    return folder


def rebuild_index(base):
    posts_dir = os.path.join(base, "posts")
    rows = []
    for d in sorted(os.listdir(posts_dir), reverse=True):
        mp = os.path.join(posts_dir, d, "meta.json")
        if os.path.exists(mp):
            rows.append(json.load(open(mp)))
    json.dump(rows, open(os.path.join(base, "index.json"), "w"),
              ensure_ascii=False, indent=2)
    lines = [f"# LinkedIn posts index ({len(rows)} stored)", ""]
    for r in rows:
        first = (r["text"].strip().splitlines() or [""])[0][:80]
        lines.append(f"- **{r['date']}** [`{r['urn'].split(':')[-1]}`](posts/"
                     f"{r['date']}_{r['urn'].split(':')[-1]}/post.md) "
                     f"({len(r['images'])} img) — {first}")
    open(os.path.join(base, "index.md"), "w").write("\n".join(lines) + "\n")
    return len(rows)


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="Download LinkedIn original posts + images.")
    ap.add_argument("--profile", default="jonhpark7966", help="public profile id")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--count", type=int, help="download recent N posts")
    g.add_argument("--all", action="store_true", help="download all available")
    g.add_argument("--new", action="store_true", help="only posts not already stored")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), ".."),
                    help="output base dir (default: the linkedin_posts folder)")
    ap.add_argument("--include-reposts", action="store_true",
                    help="also store reposts/comments/likes")
    args = ap.parse_args()

    mode = "all"
    count = 0
    if args.count:
        mode, count = "count", args.count
    elif args.new:
        mode = "new"

    base = os.path.abspath(args.out)
    posts_dir = os.path.join(base, "posts")
    os.makedirs(posts_dir, exist_ok=True)
    existing = existing_urn_set(posts_dir)

    browse = find_browse()
    b(browse, "status")
    ensure_auth(browse)

    url = f"https://www.linkedin.com/in/{args.profile}/recent-activity/all/"
    b(browse, "goto", url)
    time.sleep(4)
    cur = run_js(browse, "window.location.href")
    if "login" in cur or "authwall" in cur:
        sys.exit("Hit the LinkedIn login/authwall — session not valid. "
                 "Re-login in Chrome and retry.")

    print(f"Loading posts for '{args.profile}' (mode={mode}"
          f"{', N=' + str(count) if count else ''})...")
    items = scroll_and_collect(browse, mode, count, existing)

    wanted = items if args.include_reposts else [it for it in items if it["isOriginal"]]
    # de-dupe by urn, keep feed order (newest first)
    seen, ordered = set(), []
    for it in wanted:
        if it["urn"] and it["urn"] not in seen:
            seen.add(it["urn"]); ordered.append(it)

    if mode == "count":
        ordered = ordered[:count]
    if mode == "new":
        ordered = [it for it in ordered if it["urn"].split(":")[-1] not in existing]

    print(f"Storing {len(ordered)} posts into {posts_dir} ...")
    for it in ordered:
        folder = store_post(posts_dir, args.profile, it)
        print(f"  saved {os.path.relpath(folder, base)}")

    total = rebuild_index(base)
    print(f"Done. {len(ordered)} new/updated; {total} posts stored total.")
    print(f"Index: {os.path.join(base, 'index.md')}")


if __name__ == "__main__":
    main()
