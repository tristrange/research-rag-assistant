from pathlib import Path

import pymupdf


def extract_pages(pdf_path: str) -> list[dict]:
    path = Path(pdf_path)
    document = pymupdf.open(path)

    pages = []

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
