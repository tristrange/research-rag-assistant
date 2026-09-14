from pathlib import Path

import pymupdf

from app.types import PageData


def extract_pages(pdf_path: str) -> list[PageData]:
    path = Path(pdf_path)
    document = pymupdf.open(path)

    pages: list[PageData] = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text").strip()

        pages.append(
            {
                "document": path.name,
                "page": page_number,
                "text": text,
            }
        )

    document.close()
    return pages
