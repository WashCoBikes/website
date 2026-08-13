#!/usr/bin/env python3
"""One-shot backfill of alt text on migrated images.

The live-site extraction did not carry `alt` across, leaving 66 of 95 images
without it. Each image was viewed before its alt text was written; button text is
transcribed verbatim so it matches what sighted users see, and people are named
from the surrounding headings rather than guessed from the picture.

Idempotent: only fills images whose alt is currently empty. Kept in the repo as
provenance for where the text came from, not because it needs re-running.

Usage (from repo root):

    python scripts/apply-alt-text.py [--check]

--check exits non-zero if any content image still has empty alt, without
writing. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "src" / "content"

# (path relative to src/content, line number, image basename) -> alt text.
# Line numbers are from the migrated content at the time of writing; the script
# matches on basename within the file and falls back to filling any empty alt
# for that basename, so small line drifts are tolerated.
ALT: dict[tuple[str, str], str] = {
    # --- pages/about.md : board and staff portraits -------------------------
    ("pages/about.md", "Headshot1-NB-1x1_200.jpg"): "Nick Baker",
    ("pages/about.md", "WIN_20220707_23_30_52_Pro.jpg"): "John Haide",
    ("pages/about.md", "EMILY_SHRIVER.jpg"): "Emily Shriver",
    ("pages/about.md", "TerryWilson.jpg"): "Terry Wilson",
    ("pages/about.md", "Picture2.jpg"): "Wilbert (Wil) Warren",
    ("pages/about.md", "2014-BoardMembershighres-SBoughton.jpg"): "Steve Boughton",
    ("pages/about.md", "es9SM.jpg"): "Emily Shriver",
    ("pages/about.md", "Joe_Kurmaskie.jpg"): "Joe Kurmaskie, Executive Director",
    ("pages/about.md", "apply_now_button.png"): "Apply now to join the Board of Directors",
    # --- pages/about/affiliates.md : partner logos --------------------------
    ("pages/about/affiliates.md", "Reborn_bikes_Logo_50_.jpg"): "Reborn Bikes logo",
    ("pages/about/affiliates.md", "FB4K_LOGO.jpg"): "Free Bikes 4 Kidz Portland logo",
    ("pages/about/affiliates.md", "logo_wta.png"): "Westside Transportation Alliance logo",
    ("pages/about/affiliates.md", "Pear_logo.jpg"): "P:ear Bike Works logo",
    ("pages/about/affiliates.md", "ReDeploy_logo.jpg"): "ReDeploy logo",
    # --- pages/get-involved.md ---------------------------------------------
    ("pages/get-involved.md", "Joe_Kurmaskie.jpg"): "Joe Kurmaskie, Executive Director",
    (
        "pages/get-involved.md",
        "pngkey_com-sign-up-button-png-3341582.jpg",
    ): "Sign up for a volunteer opportunity",
    # --- pages/get-involved/volunteer-events.md -----------------------------
    (
        "pages/get-involved/volunteer-events.md",
        "pngkey_com-sign-up-button-png-3341582.jpg",
    ): "Sign up for a volunteer opportunity",
    # --- pages/get-involved/join-or-donate.md : in memoriam -----------------
    ("pages/get-involved/join-or-donate.md", "rita_jaeger.jpg"): "Rita Jaeger",
    ("pages/get-involved/join-or-donate.md", "Scott_Kuzma.jpeg"): "Scott Kuzma",
    ("pages/get-involved/join-or-donate.md", "Thumbs-D05_0335_(2).jpg"): "Carl Nelson",
    (
        "pages/get-involved/join-or-donate.md",
        "JEN_KURMASKIE.jpg",
    ): "Dr. Jennifer Kurmaskie-Konopka",
    ("pages/get-involved/join-or-donate.md", "RETREAT_031_(2).JPG"): "Mark Norberg",
    # --- pages/get-involved/more-ways-to-support.md -------------------------
    (
        "pages/get-involved/more-ways-to-support.md",
        "admujeres_1.jpg",
    ): "Participants from Adelante Mujeres holding their course completion certificates",
    (
        "pages/get-involved/more-ways-to-support.md",
        "admujeres_3.jpg",
    ): "An instructor showing a group how to inspect a bicycle tire",
    (
        "pages/get-involved/more-ways-to-support.md",
        "admujeres_5.jpg",
    ): "A volunteer demonstrating how to pump up a bicycle tire during a class",
    # --- pages/programs/adopt-a-bike.md : donate buttons --------------------
    ("pages/programs/adopt-a-bike.md", "Donate_button.png"): "Donate now",
    (
        "pages/programs/adopt-a-bike.md",
        "Corporate_Donate_Button.png",
    ): "Corporate donations",
    ("pages/programs/adopt-a-bike.md", "Volunteer_Button.png"): "Volunteer",
    # --- pages/programs/education.md ---------------------------------------
    (
        "pages/programs/education.md",
        "bike_clinic_stock_photo.jpg",
    ): "A mechanic in gloves fitting a tyre onto a bicycle wheel",
    (
        "pages/programs/education.md",
        "20160522_145512.jpg",
    ): "An instructor leading a Smart Cycling class through riding drills on a covered court",
    (
        "pages/programs/education.md",
        "20160522_135424.jpg",
    ): "An instructor demonstrating bike handling to Smart Cycling students",
    (
        "pages/programs/education.md",
        "admujeres_5.jpg",
    ): "A volunteer demonstrating how to pump up a bicycle tire during a class",
    (
        "pages/programs/education.md",
        "IMAG0527.jpg",
    ): "Children and parents with bicycles at a learn-to-ride session outside a school",
    ("pages/programs/education.md", "images__2_.jpg"): "Click here to register",
    # --- pages/programs/saddle-up-bike-camp.md ------------------------------
    (
        "pages/programs/saddle-up-bike-camp.md",
        "Register2026.png",
    ): "Register for 2026 summer bike camps",
    ("pages/programs/saddle-up-bike-camp.md", "images__2_.jpg"): "Click here to register",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "2019_BC_DRILLS.jpg",
    ): "Campers in yellow shirts riding a cone course in a parking lot",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "ENJOING_A_TREAT.jpg",
    ): "Campers sharing ice cream around a table on a camp outing",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "2019_TIGARD_BC.jpg",
    ): "A group of campers in yellow camp shirts posing together outdoors",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "20190627_120530.jpg",
    ): "Campers serving food at a community event",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "20190626_140557.jpg",
    ): "Campers cooling off in a park splash fountain",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "20190628_103813.jpg",
    ): "Campers playing on swings at a neighbourhood park",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "20190627_130045.jpg",
    ): "Campers playing table tennis indoors during a camp outing",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "20190625_140826.jpg",
    ): "Campers and a camp leader taking a break at a cafe",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "20190620_134305.jpg",
    ): "Campers cheering at a bowling alley with helmets stacked on the tables",
    (
        "pages/programs/saddle-up-bike-camp.md",
        "20190618_121245.jpg",
    ): "Campers eating lunch together indoors",
    # --- pages/resources/partners.md : sponsor logos ------------------------
    (
        "pages/resources/partners.md",
        "B604C006-A779-4201-9AB0-141846BBB0B7__1_.jpeg",
    ): "Xpose Hope logo",
    (
        "pages/resources/partners.md",
        "phs-logo-color__3_.jpg",
    ): "Providence Health and Services logo",
    ("pages/resources/partners.md", "unnamed__5_.jpg"): "Rotary International logo",
    ("pages/resources/partners.md", "th-27__1_.jpg"): "Free Bikes 4 Kidz logo",
    # --- positions ----------------------------------------------------------
    (
        "positions/board-of-directors.md",
        "apply_now_button.png",
    ): "Apply now to join the Board of Directors",
}

# Some migrated filenames contain balanced parentheses -- e.g.
# `RETREAT_031_(2).JPG` -- so the destination can't simply stop at the first ')'.
IMG = re.compile(r"(!\[)([^\]]*)(\]\()((?:[^()\s]+|\([^()]*\))+)")


def process(path: Path, check: bool) -> tuple[int, list[str]]:
    rel = path.relative_to(CONTENT).as_posix()
    text = path.read_text(encoding="utf-8")
    filled = 0
    missing: list[str] = []

    def sub(match: re.Match[str]) -> str:
        nonlocal filled
        open_br, alt, mid, src = match.groups()
        if alt.strip():
            return match.group(0)
        name = src.rsplit("/", 1)[-1]
        replacement = ALT.get((rel, name))
        if replacement is None:
            missing.append(f"{rel}: {name}")
            return match.group(0)
        filled += 1
        return f"{open_br}{replacement}{mid}{src}"

    updated = IMG.sub(sub, text)
    if not check and filled:
        path.write_text(updated, encoding="utf-8")
    return filled, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report images still lacking alt text without writing",
    )
    args = parser.parse_args()

    total = 0
    all_missing: list[str] = []
    for path in sorted(CONTENT.rglob("*.md")):
        filled, missing = process(path, args.check)
        total += filled
        all_missing.extend(missing)

    if args.check:
        if all_missing:
            print(f"{len(all_missing)} image(s) with empty alt text:", file=sys.stderr)
            for entry in all_missing:
                print(f"  {entry}", file=sys.stderr)
            return 1
        print("All content images have alt text.")
        return 0

    print(f"Filled alt text on {total} image(s).")
    if all_missing:
        print(f"Still missing ({len(all_missing)}):", file=sys.stderr)
        for entry in all_missing:
            print(f"  {entry}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
