#!/usr/bin/env python3
"""Builds the Competishun Exam News pages.

Reads:  exams.csv (calendar data), news/exam-pages.json (SEO text per exam), news/news.json (news items)
Writes: site/exam-news/index.html            -> common page (all exams)
        site/exam-news/<slug>/index.html     -> one page per exam (25)
        site/exam-news/assets/*              -> css and logos
        site/exam-news/sitemap.xml

Run:  python3 news/build.py           (fails with a clear message if any data is wrong)
"""
import csv, json, os, re, shutil, sys
from datetime import datetime, date, timedelta, timezone
from html import escape

# ---------------- settings (edit these) ----------------
SITE = "https://competishun.com"
BASE_PATH = "/exam-news/"                      # public folder for these pages
WHATSAPP_URL = "#"                              # TODO: Competishun WhatsApp alerts link
COUNSELLOR_URL = "#"                            # TODO: counsellor call / form link
COURSES_URL = "https://competishun.com/"
CALENDAR_URL = "https://competishun.com/engineering-entrance-exam-calendar/"
MAX_NEWS_COMMON = 30                            # items on the common page
NEWS_DAYS_COMMON = 60                           # older items drop off the common page
# -------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_DIR = os.path.join(ROOT, "news")
OUT = os.path.join(ROOT, "site", "exam-news")
IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)
TODAY = NOW.date()
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STATUSES = {"Official", "Expected", "News report"}
IMAGES = {"calendar", "form", "admit", "result", "alert", "cbt"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
TABS = ["jee-main-2027", "jee-advanced-2027", "neet-ug-2027", "bitsat-2027", "viteee-2027", "mht-cet-2027", "comedk-uget-2027"]
GROUP_ORDER = ["National exams", "Private university exams", "State exams", "Science institutes"]


def fail(msg):
    sys.exit("BUILD FAILED: " + msg)


def nice(d):
    return f"{MONTHS[d.month-1]} {d.day} {d.year}"


def pdate(s):
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


def txt(s):
    """Calendar text uses ' | ' as a line break."""
    return (s or "").replace(" | ", "; ").strip()


# ---------------- load + validate ----------------
def load():
    with open(os.path.join(ROOT, "exams.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    exams = {int(r["order"]): r for r in rows}
    with open(os.path.join(NEWS_DIR, "exam-pages.json"), encoding="utf-8") as f:
        pages = json.load(f)
    with open(os.path.join(NEWS_DIR, "news.json"), encoding="utf-8") as f:
        news = json.load(f)

    slugs = {}
    for p in pages:
        for k in ("order", "slug", "short", "group", "title", "description", "h1", "intro", "keywords", "image"):
            if k not in p or p[k] in ("", None):
                fail(f"exam-pages.json: '{k}' missing for {p.get('slug')}")
        if p["order"] not in exams:
            fail(f"exam-pages.json: order {p['order']} not in exams.csv")
        if p["group"] not in GROUP_ORDER:
            fail(f"exam-pages.json: unknown group {p['group']}")
        if len(p["title"]) > 65:
            print(f"warning: title over 65 chars for {p['slug']}")
        p["row"] = exams[p["order"]]
        slugs[p["slug"]] = p
    if len(slugs) != len(exams):
        fail(f"exam-pages.json has {len(slugs)} exams but exams.csv has {len(exams)}")

    seen = set()
    for it in news["items"]:
        for k in ("id", "date", "exam", "type", "status", "headline", "summary", "source", "source_url", "image"):
            if not it.get(k):
                fail(f"news.json: '{k}' missing in item {it.get('id')}")
        if it["id"] in seen:
            fail(f"news.json: duplicate id {it['id']}")
        seen.add(it["id"])
        if not ISO.match(it["date"]):
            fail(f"news.json: bad date {it['date']} in {it['id']}")
        if it["exam"] not in slugs:
            fail(f"news.json: unknown exam slug {it['exam']} in {it['id']}")
        if it["status"] not in STATUSES:
            fail(f"news.json: status must be one of {STATUSES} in {it['id']}")
        if it["image"] not in IMAGES:
            fail(f"news.json: image must be one of {IMAGES} in {it['id']}")
        if not it["source_url"].startswith("http"):
            fail(f"news.json: source_url must be a full link in {it['id']}")
    items = sorted(news["items"], key=lambda x: (x["date"], x.get("time", "")), reverse=True)
    return slugs, items, news.get("updated_at")


# ---------------- exam status helpers ----------------
def windows(r):
    out = []
    for s in ("s1", "s2"):
        lab = r.get(f"{s}_label") or ""
        out.append(dict(label=lab, rs=pdate(r[f"{s}_reg_start"]), re=pdate(r[f"{s}_reg_end"]),
                        es=pdate(r[f"{s}_exam_start"]), ee=pdate(r[f"{s}_exam_end"]) or pdate(r[f"{s}_exam_start"])))
    return out


def status(r):
    if r.get("status_override"):
        return r["status_override"], "wait"
    for w in windows(r):
        if w["rs"] and w["re"] and w["rs"] <= TODAY <= w["re"]:
            return ("Registration open" + (f" ({w['label']})" if w["label"] else "")), "open"
    for w in windows(r):
        if w["es"] and w["ee"] and w["es"] <= TODAY <= w["ee"]:
            return "Exam in progress", "open"
    for w in windows(r):
        if w["es"] and TODAY < w["es"]:
            return "Exam on " + nice(w["es"]), "wait"
    if r["date_type"] == "Expected":
        return "Official notice awaited", "wait"
    return r["date_type"], "wait"


def next_deadline(r):
    """Nearest upcoming official date for this exam: (date, what)."""
    best = None
    for w in windows(r):
        lab = (w["label"] + " ") if w["label"] else ""
        for d, what in ((w["re"], lab + "last date"), (w["es"], lab + "exam")):
            if d and d >= TODAY and (best is None or d < best[0]):
                best = (d, what)
    return best


# ---------------- html pieces ----------------
def thumb(kind, label, h=None):
    bg = {"calendar": "#01009A", "form": "#1714B8", "admit": "#00006B", "result": "#F25E04", "alert": "#D14E00", "cbt": "#2B28C4"}[kind]
    ac = "#01009A" if kind in ("result", "alert") else "#FF8A3D"
    W = 'fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"'
    A = f'fill="none" stroke="{ac}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'
    art = {
        "calendar": f'<g {W}><rect x="120" y="52" width="120" height="112" rx="12"/><path d="M120 82H240M148 40V62M212 40V62M140 102h14M168 102h14M196 102h14M140 126h14M168 126h14M140 148h14M168 148h14M196 148h14"/></g><circle cx="203" cy="126" r="14" {A}/>',
        "form": f'<g {W}><path d="M130 40H210L236 66V176H130Z"/><path d="M210 40V66H236M148 90H218M148 110H218M148 130H196"/></g><g {A}><path d="M246 108L262 124L222 164L204 168L208 150Z"/><path d="M150 154l8 8l16-16"/></g>',
        "admit": f'<g {W}><rect x="96" y="58" width="168" height="108" rx="12"/><rect x="112" y="78" width="44" height="54" rx="6"/><path d="M170 84H244M170 102H234M170 120H220"/></g><path d="M112 148V156M118 148V156M126 148V156M130 148V156M138 148V156M146 148V156M150 148V156M158 148V156" stroke="{ac}" stroke-width="3"/><circle cx="134" cy="98" r="9" fill="none" stroke="{ac}" stroke-width="3"/>',
        "result": f'<g {W}><path d="M110 170H250"/><rect x="124" y="128" width="22" height="42" rx="3"/><rect x="158" y="106" width="22" height="64" rx="3"/><rect x="192" y="82" width="22" height="88" rx="3"/></g><path d="M232 46l7 14l15 2l-11 10l3 15l-14-7l-14 7l3-15l-11-10l15-2Z" fill="{ac}"/>',
        "alert": f'<g {W}><path d="M130 96V128H150L200 156V68L150 96Z"/><path d="M150 128L158 160H172L166 132"/></g><g {A}><path d="M218 92q14 20 0 40"/><path d="M232 78q28 34 0 68"/></g>',
        "cbt": f'<g {W}><rect x="100" y="50" width="160" height="100" rx="10"/><path d="M160 150L152 176H208L200 150M120 74H200M120 94H176"/><circle cx="126" cy="122" r="6"/><circle cx="170" cy="122" r="6"/></g><circle cx="214" cy="122" r="7" fill="{ac}"/>',
    }[kind]
    style = f"background:{bg};" + (f"height:{h}px;" if h else "")
    return (f'<div class="thumb" style="{style}"><svg viewBox="0 0 360 220" preserveAspectRatio="xMidYMid meet" role="img" aria-label="{escape(label)} news">'
            f'<circle cx="320" cy="20" r="90" fill="#fff" fill-opacity=".06"/><circle cx="30" cy="210" r="70" fill="#fff" fill-opacity=".06"/>{art}</svg>'
            f'<span class="tlabel">{escape(label.upper())}</span></div>')


def st_badge(s):
    cls = {"Official": "st-official", "Expected": "st-expected", "News report": "st-report"}[s]
    return f'<span class="st {cls}">{escape(s)}</span>'


def news_item(it, pages, rel, show_exam=True):
    p = pages[it["exam"]]
    chip = f'<a class="exam-chip" href="{rel}{p["slug"]}/">{escape(p["short"])} 2027</a>' if show_exam else ""
    d = pdate(it["date"])
    return f'''<article class="item" id="{escape(it["id"])}">
  {thumb(it["image"], p["short"] + " 2027")}
  <div class="body">
    <div class="meta">{chip}<span class="muted">· {escape(it["type"])}</span>{st_badge(it["status"])}</div>
    <h3><a href="{escape(it["source_url"])}" rel="noopener" target="_blank">{escape(it["headline"])}</a></h3>
    <p>{escape(it["summary"])}</p>
    <div class="src"><time datetime="{it["date"]}">{nice(d)}</time> · Source: <a href="{escape(it["source_url"])}" rel="noopener" target="_blank">{escape(it["source"])}</a></div>
  </div>
</article>'''


def head(title, desc, canonical, rel, jsonld, keywords=None):
    kw = f'\n<meta name="keywords" content="{escape(", ".join(keywords))}">' if keywords else ""
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">{kw}
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Competishun">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}{BASE_PATH}assets/competishun-logo-color.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{rel}assets/style.css">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>'''


def header(rel, pages, active):
    tabs = [f'<a href="{rel}" class="{"on" if active == "all" else ""}">All News</a>']
    for s in TABS:
        tabs.append(f'<a href="{rel}{s}/" class="{"on" if active == s else ""}">{escape(pages[s]["short"])}</a>')
    tabs.append(f'<a href="{rel}#all-exams">All 25 exams</a>')
    return f'''<div class="topbar"><div class="wrap"><span>{NOW.strftime("%A")} · {nice(TODAY)} · <span class="live">Updated every hour</span></span>
<nav aria-label="Competishun"><a href="{COURSES_URL}">Courses</a><a href="{COURSES_URL}">Test Series</a><a href="{CALENDAR_URL}">Exam Calendar</a></nav></div></div>
<header class="site-header"><div class="wrap brandrow">
  <a class="brand" href="{SITE}/"><img src="{rel}assets/competishun-logo-white.png" alt="Competishun — The Power of Real Gurus" width="257" height="38"><span class="tag">EXAM NEWS</span></a>
  <div class="head-btns"><a class="btn btn-ghost" href="{rel}#all-exams">All 25 exams</a><a class="btn btn-orange" href="{WHATSAPP_URL}">Get exam alerts</a></div>
</div>
<div class="wrap"><nav class="tabs" aria-label="Exam news sections">{"".join(tabs)}</nav></div></header>'''


def footer(rel, pages):
    top = "".join(f'<a href="{rel}{s}/">{escape(pages[s]["short"])} 2027 News</a>' for s in TABS[:5])
    return f'''<footer class="site-footer"><div class="wrap foot-grid">
<div><img src="{rel}assets/competishun-logo-white.png" alt="Competishun" width="216" height="32"><p>Verified exam news for JEE and NEET students. We check official exam websites every hour. No ads.</p></div>
<div><h2>Exam news</h2>{top}<a href="{rel}#all-exams" style="color:#FF8A3D;font-weight:600">All 25 exams →</a></div>
<div><h2>Useful links</h2><a href="{CALENDAR_URL}">Exam Calendar 2026-27</a><a href="{COURSES_URL}">JEE 2027 Courses</a><a href="{COURSES_URL}">Test Series</a></div>
<div><h2>Get free exam alerts</h2><p>Last dates, admit cards and results on WhatsApp.</p><a class="btn btn-orange" style="display:inline-flex" href="{WHATSAPP_URL}">Join on WhatsApp</a></div>
</div><div class="wrap foot-bottom"><span>© {TODAY.year} Competishun · The Power of Real Gurus · Jaipur</span><span>Always confirm dates on the official exam website.</span></div></footer>
</body></html>'''


def cta():
    return f'''<div class="cta"><h2>Never miss a last date</h2><p>Free WhatsApp alerts for registration, admit card and result updates.</p>
<a class="btn btn-orange" href="{WHATSAPP_URL}">Join WhatsApp alerts</a><a class="btn btn-outline" href="{COUNSELLOR_URL}">Talk to a counsellor</a></div>'''


def faq_html(qs):
    return "".join(f'<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>' for q, a in qs)


def faq_ld(qs):
    return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qs]}


def exam_faqs(p):
    r, n = p["row"], p["short"] + " 2027"
    qs = [
        (f"When is the {n} exam?", f"{txt(r['exam_dates'])}." + (" These dates are expected and not yet official." if r["date_type"] == "Expected" else "")),
        (f"When will {n} registration start?", txt(r["registration"]) + "."),
        (f"What is the last date to apply for {n}?", txt(r["last_date"]) + "."),
        (f"Who conducts {n} and what is the official website?", f"{n} is conducted by {r['conducting_body']}. The official website is {r['official_url']}"),
    ]
    return qs


def directory_html(pages, rel):
    groups = ""
    for g in GROUP_ORDER:
        links = "".join(f'<a href="{rel}{p["slug"]}/">{escape(p["short"])} 2027 News</a>' for p in sorted(pages.values(), key=lambda x: x["order"]) if p["group"] == g)
        groups += f'<div><h3>{escape(g)}</h3>{links}</div>'
    return f'''<section class="dir" id="all-exams" aria-labelledby="dir"><h2 id="dir">All 25 exam news pages</h2>
    <p style="margin:6px 0 0;color:#4A4030">Each exam has its own page with the latest news, dates and FAQs.</p><div class="dir-grid">{groups}</div></section>'''


# ---------------- pages ----------------
def build_exam(p, pages, items):
    r, slug = p["row"], p["slug"]
    rel = "../"
    canonical = f"{SITE}{BASE_PATH}{slug}/"
    mine = [it for it in items if it["exam"] == slug]
    stext, skind = status(r)
    nd = next_deadline(r)
    verified = pdate(r["verified_on"]) if ISO.match(r.get("verified_on", "")) else TODAY
    modified = max([pdate(it["date"]) for it in mine] + [verified])
    qs = exam_faqs(p)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": p["h1"], "description": p["description"], "url": canonical,
         "dateModified": modified.isoformat(), "inLanguage": "en-IN",
         "publisher": {"@type": "EducationalOrganization", "name": "Competishun", "url": SITE + "/", "logo": f"{SITE}{BASE_PATH}assets/competishun-logo-color.png"},
         "mainEntity": {"@type": "ItemList", "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "name": it["headline"], "url": f"{canonical}#{it['id']}"} for i, it in enumerate(mine[:20])]}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Exam News", "item": SITE + BASE_PATH},
            {"@type": "ListItem", "position": 3, "name": p["short"] + " 2027", "item": canonical}]},
        faq_ld(qs)]}

    news_html = "".join(news_item(it, pages, rel, show_exam=False) for it in mine) or \
        f'<div class="empty">No new official update for {escape(p["short"])} 2027 yet. We check every hour. Last checked: {nice(verified)}.</div>'
    others = [o for o in pages.values() if o["group"] == p["group"] and o["slug"] != slug][:8]
    if len(others) < 6:
        others += [pages[s] for s in TABS if s != slug and pages[s] not in others][:6 - len(others)]
    count = ""
    if nd:
        days = (nd[0] - TODAY).days
        count = f'''<div class="count"><div class="k">{escape(nd[1].upper())} IN</div><div class="n">{days} days</div><div class="d">{nice(nd[0])}</div>
<a class="btn btn-orange" href="{escape(r["official_url"])}" rel="noopener" target="_blank">Open official website</a></div>'''
    tag_dt = "Official dates" if r["date_type"] == "Official" else ("Some dates official" if r["date_type"] == "Partly Official" else "Expected dates")
    notes = f'<p class="muted" style="margin:12px 0 0">{escape(txt(r["notes"]))}</p>' if r.get("notes") else ""

    html = head(p["title"], p["description"], canonical, rel, ld, p["keywords"]) + header(rel, pages, slug) + f'''
<section class="hero"><div class="wrap">
  <div class="hero-text">
    <nav class="crumbs" aria-label="Breadcrumb"><a href="{SITE}/">Home</a><span>›</span><a href="{rel}">Exam News</a><span>›</span><span style="color:#fff">{escape(p["short"])} 2027</span></nav>
    <h1>{escape(p["h1"])}</h1>
    <p>{escape(p["intro"])}</p>
    <div class="pills"><span class="pill {"pill-open" if skind == "open" else "pill-wait"}">{escape(stext)}</span>
      <span class="pill">Last updated: {nice(modified)}</span><span class="pill">Conducted by {escape(r["conducting_body"])}</span></div>
  </div>
  <div class="hero-img">{thumb(p["image"], p["short"] + " 2027", 230)}</div>
</div></section>
<div class="wrap"><div class="facts">
  <div class="fact"><b>REGISTRATION</b><span>{escape(txt(r["registration"]))}</span></div>
  <div class="fact"><b>LAST DATE</b><span>{escape(txt(r["last_date"]))}</span></div>
  <div class="fact"><b>EXAM DATES</b><span>{escape(txt(r["exam_dates"]))}</span></div>
  <div class="fact"><b>MODE</b><span>{escape(r["mode"])}</span></div>
</div></div>
<div class="wrap cols">
  <main class="main">
    <section aria-labelledby="latest"><div class="sec-head"><h2 id="latest">{escape(p["short"])} 2027 latest updates</h2><span class="muted">Newest first · Updated every hour</span></div>
      <div class="news">{news_html}</div></section>
    <section class="card" aria-labelledby="dates"><h2 id="dates">{escape(p["short"])} 2027 important dates</h2>
      <div class="tbl"><table><tbody>
        <tr><td>Registration</td><td>{escape(txt(r["registration"]))}</td></tr>
        <tr><td>Last date</td><td>{escape(txt(r["last_date"]))}</td></tr>
        <tr><td>Exam dates</td><td>{escape(txt(r["exam_dates"]))}</td></tr>
        <tr><td>Mode</td><td>{escape(r["mode"])}</td></tr>
        <tr><td>Date status</td><td>{tag_dt}</td></tr>
      </tbody></table></div>{notes}
      <p class="muted" style="margin:10px 0 0">Source: <a href="{escape(r["official_url"])}" rel="noopener" target="_blank">{escape(r["official_url"])}</a> · Checked {nice(verified)}</p></section>
    <section class="card faq" style="margin:0" aria-labelledby="faq"><h2 id="faq">{escape(p["short"])} 2027: frequently asked questions</h2>{faq_html(qs)}</section>
  </main>
  <aside class="side">
    {count}
    <div class="card"><h2>Quick links</h2><div class="links">
      <a href="{escape(r["official_url"])}" rel="noopener" target="_blank">Official {escape(p["short"])} website</a>
      {f'<a href="{escape(r["more_info_url"])}">{escape(p["short"])} 2027 complete guide</a>' if r.get("more_info_url") else ""}
      <a href="{CALENDAR_URL}">Exam Calendar 2026-27</a><a href="{rel}">All exam news</a></div></div>
    <div class="card"><h2>Other exam news</h2><div class="chips">{"".join(f'<a href="{rel}{o["slug"]}/">{escape(o["short"])}</a>' for o in others)}</div>
      <p style="margin:12px 0 0"><a href="{rel}#all-exams" style="font-weight:600;font-size:14px">See all 25 exams →</a></p></div>
    {cta()}
  </aside>
</div>
<div class="wrap">{directory_html(pages, rel)}</div>
''' + footer(rel, pages)
    return html


def build_common(pages, items):
    rel = ""
    canonical = SITE + BASE_PATH
    cutoff = TODAY - timedelta(days=NEWS_DAYS_COMMON)
    recent = [it for it in items if pdate(it["date"]) >= cutoff][:MAX_NEWS_COMMON]
    lead = next((it for it in recent if it.get("top")), recent[0] if recent else None)
    side = [it for it in recent if it is not lead][:3]
    rest = [it for it in recent if it is not lead]

    # deadlines across all exams
    dls = []
    for p in pages.values():
        nd = next_deadline(p["row"])
        if nd:
            dls.append((nd[0], p, nd[1]))
    dls.sort(key=lambda x: x[0])
    dl_html = "".join(f'''<a class="dl" href="{p["slug"]}/"><div class="days"><b>{(d - TODAY).days}</b><small>DAYS</small></div>
<div><span class="w">{escape(p["short"])} {escape(what)}</span><span class="d">{nice(d)}</span></div></a>''' for d, p, what in dls[:4])


    qs = [
        ("How often is this page updated?", "Every hour. New notices from NTA and other exam bodies appear here soon after they are released."),
        ("What do Official and Expected mean?", "Official means the exam body has announced it. Expected means it is based on past years or news reports. News report means a trusted news site has reported it."),
        ("Which exams are covered?", "25 engineering and medical entrance exams including JEE Main, JEE Advanced, NEET UG, BITSAT, VITEEE, SRMJEEE, MHT CET, WBJEE, COMEDK and more."),
        ("Are there ads on this page?", "No. This page has only verified exam news and useful links for students."),
    ]
    modified = pdate(items[0]["date"]) if items else TODAY
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": "NEET and JEE 2027 Latest Exam News", "url": canonical, "dateModified": max(modified, TODAY).isoformat(),
         "description": "NEET latest news, JEE latest news and exam dates for JEE Main, JEE Advanced, BITSAT and 21 more entrance exams. Updated every hour.", "inLanguage": "en-IN",
         "publisher": {"@type": "EducationalOrganization", "name": "Competishun", "url": SITE + "/"},
         "hasPart": [{"@type": "WebPage", "name": p["h1"], "url": f"{canonical}{p['slug']}/"} for p in sorted(pages.values(), key=lambda x: x["order"])]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Exam News", "item": canonical}]},
        faq_ld(qs)]}

    lead_html = ""
    if lead:
        lp = pages[lead["exam"]]
        lead_html = f'''<section class="lead" aria-label="Top stories">
  <article class="lead-main">{thumb(lead["image"], lp["short"] + " 2027")}
    <div class="body"><div class="meta"><span class="kicker">TOP STORY</span>{st_badge(lead["status"])}</div>
      <h2><a href="{lp["slug"]}/#{lead["id"]}" style="color:inherit;text-decoration:none">{escape(lead["headline"])}</a></h2>
      <p>{escape(lead["summary"])}</p>
      <p class="src" style="margin-top:12px">Competishun Exam Desk · {nice(pdate(lead["date"]))} · Source: <a href="{escape(lead["source_url"])}" rel="noopener" target="_blank">{escape(lead["source"])}</a></p></div></article>
  <div class="lead-side"><div class="rule-title">Top stories</div>
  {"".join(f'<a class="mini" href="{pages[s["exam"]]["slug"]}/#{s["id"]}">{thumb(s["image"], pages[s["exam"]]["short"])}<div class="body"><span class="kicker">{escape(pages[s["exam"]]["short"].upper())} 2027</span><strong>{escape(s["headline"])}</strong><span class="muted">{nice(pdate(s["date"]))} · {escape(s["source"])}</span></div></a>' for s in side)}
  </div></section>'''

    filters = '<a class="on" href="./">All</a>' + "".join(f'<a href="{s}/">{escape(pages[s]["short"])}</a>' for s in TABS)
    brk = f'<div class="breaking"><div class="wrap"><span class="badge-breaking">LATEST</span><a href="{pages[lead["exam"]]["slug"]}/#{lead["id"]}" style="color:var(--ink);font-weight:600;text-decoration:none">{escape(lead["headline"])}</a></div></div>' if lead else ""

    html = head("NEET & JEE Latest News 2027: Exam Dates & Updates | Competishun",
                "NEET latest news and JEE latest news 2027: exam dates, registration, last dates, admit cards and results for 25 entrance exams. Updated every hour.",
                canonical, rel, ld, ["neet latest news", "jee latest news", "jee main 2027 exam dates", "neet 2027 exam date", "jee advanced 2027 exam date"]) + header(rel, pages, "all") + brk + f'''
<div class="wrap">
  <h1 style="margin:28px 0 0;font-size:38px;color:var(--blue);line-height:1.15">NEET &amp; JEE 2027 Latest Exam News</h1>
  <p style="margin:8px 0 0;font-size:17px;color:var(--muted);max-width:760px">Registration, last dates, exam dates, admit cards and results for 25 engineering and medical entrance exams. Checked every hour from official websites.</p>
  {lead_html}
  <section class="deadlines" aria-labelledby="dl"><div class="sec-head" style="margin:0"><h2 id="dl">Deadlines to watch</h2><a href="{CALENDAR_URL}" style="color:#FF8A3D;font-weight:600;text-decoration:none;font-size:14px">Full exam calendar →</a></div>
    <div class="dl-grid">{dl_html}</div></section>
  <div class="cols" style="padding-left:0;padding-right:0">
    <main class="main"><section aria-labelledby="latest"><div class="sec-head"><h2 id="latest">Latest updates</h2><span class="muted">Newest first · Auto-updated every hour</span></div>
      <nav class="filters" aria-label="News by exam">{filters}</nav>
      <div class="news">{"".join(news_item(it, pages, rel) for it in rest)}</div></section></main>
    <aside class="side">{cta()}
      <div class="card"><h2>How we update this page</h2><p style="margin:0;font-size:14px;line-height:1.6;color:#3A4456">We check official exam websites every hour. A date is marked Official only when it is on the official site or confirmed by two trusted news sources.</p></div>
    </aside>
  </div>
  {directory_html(pages, rel)}
  <section class="card faq" aria-labelledby="faq"><h2 id="faq">Frequently asked questions</h2>{faq_html(qs)}</section>
</div>
''' + footer(rel, pages)
    return html


def main():
    pages, items, _ = load()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    shutil.copy(os.path.join(NEWS_DIR, "style.css"), os.path.join(OUT, "assets", "style.css"))
    for f in os.listdir(os.path.join(NEWS_DIR, "assets")):
        shutil.copy(os.path.join(NEWS_DIR, "assets", f), os.path.join(OUT, "assets", f))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_common(pages, items))
    urls = [(SITE + BASE_PATH, TODAY)]
    for p in pages.values():
        d = os.path.join(OUT, p["slug"])
        os.makedirs(d)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_exam(p, pages, items))
        mine = [pdate(it["date"]) for it in items if it["exam"] == p["slug"]]
        urls.append((f"{SITE}{BASE_PATH}{p['slug']}/", max(mine + [pdate(p["row"]["verified_on"]) or TODAY])))
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "".join(f"  <url><loc>{u}</loc><lastmod>{d.isoformat()}</lastmod><changefreq>hourly</changefreq></url>\n" for u, d in urls)
    sm += "</urlset>\n"
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sm)
    print(f"OK: built 1 common page + {len(pages)} exam pages + sitemap ({len(items)} news items) at {NOW:%Y-%m-%d %H:%M} IST")


if __name__ == "__main__":
    main()
