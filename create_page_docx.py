#!/usr/bin/env python3
"""Render Marktbericht Word files (.docx) into website HTML.

    ./create_page_docx.py ./*.docx        one output/YYYY-MM-DD.html per file
    ./create_page_docx.py < report.docx   a single file from stdin
"""
import html
import io
import re
import sys
import zipfile

import mammoth

from create_page import OUTPUT_DIR, iso_date, split_intro, split_items, template


def extract_date(docx):
    # The date sits in the page header ("Marktbericht vom <TIME field>"), which
    # mammoth ignores. The field's cached result is the date Word last saved.
    with zipfile.ZipFile(docx) as archive:
        for name in archive.namelist():
            if re.fullmatch(r"word/header\d*\.xml", name):
                xml = archive.read(name).decode("utf-8")
                text = "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml))
                match = re.search(r"Marktbericht vom\s*(\d{1,2}\.\s*\S+\s+\d{4})", text)
                if match:
                    return match[1]
    raise ValueError("'Marktbericht vom <date>' not found in the page header")


def extract_pairs(text):
    # A pair is a paragraph that starts with bold text. The rest of the
    # paragraph is the body, with its inline markup (links, bold words) removed.
    pairs = re.findall(r"<p>[^/]*?<strong>(.*?)</strong>(.*?)</p>", text)
    return [(html.unescape(title).strip(),
             html.unescape(re.sub(r"<[^>]+>", "", body)).strip())
            for title, body in pairs]


def create_page(docx):
    """Render one DOCX (path or file object); return (iso date, html)."""
    text = mammoth.convert_to_html(docx).value

    pictures = re.findall(r'data:image[^\"]*', text)
    text_without_pictures = re.sub(r'(?s)<img\b[^>]*\/?>', '', text)
    intro, items = split_intro(extract_pairs(text_without_pictures))

    date = extract_date(docx)
    html_page = template.render(
        full_date=date,
        farm_text=intro["farm_text"],
        aktuelles_markt=intro["aktuelles_markt"],
        problematisches=intro["problematisches"],
        items=split_items(items),
        img=pictures
    )
    return iso_date(date), html_page


def main():
    if len(sys.argv) > 1:
        sources = [(path, path) for path in sys.argv[1:]]
    elif not sys.stdin.isatty():
        sources = [("<stdin>", io.BytesIO(sys.stdin.buffer.read()))]
    else:
        sys.exit(__doc__)

    OUTPUT_DIR.mkdir(exist_ok=True)
    failed = False
    for name, docx in sources:
        try:
            date, html_page = create_page(docx)
        except Exception as error:
            print(f"{name}: {error}", file=sys.stderr)
            failed = True
            continue
        out = OUTPUT_DIR / f"{date}.html"
        out.write_text(html_page, encoding="utf-8")
        print(f"{name} -> {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
