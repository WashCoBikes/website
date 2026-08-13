#!/usr/bin/env python3
"""Scrape WashCo Bikes live-site content into Markdown + local images.

Faithful, verbatim extraction for the site-rework prototype. Re-runnable:
fetches the live sitemap, caches raw HTML, extracts the page-body container,
and downloads images so nothing is hotlinked.

What it does NOT do: it does not perform the editorial merge (concatenating
source pages under section headings), and it does not hand-curate staff,
positions, or events into structured collections. Those are authored in a
separate, inspected step (generate-content.py). This script's job is
provenance + faithful text + local images.

Usage (from repo root):

    PYTHONPATH=/tmp/scrape-libs mise exec -- python scripts/scrape.py

Dependencies (installed to an isolated dir, NOT the repo — see plan §4.2):

    pip install --target /tmp/scrape-libs requests beautifulsoup4 markdownify

Outputs:
    .cache/scrape/html/*.html       raw HTML, one file per fetched URL (cached)
    .cache/scrape/content/*.md      Markdown body per canonical source page
    .cache/scrape/meta.json         title/description/hero per source page
    .cache/scrape/events.json       event entries from .ev pages
    .cache/scrape/images.json       source-image-path -> local filename map
    src/assets/images/              downloaded images
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

BASE = "https://washcobikes.org"
ROOT = Path(__file__).resolve().parents[1]
CACHE_HTML = ROOT / ".cache" / "scrape" / "html"
CACHE_CONTENT = ROOT / ".cache" / "scrape" / "content"
CACHE_META = ROOT / ".cache" / "scrape" / "meta.json"
CACHE_EVENTS = ROOT / ".cache" / "scrape" / "events.json"
CACHE_IMAGES = ROOT / ".cache" / "scrape" / "images.json"
IMAGES_DIR = ROOT / "src" / "assets" / "images"

DELAY = 0.5  # seconds between requests; only ~70 pages

# Canonical source pages whose body content is migrated, mapped to the new
# route slug. The /index/* URLs in the live sitemap are homepage aliases, so
# "Who We Are" and "Our Affiliates" are fetched from their real /home/* paths.
# A non-None "section" value means the source page is folded into the parent
# route under that anchor id.
SOURCE_PAGES = [
    # (source path, dest slug, section anchor or None)
    ("home/who_we_are", "about", None),
    ("home/our_affiliates", "about/affiliates", None),
    ("support_us/more_ways_to_support/about_us", "about", None),
    ("retail_amp_repair_shop", "shop", None),
    ("retail_amp_repair_shop/service_and_repair_rates", "shop/rates", None),
    ("retail_amp_repair_shop/meet_our_mechanics", "shop/mechanics", None),
    ("retail_amp_repair_shop/tienda_y_taller_de_reparaciones", "shop/es", None),
    ("programs", "programs", None),
    ("programs/adopt-a-bike", "programs/adopt-a-bike", None),
    ("programs/education", "programs/education", None),
    ("programs/education/bike_repair_clinics", "programs/education", "repair-clinics"),
    ("programs/education/smart_cycling", "programs/education", "smart-cycling"),
    ("programs/education/skills_and_safety_rodeos", "programs/education", "rodeos"),
    ("programs/education/learn_to_ride", "programs/education", "learn-to-ride"),
    ("programs/saddle_up_bike_camp", "programs/saddle-up-bike-camp", None),
    ("programs/saddle_up_bike_camp/camps_faq", "programs/saddle-up-bike-camp", "faq"),
    ("programs/saddle_up_bike_camp/meet_our_instructors", "programs/saddle-up-bike-camp", "instructors"),
    ("programs/saddle_up_bike_camp/photo_gallery", "programs/saddle-up-bike-camp", "gallery"),
    ("jobs_volunteer", "get-involved", None),
    ("jobs_volunteer/volunteer_events", "get-involved/volunteer-events", None),
    ("jobs_volunteer/open_positions", "get-involved/open-positions", None),
    ("support_us", "get-involved", None),
    ("support_us/join_or_donate", "get-involved/join-or-donate", None),
    ("support_us/in_memoriam", "get-involved/join-or-donate", "in-memoriam"),
    ("support_us/big_wheelies", "get-involved/big-wheelies", None),
    ("support_us/more_ways_to_support", "get-involved/more-ways-to-support", None),
    ("support_us/more_ways_to_support/our_stories", "get-involved/more-ways-to-support", "our-stories"),
    ("support_us/more_ways_to_support/contact", "contact", None),
    ("ride_resources", "resources", None),
    ("partners", "resources/partners", None),
    ("contact_us", "contact", None),
]

# Brand assets referenced from the chrome (header/footer/social), downloaded
# once so the new header/footer is self-contained.
BRAND_ASSETS = [
    "/site/1562Wash/WashCo_Logo.png",
    "/site/1562Wash/Reborn_bikes.png",
    "/site/social/facebook_icon.png",
    "/site/social/X_icon.png",
]


def safe_slug(path: str) -> str:
    """Filesystem-safe name for a URL path."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/") or "home")


