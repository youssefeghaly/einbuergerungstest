#!/usr/bin/env python3
"""Extract the official BAMF question catalog from its PDF into structured JSON.

Source: "Gesamtfragenkatalog zum Test 'Leben in Deutschland' und zum
'Einbürgerungstest'", Bundesamt für Migration und Flüchtlinge.

The PDF contains the questions and their four answer options, but *no*
answer key.  This script therefore only extracts questions, options and
images; correct answers are merged in by tools/build_dataset.py.

Output:
  data/catalog_pdf.json   one record per question, in official document order
  data/images/qNNN.png    cropped image strips for the image-based questions

Usage:  python3 tools/extract_catalog.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    sys.exit("PyMuPDF missing. Install with: pip install pymupdf")

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "raw" / "gesamtfragenkatalog-2025-05-07.pdf"
OUT_JSON = ROOT / "data" / "catalog_pdf.json"
IMAGE_DIR = ROOT / "data" / "images"

# State sections appear in this order in Teil II (alphabetical).
STATE_ORDER = [
    ("Baden-Württemberg", "BW"),
    ("Bayern", "BY"),
    ("Berlin", "BE"),
    ("Brandenburg", "BB"),
    ("Bremen", "HB"),
    ("Hamburg", "HH"),
    ("Hessen", "HE"),
    ("Mecklenburg-Vorpommern", "MV"),
    ("Niedersachsen", "NI"),
    ("Nordrhein-Westfalen", "NW"),
    ("Rheinland-Pfalz", "RP"),
    ("Saarland", "SL"),
    ("Sachsen", "SN"),
    ("Sachsen-Anhalt", "ST"),
    ("Schleswig-Holstein", "SH"),
    ("Thüringen", "TH"),
]
STATE_BY_NAME = {name: code for name, code in STATE_ORDER}

HEADER_RE = re.compile(r"^Aufgabe\s+(\d+)$")
SECTION_RE = re.compile(r"^Fragen für das Bundesland (.+?)\s*$")
FOOTER_RE = re.compile(r"^Seite\s+\d+\s+von\s+\d+$")
CAPTION_RE = re.compile(r"^(?:Bild \d+\s*)+$")
# Most pages mark answer options with a Wingdings2 box glyph, but a handful of
# pages use a plain "□" (U+25A1) in ArialMT, sitting on its own line.
BOX_CHARS = "□"

ZOOM = 2.2  # render scale for cropped image strips (2.2x stays crisp, keeps files small)
JPEG_QUALITY = 88


def norm(text: str) -> str:
    """Normalise whitespace and unify typographic characters for comparison."""
    text = unicodedata.normalize("NFC", text)
    replacements = {
        "\u00a0": " ", "\u2018": "'", "\u2019": "'", "\u201c": '"',
        "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2026": "...",
        "\u00ad": "", "\ufb01": "fi", "\ufb02": "fl",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def page_lines(page):
    """Return visual lines with merged spans, sorted top-to-bottom, left-to-right."""
    raw_spans = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                raw_spans.append(
                    {
                        "text": span["text"],
                        "font": span["font"],
                        "x": span["bbox"][0],
                        "y": span["bbox"][1],
                        "y1": span["bbox"][3],
                        "size": span["size"],
                    }
                )
    raw_spans.sort(key=lambda s: (round(s["y"], 1), s["x"]))

    lines, current = [], []
    for span in raw_spans:
        if current and abs(span["y"] - current[0]["y"]) > 2.5:
            lines.append(current)
            current = []
        current.append(span)
    if current:
        lines.append(current)

    merged = []
    for group in lines:
        group.sort(key=lambda s: s["x"])
        merged.append(
            {
                "text": norm("".join(s["text"] for s in group)),
                "spans": group,
                "is_option": any("Wingdings" in s["font"] for s in group),
                "y": min(s["y"] for s in group),
                "y1": max(s["y1"] for s in group),
                "x": min(s["x"] for s in group),
            }
        )
    return [ln for ln in merged if ln["text"]]


def is_bold(line) -> bool:
    return any("Bold" in s["font"] for s in line["spans"])


def is_option_marker(line) -> bool:
    return line["is_option"] or line["text"].startswith(BOX_CHARS)


def option_marker_text(line) -> str:
    """Option text carried on the marker's own line, if any."""
    parts = [s["text"] for s in line["spans"] if "Wingdings" not in s["font"]]
    return norm("".join(parts).lstrip(BOX_CHARS))


def question_images(page, y_top: float, y_bottom: float):
    """Images whose vertical centre falls inside the question's text band."""
    found = []
    for info in page.get_image_info():
        x0, top, x1, bottom = info["bbox"]
        centre = (top + bottom) / 2
        if y_top <= centre <= y_bottom:
            found.append({"x0": x0, "y0": top, "x1": x1, "y1": bottom})
    found.sort(key=lambda im: im["x0"])
    return found


