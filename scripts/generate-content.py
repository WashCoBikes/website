#!/usr/bin/env python3
"""Assemble the scraped content into Astro content collections.

Companion to scrape.py. Reads the faithful Markdown + metadata that scrape.py
wrote to .cache/scrape/, applies the editorial merge defined in
docs/implementation-plan.md §5-§6 (concatenate merged source pages under
section headings, assign locale/order, rewrite image paths to be depth-relative
and internal links to the new routes), and writes:

    src/content/pages/*.md
    src/content/staff/*.md
    src/content/positions/*.md
    src/content/events/*.md
    src/data/site.json

Re-runnable and idempotent. Run from the repo root after scrape.py:

    PYTHONPATH=/tmp/scrape-libs mise exec -- python scripts/generate-content.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "scrape" / "content"
META = json.loads((ROOT / ".cache" / "scrape" / "meta.json").read_text(encoding="utf-8"))
EVENTS = json.loads((ROOT / ".cache" / "scrape" / "events.json").read_text(encoding="utf-8"))
PAGES_DIR = ROOT / "src" / "content" / "pages"
STAFF_DIR = ROOT / "src" / "content" / "staff"
POSITIONS_DIR = ROOT / "src" / "content" / "positions"
EVENTS_DIR = ROOT / "src" / "content" / "events"

# Old source path (no leading slash) -> new route. Drives both the content-link
# rewrite and mirrors docs/implementation-plan.md §7.
LINK_MAP = {
    "home/who_we_are": "/about",
    "home/our_affiliates": "/about/affiliates",
    "index/who_we_are": "/about",
    "index/our_affiliates": "/about/affiliates",
    "support_us/more_ways_to_support/about_us": "/about",
    "retail_amp_repair_shop": "/shop",
    "retail_amp_repair_shop/service_and_repair_rates": "/shop/rates",
    "retail_amp_repair_shop/meet_our_mechanics": "/shop/mechanics",
    "retail_amp_repair_shop/tienda_y_taller_de_reparaciones": "/shop/es",
    "programs": "/programs",
    "programs/adopt-a-bike": "/programs/adopt-a-bike",
    "programs/education": "/programs/education",
    "programs/education/bike_repair_clinics": "/programs/education#repair-clinics",
    "programs/education/smart_cycling": "/programs/education#smart-cycling",
    "programs/education/skills_and_safety_rodeos": "/programs/education#rodeos",
    "programs/education/learn_to_ride": "/programs/education#learn-to-ride",
    "programs/saddle_up_bike_camp": "/programs/saddle-up-bike-camp",
    "programs/saddle_up_bike_camp/camps_faq": "/programs/saddle-up-bike-camp#faq",
    "programs/saddle_up_bike_camp/meet_our_instructors": "/programs/saddle-up-bike-camp#instructors",
    "programs/saddle_up_bike_camp/photo_gallery": "/programs/saddle-up-bike-camp#gallery",
    "jobs_volunteer": "/get-involved",
    "jobs_volunteer/volunteer_events": "/get-involved/volunteer-events",
    "jobs_volunteer/open_positions": "/get-involved/open-positions",
    "support_us": "/get-involved",
    "support_us/join_or_donate": "/get-involved/join-or-donate",
    "support_us/in_memoriam": "/get-involved/join-or-donate#in-memoriam",
    "support_us/big_wheelies": "/get-involved/big-wheelies",
    "support_us/more_ways_to_support": "/get-involved/more-ways-to-support",
    "support_us/more_ways_to_support/our_stories": "/get-involved/more-ways-to-support#our-stories",
    "support_us/more_ways_to_support/contact": "/contact",
    "contact_us": "/contact",
    "partners": "/resources/partners",
    "ride_resources": "/resources",
    "washco_bikes_events": "/events",
}


def safe_slug(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/") or "home")


def source_file(source: str) -> Path:
    return CACHE / f"{safe_slug(source)}.md"


def strip_scrape_header(md: str) -> str:
    """Drop scrape.py's provenance comments and the auto-added H1."""
    lines = md.splitlines()
    out = []
    skipped_h1 = False
    for line in lines:
        if line.startswith("<!--"):
            continue
        if not skipped_h1 and line.startswith("# ") and not line.startswith("## "):
            skipped_h1 = True
            continue
        out.append(line)
    # Drop the leading blank line left by the stripped H1 block.
    while out and out[0].strip() == "":
        out.pop(0)
    return "\n".join(out).strip() + "\n"


