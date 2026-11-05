from pypdf import PdfReader
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"])
)

template = env.get_template("website.html")



reader = PdfReader("../Marinello Marktbericht 30.09.2026.pdf")
number_of_pages = len(reader.pages)
page = reader.pages[0]

print(number_of_pages)
print(page.extract_text(extraction_mode="layout"))




html = template.render(
    full_date=date,
    farm_text=farm_text,
    aktuelles_markt=aktelles_markt,
    problematisches=problematisches,
    items=items_split,
    img=pictures
)

Path("output.html").write_text(html, encoding="utf-8")