def download(url: str, dest: Path) -> bool:
    resp = requests.get(url, timeout=30, headers={"User-Agent": "washco-prototype-scraper/1.0"})
    if resp.status_code != 200:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return True


def fetch_page(path: str) -> BeautifulSoup | None:
    """Fetch a content page, using (and refreshing) the HTML cache."""
    cache_file = CACHE_HTML / f"{safe_slug(path)}.html"
    if not cache_file.exists():
        url = f"{BASE}/{path.lstrip('/')}"
        if not download(url, cache_file):
            print(f"  ! fetch failed: {url}", file=sys.stderr)
            return None
        time.sleep(DELAY)
    return BeautifulSoup(cache_file.read_text(encoding="utf-8", errors="replace"), "html.parser")


def local_image_name(src: str) -> str:
    """Deterministic local filename derived from the source image path."""
    src = src.split("?")[0]
    rel = src.strip("/")
    if rel.startswith("site/1562Wash/"):
        rel = rel[len("site/1562Wash/"):]
    # Drop the size-prefix directory (600w/, 250w/, 400w/, Top_Photo/) but keep
    # the stem so the same source image maps to one local file regardless of
    # which size variant the page referenced.
    rel = re.sub(r"^(600w|400w|250w|Top_Photo)/", "", rel)
    rel = rel.replace("/", "-")
    rel = re.sub(r"-+", "-", rel)
    return rel or "image"


def clean_content(soup: BeautifulSoup) -> BeautifulSoup | None:
    """Extract #content inner HTML, unwrapping presentational markup."""
    content = soup.select_one("#content")
    if content is None:
        return None
    clone = BeautifulSoup(str(content), "html.parser")
    for sel in (".clear_all", "script", "style"):
        for el in clone.select(sel):
            el.decompose()
    # Unwrap inline presentation spans/fonts, keeping their text.
    for el in clone.find_all(["span", "font"]):
        el.unwrap()
    # Drop empty paragraphs (including &nbsp;-only ones), but keep paragraphs
    # that contain an image (staff photos, galleries) or a link.
    for p in clone.find_all("p"):
        if not p.get_text(strip=True) and not p.find("img") and not p.find("a"):
            p.decompose()
    return clone


def extract_images(soup: BeautifulSoup, image_map: dict, broken: list) -> None:
    """Download images in this soup and rewrite src to a local marker path.
    Images that 404 at the source are dropped (broken on the live site) and
    recorded in `broken` rather than left as a dangling reference."""
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        if not src or src.startswith("data:"):
            continue
        absolute = urllib.parse.urljoin(BASE + "/", src)
        name = local_image_name(src)
        if not (IMAGES_DIR / name).exists():
            if not download(absolute, IMAGES_DIR / name):
                broken.append(src)
                img.decompose()
                continue
            time.sleep(0.1)
        image_map[src] = name
        img["src"] = f"/assets/images/{name}"
        for attr in ("width", "height", "border", "style"):
            img.attrs.pop(attr, None)