def img_prefix(slug: str) -> str:
    """Relative path from src/content/pages/<slug>.md to src/assets/images/."""
    depth = slug.count("/")
    return "../" * (depth + 2) + "assets/images/"


def rewrite_images(md: str, slug: str) -> str:
    return md.replace("/assets/images/", img_prefix(slug))


def rewrite_links(md: str) -> str:
    """Rewrite internal links (absolute, root-relative, or bare) to new routes."""

    def repl(m: re.Match) -> str:
        url = m.group(1)
        # Strip an absolute washcobikes.org prefix to get the bare path.
        path = re.sub(r"^https?://washcobikes\.org/?", "", url).strip("/")
        if path in LINK_MAP:
            return "](" + LINK_MAP[path] + ")"
        # Preserve anything unknown (external links, mailto, PDFs, anchors).
        return m.group(0)

    return re.sub(r"\]\(([^)]+)\)", repl, md)


def hero_for(slug: str, source_keys: list[str]) -> str | None:
    """First non-null hero image filename among the page's sources."""
    for key in source_keys:
        info = META.get(key)
        if info and info.get("hero"):
            return re.sub(r"^(600w|400w|250w|Top_Photo)/", "", info["hero"].strip("/").split("site/1562Wash/")[-1]).replace("/", "-")
    return None


def quote(v: str) -> str:
    return json.dumps(v, ensure_ascii=False)


def write_page(slug: str, title: str, body: str, *, locale: str = "en",
               order: int | None = None, source_url: str | None = None,
               sections: list | None = None) -> None:
    fm = [f"title: {quote(title)}", f"slug: {quote(slug)}", f"locale: {locale}"]
    if order is not None:
        fm.append(f"order: {order}")
    if source_url:
        fm.append(f"sourceUrl: {quote(source_url)}")
    if sections:
        fm.append("sections:")
        for s in sections:
            fm.append(f"  - id: {s['id']}")
            fm.append(f"    label: {quote(s['label'])}")
            if s.get("staffGroup"):
                fm.append(f"    staffGroup: {s['staffGroup']}")
    fm.append("draft: false")
    doc = "---\n" + "\n".join(fm) + "\n---\n\n" + body
    (PAGES_DIR / f"{slug}.md").parent.mkdir(parents=True, exist_ok=True)
    (PAGES_DIR / f"{slug}.md").write_text(doc, encoding="utf-8")


def assemble(sources: list, slug: str) -> str:
    """Concatenate source bodies. Tuple forms:
    ("page-source", anchor|None)  — migrated content, optional H2 anchor
    ("staff", group, anchor_id)   — placeholder for a staff-card section."""
    parts = []
    for item in sources:
        if item[0] == "staff":
            _, group, _anchor_id = item
            parts.append(f'<div data-staff-slot="{group}"></div>')
            continue
        source, anchor = item
        body = strip_scrape_header(source_file(source).read_text(encoding="utf-8"))
        if anchor:
            label = META.get(f"{source}|{anchor}", {}).get("title", anchor.replace("-", " ").title())
            body = re.sub(rf"^##\s+{re.escape(label)}\s*\n+", "", body, flags=re.IGNORECASE)
            body = f'<h2 id="{anchor}">{label}</h2>\n\n{body}'
        parts.append(body)
    return "\n".join(parts).strip() + "\n"