def extract():
    doc = pymupdf.open(PDF)
    records = []
    current_state = None
    current = None

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_number = page_index + 1
        lines = page_lines(page)

        for line in lines:
            text = line["text"]

            if FOOTER_RE.match(text):
                continue

            section = SECTION_RE.match(text)
            if section and is_bold(line):
                name = section.group(1)
                if name not in STATE_BY_NAME:
                    raise SystemExit(f"unknown state section: {name!r}")
                current_state = STATE_BY_NAME[name]
                continue

            if text in ("Teil I", "Teil II", "Allgemeine Fragen"):
                continue

            header = HEADER_RE.match(text)
            if header and is_bold(line):
                if current:
                    records.append(current)
                number = int(header.group(1))
                current = {
                    "part": "state" if current_state else "general",
                    "state": current_state,
                    "number": number,
                    "question_id": f"{current_state}-{number}" if current_state else str(number),
                    "page": page_number,
                    "stem_lines": [],
                    "options": [],
                    "y_start": line["y"],
                    "y_end": line["y1"],
                    "awaiting_option_text": False,
                }
                continue

            if current is None:
                continue

            current["y_end"] = max(current["y_end"], line["y1"])

            if is_option_marker(line):
                marker_text = option_marker_text(line)
                if marker_text:
                    current["options"].append(marker_text)
                    current["awaiting_option_text"] = False
                else:
                    # marker sits on its own line; the option text follows
                    current["awaiting_option_text"] = True
            elif current["awaiting_option_text"]:
                current["options"].append(text)
                current["awaiting_option_text"] = False
            elif current["options"]:
                # continuation of the previous (wrapped) answer option
                current["options"][-1] = norm(current["options"][-1] + " " + text)
            else:
                current["stem_lines"].append({"text": text, "y": line["y"], "y1": line["y1"]})

    if current:
        records.append(current)

    # Second pass: attach images and crop the strips.
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for record in records:
        page = doc[record["page"] - 1]

        # Text lines belonging to this question (stem + option rows + captions).
        page_lines_all = page_lines(page)
        band = [
            ln
            for ln in page_lines_all
            if record["y_start"] - 1 <= ln["y"] <= record["y_end"] + 1
        ]
        captions = [ln for ln in band if CAPTION_RE.match(ln["text"])]

        images = question_images(page, record["y_start"], record["y_end"])

        # The "Bild N" captions sit above the options and must not pollute the stem.
        if images:
            stem = [
                ln["text"]
                for ln in record["stem_lines"]
                if not CAPTION_RE.match(ln["text"])
            ]
        else:
            stem = [ln["text"] for ln in record["stem_lines"]]

        record["stem"] = norm(" ".join(stem))
        record.pop("stem_lines", None)
        record["image_count"] = len(images)

        if images:
            x0 = min(im["x0"] for im in images) - 6
            x1 = max(im["x1"] for im in images) + 6
            y0 = min(im["y0"] for im in images) - 6
            y1 = max(im["y1"] for im in images) + 6
            if captions:
                y1 = max(y1, max(ln["y1"] for ln in captions) + 4)
            clip = pymupdf.Rect(x0, y0, x1, y1)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=clip)
            name = f"q{record['question_id']}.jpg"
            (IMAGE_DIR / name).write_bytes(
                pixmap.tobytes("jpeg", jpg_quality=JPEG_QUALITY)
            )
            record["image"] = f"data/images/{name}"
        else:
            record["image"] = None
            record["image_count"] = 0

        record.pop("y_start", None)
        record.pop("y_end", None)

    return records


def main():
    records = extract()

    general = [r for r in records if r["part"] == "general"]
    state = [r for r in records if r["part"] == "state"]

    print(f"questions total : {len(records)}")
    print(f"  general       : {len(general)}")
    print(f"  state         : {len(state)}")
    print(f"  with images   : {sum(1 for r in records if r['image'])}")

    problems = []
    if len(general) != 300:
        problems.append(f"expected 300 general questions, found {len(general)}")
    missing = sorted(set(range(1, 301)) - {r["number"] for r in general})
    if missing:
        problems.append(f"general questions missing numbers: {missing}")

    for name, code in STATE_ORDER:
        rows = [r for r in state if r["state"] == code]
        if len(rows) != 10:
            problems.append(f"{name} ({code}): expected 10 questions, found {len(rows)}")
        nums = sorted(r["number"] for r in rows)
        if nums != list(range(1, 11)):
            problems.append(f"{name} ({code}): unexpected numbering {nums}")

    for record in records:
        if len(record["options"]) != 4:
            problems.append(
                f"{record['question_id']}: {len(record['options'])} options instead of 4"
            )
        if not record["stem"]:
            problems.append(f"{record['question_id']}: empty question text")
        for option in record["options"]:
            if not option:
                problems.append(f"{record['question_id']}: empty option text")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT_JSON.relative_to(ROOT)}")

    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for problem in problems[:40]:
            print("  -", problem)
        return 1

    print("structure checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
