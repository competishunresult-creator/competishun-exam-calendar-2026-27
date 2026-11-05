# Competishun Exam News — developer guide

26 SEO pages: one common page plus one page per exam (25). They are rebuilt automatically every hour.

## What is in this folder

| File | What it is |
|---|---|
| `news.json` | All news items. The hourly task adds new items here. |
| `exam-pages.json` | SEO text for each exam page: URL slug, title tag, meta description, H1, intro, keywords. |
| `build.py` | Builds the pages from `exams.csv` + `exam-pages.json` + `news.json`. |
| `style.css`, `assets/` | Shared design (Competishun blue `#01009A`, orange `#F25E04`, cream `#F7F2E6`; fonts Jost + Inter) and logos. |
| `../site/exam-news/` | **The finished pages.** Ready-to-serve static HTML. Do not edit by hand; it is overwritten every hour. |

## Page URLs

- Common page: `https://competishun.com/exam-news/`
- Exam pages: `https://competishun.com/exam-news/<slug>/` (for example `/exam-news/jee-advanced-2027/`, `/exam-news/neet-ug-2027/`)
- Sitemap: `https://competishun.com/exam-news/sitemap.xml`

All 25 slugs are in `exam-pages.json`.

## How to make it live (recommended)

Serve the folder `site/exam-news/` at `https://competishun.com/exam-news/` and keep it in sync with GitHub:

1. Clone this repo on the web server.
2. Point `/exam-news/` to `site/exam-news/` (Nginx `alias`, Apache `Alias`, or a WordPress-side reverse proxy).
3. Add a cron job every 10 minutes: `cd /path/to/repo && git pull --ff-only`.

The pages are plain HTML with all news already inside the page, so Google can read everything. No JavaScript is needed.

If you prefer to build inside WordPress instead, use `site/exam-news/` as the exact reference for markup, meta tags and structured data, and read `news.json` + `exams.csv` on the server (not in the browser).

## SEO already included in every page

- Unique `<title>`, meta description, canonical URL, Open Graph tags
- One H1 with exam name and year; breadcrumb
- Structured data (JSON-LD): CollectionPage, BreadcrumbList, FAQPage
- FAQ answers built from the live calendar data (so they stay correct)
- Internal links: every exam page links to the common page and related exams; the common page links to all 25
- `sitemap.xml` with `lastmod` dates
- No ads

**After going live:** submit `sitemap.xml` in Google Search Console, and add the common page to the main site menu.

## Things to fill in

In `build.py` settings at the top: `WHATSAPP_URL` and `COUNSELLOR_URL` (now `#`).

## Data rules (for anyone editing `news.json`)

Each item needs: `id` (unique), `date` (YYYY-MM-DD), `exam` (a slug from `exam-pages.json`), `type`, `status` (`Official`, `Expected` or `News report`), `headline`, `summary`, `source`, `source_url`, `image` (`calendar`, `form`, `admit`, `result`, `alert`, `cbt`). Optional: `top: true` to make it the top story.

Run `python3 news/build.py` after any change. It stops with a clear message if anything is wrong.
