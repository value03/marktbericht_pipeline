#!/usr/bin/env python3
"""Render Marktbericht PDFs into website HTML.

    ./create_page.py ./*.pdf        one output/YYYY-MM-DD.html per PDF
    ./create_page.py < report.pdf   a single PDF from stdin
"""
import base64
import io
import math
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader
from pypdf.generic import ContentStream

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path("output")

MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
    "dezember": 12,
}

# intro section title prefix (lowercase) -> template variable
INTRO_SECTIONS = {
    "aus unserem farm": "farm_text",
    "aktuelles auf dem markt": "aktuelles_markt",
    "problematisch oder saisonende": "problematisches",
}

env = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(["html", "xml"])
)

template = env.get_template("website.html")


def clean(text):
    # rejoin words hyphenated at a line break, then flatten line breaks
    text = re.sub(r"(?<=\w)-\n", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_pairs(page):
    # A pair starts with bold text at the beginning of a line (like the
    # <p><strong> paragraphs in the DOCX). Bold words inside a body stay body.
    # Returns the cleaned (title, body) pairs and the y position of each title.
    pairs = []
    title_y = []
    at_line_start = True
    in_title = False

    def visit(text, cm, tm, font, size):
        nonlocal at_line_start, in_title
        bold = "Bold" in (font or {}).get("/BaseFont", "")
        for i, chunk in enumerate(text.split("\n")):
            if i > 0:
                if pairs:
                    pairs[-1][1 if not in_title else 0] += "\n"
                at_line_start = True
            if not chunk:
                continue
            if bold and at_line_start and chunk.strip():
                pairs.append([chunk, ""])
                title_y.append(tm[5])
                in_title = True
            elif in_title and (bold or not chunk.strip()):
                pairs[-1][0] += chunk
            elif pairs:
                in_title = False
                pairs[-1][1] += chunk
            if chunk.strip():
                at_line_start = False

    page.extract_text(visitor_text=visit)
    return [(clean(title), clean(body)) for title, body in pairs], title_y


def split_intro(pairs):
    # The intro sections come before the "Aktuelles vom Markt" heading, and an
    # issue may leave some of them out, so they are matched by title.
    # Returns the intro bodies (empty if missing) and the product items.
    intro = dict.fromkeys(INTRO_SECTIONS.values(), "")
    for i, (title, body) in enumerate(pairs):
        if title.lower() == "aktuelles vom markt":
            return intro, pairs[i + 1:]
        key = next((key for prefix, key in INTRO_SECTIONS.items()
                    if title.lower().startswith(prefix)), None)
        if key is None:
            raise ValueError(f"unknown intro section: {title!r}")
        intro[key] = body
    raise ValueError("heading 'Aktuelles vom Markt' not found")


def split_items(items):
    items_split = [[] for i in range(5)]

    left_items = len(items) - 3 * 2  # 2 text blocks per image

    split_two = math.floor(left_items / 2)
    split_one = split_two + left_items % 2

    split = 0

    items_split[0] = items[0:2]
    split = 2
    items_split[1] = items[2:split + split_one]
    split = split + split_one
    items_split[2] = items[split: split + 2]
    split += 2
    items_split[3] = items[split: split + split_two]
    split += split_two
    items_split[4] = items[split:]
    return items_split


def extract_pictures(reader, page, header_y):
    # Word draws each image right after a "cm" (a b c d x y). y is its position,
    # and a/b hold the rotation: the photos are stored turned 90° left and only
    # rotated upright when drawn, so the pixels have to be turned back here.
    xobjects = page["/Resources"].get("/XObject", {})
    placed = []
    cm = [1, 0, 0, 1, 0, 0]

    for operands, operator in ContentStream(page.get_contents(), reader).operations:
        if operator == b"cm":
            cm = [float(x) for x in operands]
        elif operator == b"Do":
            xobj = xobjects[operands[0]].get_object()
            if xobj.get("/Subtype") == "/Image":
                placed.append((cm, xobj))

    pictures = []
    for cm, xobj in sorted(placed, key=lambda p: -p[0][5]):
        if cm[5] > header_y:
            continue  # logo in the page header
        angle = round(math.degrees(math.atan2(cm[1], cm[0])))
        if angle == 0 and xobj.get("/Filter") == "/DCTDecode":
            data = xobj.get_data()  # already a complete JPEG file
        else:
            buffer = io.BytesIO()
            image = xobj.decode_as_image().rotate(angle, expand=True)
            image.convert("RGB").save(buffer, format="JPEG", quality=95)
            data = buffer.getvalue()
        pictures.append("data:image/jpeg;base64," + base64.b64encode(data).decode())
    return pictures


def iso_date(date):
    # "30. September 2026" -> "2026-09-30"
    match = re.fullmatch(r"(\d{1,2})\.\s*(\S+)\s+(\d{4})", date)
    if not match or match[2].lower() not in MONTHS:
        raise ValueError(f"unrecognised date in header: {date!r}")
    day, month, year = match.groups()
    return f"{year}-{MONTHS[month.lower()]:02d}-{int(day):02d}"


def create_page(pdf):
    """Render one PDF (path or file object); return (iso date, html)."""
    reader = PdfReader(pdf)
    page = reader.pages[0]
    matching_text, title_y = extract_pairs(page)

    # pair 0 is the header "Marktbericht vom 30. September 2026" (body: address)
    date = re.sub(r"^Marktbericht vom\s*", "", matching_text[0][0])
    intro, items = split_intro(matching_text[1:])

    html = template.render(
        full_date=date,
        farm_text=intro["farm_text"],
        aktuelles_markt=intro["aktuelles_markt"],
        problematisches=intro["problematisches"],
        items=split_items(items),
        img=extract_pictures(reader, page, title_y[1])
    )
    return iso_date(date), html


def main():
    if len(sys.argv) > 1:
        sources = [(path, path) for path in sys.argv[1:]]
    elif not sys.stdin.isatty():
        sources = [("<stdin>", io.BytesIO(sys.stdin.buffer.read()))]
    else:
        sys.exit(__doc__)

    OUTPUT_DIR.mkdir(exist_ok=True)
    failed = False
    for name, pdf in sources:
        try:
            date, html = create_page(pdf)
        except Exception as error:
            print(f"{name}: {error}", file=sys.stderr)
            failed = True
            continue
        out = OUTPUT_DIR / f"{date}.html"
        out.write_text(html, encoding="utf-8")
        print(f"{name} -> {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