def page_meta(soup: BeautifulSoup) -> dict:
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    desc = ""
    d = soup.select_one('meta[name="description"]')
    if d and d.get("content"):
        desc = d["content"].strip()
    hero = None
    main_photo = soup.select_one("#main_photo img")
    if main_photo and main_photo.get("src"):
        hero = main_photo["src"]
    return {"title": title, "description": desc, "hero": hero}


def sitemap() -> list[str]:
    cache = CACHE_HTML / "sitemap.xml"
    if not cache.exists():
        download(f"{BASE}/sitemap.xml", cache)
    root = ET.fromstring(cache.read_text(encoding="utf-8"))
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]


def main() -> None:
    for d in (CACHE_HTML, CACHE_CONTENT, IMAGES_DIR):
        d.mkdir(parents=True, exist_ok=True)

    image_map: dict[str, str] = {}
    meta: dict[str, dict] = {}
    broken: list[str] = []

    print(f"Fetching {len(SOURCE_PAGES)} content pages...")
    for source, dest, section in SOURCE_PAGES:
        soup = fetch_page(source)
        if soup is None:
            continue
        body = clean_content(soup)
        key = f"{source}|{section or ''}"
        info = page_meta(soup)
        info["dest"] = dest
        info["section"] = section
        info["sourceUrl"] = f"{BASE}/{source}"
        meta[key] = info

        if body is not None:
            extract_images(body, image_map, broken)
            markdown = md(str(body), heading_style="ATX")
            markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
            header = f"<!-- source: {BASE}/{source} -->\n<!-- dest: {dest}"
            if section:
                header += f"  section: {section}"
            header += " -->\n\n# " + info["title"] + "\n\n"
            out = CACHE_CONTENT / f"{safe_slug(source)}.md"
            out.write_text(header + markdown + "\n", encoding="utf-8")

        hero = info.get("hero")
        if hero and hero not in image_map:
            name = local_image_name(hero)
            if not (IMAGES_DIR / name).exists() and not download(
                urllib.parse.urljoin(BASE + "/", hero), IMAGES_DIR / name
            ):
                broken.append(hero)
                continue
            image_map[hero] = name

        print(f"  + {source} -> {dest}" + (f"#{section}" if section else ""))

    print(f"Downloading {len(BRAND_ASSETS)} brand assets...")
    for src in BRAND_ASSETS:
        name = local_image_name(src)
        if not (IMAGES_DIR / name).exists() and not download(
            urllib.parse.urljoin(BASE + "/", src), IMAGES_DIR / name
        ):
            broken.append(src)
            continue
        image_map[src] = name
        print(f"  + {src} -> {name}")

    # Events: fetch every .ev page in the sitemap except the malformed one.
    print("Fetching events...")
    events = []
    for url in sitemap():
        if not url.endswith(".ev"):
            continue
        if "0000/00/00" in url:
            continue  # malformed date, skip per plan §3.3
        path = urllib.parse.urlparse(url).path.lstrip("/")
        soup = fetch_page(path)
        if soup is None:
            continue
        body = clean_content(soup)
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        date_match = re.search(r"(\w+ \d{1,2}(?:st|nd|rd|th)? \d{4})", title)
        events.append(
            {
                "sourceUrl": url,
                "title": title,
                "date": date_match.group(1) if date_match else "",
                "body": md(str(body), heading_style="ATX").strip() if body else "",
            }
        )
        print(f"  + event: {path}")

    CACHE_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    CACHE_EVENTS.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
    CACHE_IMAGES.write_text(
        json.dumps({"images": image_map, "broken": sorted(set(broken))}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"\nDone. {len(meta)} pages, {len(events)} events, {len(image_map)} images, "
        f"{len(set(broken))} broken references dropped."
    )


if __name__ == "__main__":
    main()
