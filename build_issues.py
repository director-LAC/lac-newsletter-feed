#!/usr/bin/env python3
"""
Builds issues.json for the Lander Art Center /subscribe page.

Runs inside GitHub Actions, which is the whole point: this is a SERVER, so the
CORS wall that blocks the browser does not apply here. It reads Mailchimp's public
archive, removes the Tuesday resends, resolves the short links, and writes a small
JSON file that the website can safely fetch.

WHY THE DEDUPE EXISTS. Mailchimp lists every issue twice, a Saturday original and a
Tuesday resend three days later. Verified July 2026 by content hash across all 20
archive entries: eight pairs were byte identical and two differed only in the subject
line. So the pairs are matched on body content with the title stripped out, and the
EARLIER of each pair is kept. A brand new issue that has not been resent yet has no
partner and is kept as is.

FAILS LOUD, NOT QUIET. If anything goes wrong the script exits non-zero and writes
nothing. The website keeps serving the last good issues.json, and the Actions run
shows red so somebody knows.
"""
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime

ARCHIVE = ("https://us21.campaign-archive.com/home/"
           "?u=a25ddc5c2791b64036a7752c2&id=6a926fe853")
KEEP = 5           # how many issues the page shows
UA = "Mozilla/5.0 (compatible; LAC-site-builder/1.0)"
MIN_EXPECTED = 3   # sanity floor, below this we assume the scrape broke


def fetch(url, tries=3, timeout=45):
    """Mailchimp returns transient 503s. Five of twenty links did on the first
    pass in July 2026 and all five were fine on retry. Never trust one attempt."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.geturl(), r.read().decode("utf-8", "replace")
        except Exception as exc:
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url} ({last})")


def body_signature(markup):
    """Hash the readable body with the title removed, so a resend that only changed
    its subject line still matches its original."""
    txt = re.sub(r"<title[^>]*>.*?</title>", " ", markup, flags=re.S | re.I)
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", txt, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return hashlib.md5(txt.encode()).hexdigest(), len(txt)


def main():
    _, page = fetch(ARCHIVE)
    entries = re.findall(
        r'<li class="campaign">(\d{2}/\d{2}/\d{4}) - <a href="([^"]+)" title="([^"]*)"',
        page)
    if not entries:
        raise RuntimeError("archive page returned no campaigns, the markup probably changed")
    print(f"archive lists {len(entries)} entries")

    seen = {}
    for date_str, short_url, title in entries:
        date = datetime.strptime(date_str, "%m/%d/%Y").date()
        title = html.unescape(title).strip()
        final, markup = fetch(short_url)
        sig, length = body_signature(markup)
        print(f"  {date}  {sig[:8]}  {length:>6} chars  {title[:44]}")
        prior = seen.get(sig)
        if prior is None:
            seen[sig] = {"date": date, "title": title, "url": final}
            continue
        # keep the EARLIER send's date and subject, that is the original
        if date < prior["date"]:
            prior["date"], prior["title"] = date, title
        # but take a mailchi.mp address from whichever send happens to carry one
        if "mailchi.mp" in final and "mailchi.mp" not in prior["url"]:
            prior["url"] = final

    issues = sorted(seen.values(), key=lambda i: i["date"], reverse=True)
    print(f"\n{len(entries)} entries collapsed to {len(issues)} unique issues")
    if len(issues) < MIN_EXPECTED:
        raise RuntimeError(f"only {len(issues)} issues survived dedupe, refusing to publish")

    out = [{"date": i["date"].isoformat(), "title": i["title"], "url": i["url"]}
           for i in issues[:KEEP]]
    for row in out:
        if not row["url"].startswith("https://"):
            raise RuntimeError(f"refusing to publish a non-https url: {row['url']}")

    with open("issues.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(f"\nwrote issues.json with {len(out)} issues:")
    for row in out:
        print(f"   {row['date']}  {row['title'][:56]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