def main() -> None:
    for d in (PAGES_DIR, STAFF_DIR, POSITIONS_DIR, EVENTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # ---- Pages -----------------------------------------------------------
    pages = [
        # (slug, title, sources [(source, anchor)], locale, order, sections)
        ("about", "Who We Are", [
            ("home/who_we_are", None),
            ("support_us/more_ways_to_support/about_us", None),
        ], "en", 10, None),
        ("about/affiliates", "Our Affiliates", [("home/our_affiliates", None)], "en", 11, None),
        ("shop", "Community Bicycle Center", [("retail_amp_repair_shop", None)], "en", 20, None),
        ("programs/saddle-up-bike-camp", "Saddle Up Bike Camp", [
            ("programs/saddle_up_bike_camp", None),
            ("programs/saddle_up_bike_camp/camps_faq", "faq"),
            ("staff", "instructor", "instructors"),
            ("programs/saddle_up_bike_camp/photo_gallery", "gallery"),
        ], "en", 31, [
            {"id": "faq", "label": "Camps FAQ"},
            {"id": "instructors", "label": "Meet Our Instructors", "staffGroup": "instructor"},
            {"id": "gallery", "label": "Photo Gallery"},
        ]),
        ("programs/education", "Education", [
            ("programs/education", None),
            ("programs/education/bike_repair_clinics", "repair-clinics"),
            ("programs/education/smart_cycling", "smart-cycling"),
            ("programs/education/skills_and_safety_rodeos", "rodeos"),
            ("programs/education/learn_to_ride", "learn-to-ride"),
        ], "en", 32, [
            {"id": "repair-clinics", "label": "Bike Repair Clinics"},
            {"id": "smart-cycling", "label": "Smart Cycling"},
            {"id": "rodeos", "label": "Skills and Safety Rodeos"},
            {"id": "learn-to-ride", "label": "Learn to Ride"},
        ]),
        ("programs/adopt-a-bike", "Adopt-a-Bike", [("programs/adopt-a-bike", None)], "en", 33, None),
        ("get-involved", "Get Involved", [
            ("jobs_volunteer", None),
            ("support_us", None),
        ], "en", 40, None),
        ("get-involved/volunteer-events", "Volunteer Events", [("jobs_volunteer/volunteer_events", None)], "en", 41, None),
        ("get-involved/join-or-donate", "Join or Donate", [
            ("support_us/join_or_donate", None),
            ("support_us/in_memoriam", "in-memoriam"),
        ], "en", 42, [{"id": "in-memoriam", "label": "In Memoriam"}]),
        ("get-involved/big-wheelies", "Big Wheelies", [("support_us/big_wheelies", None)], "en", 43, None),
        ("get-involved/more-ways-to-support", "More Ways to Support", [
            ("support_us/more_ways_to_support", None),
            ("support_us/more_ways_to_support/our_stories", "our-stories"),
        ], "en", 44, [{"id": "our-stories", "label": "Our Stories"}]),
        ("resources", "Ride Resources", [("ride_resources", None)], "en", 50, None),
        ("resources/partners", "Partners", [("partners", None)], "en", 51, None),
        ("contact", "Contact", [
            ("contact_us", None),
            ("support_us/more_ways_to_support/contact", None),
        ], "en", 60, None),
    ]

    for slug, title, sources, locale, order, sections in pages:
        body = assemble(sources, slug)
        body = rewrite_images(body, slug)
        body = rewrite_links(body)
        primary = sources[0][0]
        source_url = f"https://washcobikes.org/{primary}"
        write_page(slug, title, body, locale=locale, order=order, source_url=source_url, sections=sections)
        print(f"page: {slug}")

    # ---- Staff -----------------------------------------------------------
    staff = [
        ("todd-kelley", "Todd Kelley", "Mechanic", "mechanic", "Todd_Kelley_sm.jpg",
         "Todd has been a bike enthusiast and advocate for many years. When he moved to the area, he discovered the WashCo Bike Shop for all his cycling needs. He also realized his values aligned well with the organization's mission.\n\nTodd says \u201cevery kid should have a bike and find their freedom\u201d. He wants WashCo Bikes to be a place where you feel welcomed even if you're a casual biker. You can walk in and easily find the things you need and interact with the great staff working to keep bikes in tip-top shape."),
        ("mitch-taylor", "Mitch Taylor", "Instructor", "instructor", "mitch_taylor.jpg",
         "Mitch, a resident of Forest Grove, has been a dedicated instructor at our Summer Bike Camps for many years. A passionate cyclist, he enjoys the freedom that retirement brings and spends much of his time exploring new places on two wheels. His bike adventures have taken him across the U.S., including New York and Missouri, as well as through parts of Europe. Most recently, he returned from bike tours in Portugal and Spain\u2014including a memorable climb up a ridiculously steep 3-kilometer hill with a rewarding view of the Mediterranean."),
        ("tana-gutza", "Tana Gutza", "Instructor", "instructor", "Tana_biking_St__Helens.jpg",
         "Tana has been cycling since she was 6. Her favorite bike paths and riding areas are Banks Vernonia Trail, Hagg Lake and the Tillamook State Forest. Her most recent mountain biking adventure took her to Canada where she saw her first bear on the trail. Prior to retirement, Tana worked as an Accountant after graduating from Portland State University with a Bachelor's Degree in Business Administration (Accounting Major). Besides biking, Tana enjoys walks with her husband, spending time with family and friends, cross country skiing and looking after her 4 rowdy cats."),
        ("hannah-hardt", "Hannah Hardt", "Instructor", "instructor", "HannahHardt.jpg",
         "Hannah is a School Support Specialist at a high school in Beaverton and a busy parent to two active kids, ages 12 and 14. She loves animals, reading, playing games, camping, and doing just about anything outdoors\u2014including riding her bike. For Hannah, biking feels like freedom, and she's passionate about sharing that joy with others. She's excited to be part of WashCo Bikes and looks forward to seeing you out on the trail!"),
        ("micah-peterson", "Micah Peterson", "Instructor", "instructor", "Micah_Peterson.jpeg",
         "Micah is a 16-year-old mountain biker who has been riding from a young age and has loved bikes for as long as he can remember. Heading into his junior year of high school, he's entering his third season on his NICA mountain bike team. He brings strong knowledge of bikes and bike safety, along with experience volunteering with children at church events. Micah is excited for the opportunity to help teach and inspire young bikers this season."),
        ("grae-taylor", "Grae Taylor", "Instructor", "instructor", "Grae_Taylor.jpg",
         "Grae\u2014yes, like the color\u2014is a 16-year-old heading into his junior year of high school. He bikes both competitively and for fun, and brings energy and enthusiasm to every ride."),
        ("emily-hackett", "Emily Hackett", "Camps Coordinator", "instructor", "Emily_Hackett.jpg",
         "A lifelong cyclist and dedicated bike commuter, Emily has been involved with WashCo Bikes for over 15 years in various roles, including volunteer, project manager, web support specialist, and board member. Now retired, she is eager to take a more hands-on approach to supporting WashCo Bikes' programs and the communities they serve. When she's not giving back, Emily trades pavement for dirt, letting her road bike collect a little dust as she explores mountain biking trails both locally and across the western U.S."),
    ]
    for i, (slug, name, role, group, photo, bio) in enumerate(staff):
        doc = (
            "---\n"
            f"name: {quote(name)}\n"
            f"role: {quote(role)}\n"
            f"group: {group}\n"
            f"order: {i}\n"
            f"photo: ../../assets/images/{photo}\n"
            f"bio: {quote(bio)}\n"
            "---\n"
        )
        (STAFF_DIR / f"{slug}.md").write_text(doc, encoding="utf-8")
    print(f"staff: {len(staff)}")

    # ---- Positions -------------------------------------------------------
    positions_md = strip_scrape_header(source_file("jobs_volunteer/open_positions").read_text(encoding="utf-8"))
    position_specs = [
        ("Administration Assistant", "administration-assistant", "volunteer"),
        ("Top Shelf Bicycle Education Instructors Needed!", "top-shelf-bicycle-education-instructors", "paid"),
        ("Our Board of Directors-4 Openings", "board-of-directors", "volunteer"),
        ("Part Time Program Manager/Bike Camp Director", "program-manager-bike-camp-director", "paid"),
        ("Bike Camp Instructor", "bike-camp-instructor", "paid"),
    ]
    # Split the positions body on the known position-title headings.
    chunks: list[tuple[str, str]] = []
    headings = [t for t, _, _ in position_specs]
    idx = []
    for h in headings:
        m = re.search(rf"^## {re.escape(h)}\s*$", positions_md, flags=re.MULTILINE)
        idx.append(m.start() if m else None)
    for n, (_, slug, ptype) in enumerate(position_specs):
        start = idx[n]
        end = idx[n + 1] if n + 1 < len(idx) and idx[n + 1] is not None else len(positions_md)
        if start is None:
            continue
        chunk = positions_md[start:end].strip()
        # Remove the leading "## <title>" line.
        chunk = re.sub(rf"^## {re.escape(headings[n])}\s*", "", chunk).strip()
        chunk = rewrite_images(chunk, "positions")
        chunk = rewrite_links(chunk)
        doc = (
            "---\n"
            f"title: {quote(headings[n])}\n"
            f"type: {ptype}\n"
            f"active: true\n"
            "---\n\n"
            f"{chunk}\n"
        )
        (POSITIONS_DIR / f"{slug}.md").write_text(doc, encoding="utf-8")
        print(f"position: {slug}")

    for e in EVENTS:
        m = re.search(r"washco_bikes_events/(\d{4})/(\d{2})/(\d{2})/", e["sourceUrl"])
        start = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
        body = e["body"]
        title = ""
        tm = re.search(r"^## (.+)$", body, flags=re.MULTILINE)
        if tm:
            title = tm.group(1).strip()
        if not title:
            title = e["title"].replace(f" on {e['date']}", "").strip()

        location = ""
        lm = re.search(r"^Location:\s*(.+)$", body, flags=re.MULTILINE)
        if lm:
            location = lm.group(1).strip()

        desc = body
        # Drop the nav footer and the metadata lines from the description.
        desc = re.sub(r"WashCo Bikes Events ::.*$", "", desc, flags=re.DOTALL).strip()
        desc = re.sub(r"^# .+$", "", desc, flags=re.MULTILINE)
        desc = re.sub(rf"^## {re.escape(title)}$", "", desc, flags=re.MULTILINE)
        desc = re.sub(r"^\*\*.*\*\*$", "", desc, flags=re.MULTILINE)
        desc = re.sub(r"^Time:.*$", "", desc, flags=re.MULTILINE)
        desc = re.sub(r"^Location:.*$", "", desc, flags=re.MULTILINE)
        desc = re.sub(r"\n{3,}", "\n\n", desc).strip()

        time_line = ""
        t2 = re.search(r"^Time:\s*(.+)$", body, flags=re.MULTILINE)
        if t2:
            time_line = t2.group(1).strip()
        if time_line:
            desc = f"Time: {time_line}\n\n{desc}".strip()

        slug = re.sub(r"[^a-z0-9-]+", "-", title.lower()).strip("-") or "event"
        if start:
            slug = f"{start}-{slug}"

        doc = (
            "---\n"
            f"title: {quote(title)}\n"
            f"startDate: {start}\n"
            + (f"location: {quote(location)}\n" if location else "")
            + f"sourceUrl: {quote(e['sourceUrl'])}\n"
            + "---\n\n"
            f"{desc}\n"
        )
        (EVENTS_DIR / f"{slug}.md").write_text(doc, encoding="utf-8")
    print(f"events: {len(EVENTS)}")


if __name__ == "__main__":
    main()
