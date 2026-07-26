# lac-newsletter-feed

Keeps the "Past issues" list on <https://www.landerartcenter.com/subscribe> current
without anyone touching it on newsletter day.

`build_issues.py` runs twice daily in GitHub Actions, reads the public Mailchimp
campaign archive, strips the Tuesday resends, and commits `issues.json`. The website
fetches that file from `raw.githubusercontent.com`, which serves it with
`access-control-allow-origin: *`.

**This repository must stay public.** `raw.githubusercontent.com` will not serve a
private repository without a token, and the website has no way to supply one. If it
is made private the site does not error, it just silently falls back to the five
issues hard coded in the page and never updates again.

## Why a scheduled job instead of the browser fetching Mailchimp directly

Browser JavaScript cannot read the Mailchimp archive. Tested July 2026:

- the archive feed sends no `access-control-allow-origin`, even with an `Origin` header
- its CORS preflight returns 400
- it ignores a JSONP callback parameter
- Mailchimp's own archive JS widget returns 404, retired
- Squarespace's RSS block only publishes a feed, it cannot read one

A scheduled server is the only way in. This is one.

## What is in here

| file | what it does |
| --- | --- |
| `build_issues.py` | reads the archive, dedupes, writes `issues.json` |
| `.github/workflows/build-issues.yml` | runs it twice daily and on demand |
| `issues.json` | the output the website reads |

## Nothing sensitive lives here

The audience and list IDs in `build_issues.py` are already public: they appear in the
archive URL, in the signup form on the website, and in the page embed. `issues.json`
contains newsletter subject lines, dates, and links that Mailchimp already publishes
at a public address. There are no subscriber records, email addresses, or credentials
in this repository, and none should ever be added.

## If it breaks

A failed run shows red in the Actions tab and writes nothing, so the website keeps
serving the last good `issues.json`. The likely cause is Mailchimp changing the markup
of the archive page, which would trip the "archive page returned no campaigns" guard.
