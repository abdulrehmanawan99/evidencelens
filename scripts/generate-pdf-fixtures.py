"""Generate deterministic, original PDF samples; requires the development dependencies."""
from io import BytesIO
from pathlib import Path
import sys

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.fixtures import SOURCES

destination = root / "fixtures/pdf"
destination.mkdir(exist_ok=True)
for index, (name, content) in enumerate(SOURCES, 1):
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=letter, invariant=True)
    canvas.setTitle(name.removesuffix(".txt"))
    text = canvas.beginText(48, 740)
    text.setFont("Helvetica", 11)
    text.setLeading(18)
    for line in content.splitlines():
        # Keep every line inside the page while preserving the exact evaluation quotations.
        text.textLine(line)
    canvas.drawText(text)
    canvas.showPage()
    canvas.save()
    path = destination / f"{index}.pdf"
    path.write_bytes(buffer.getvalue())
    print(path.name)
