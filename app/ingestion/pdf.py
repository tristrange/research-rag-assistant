from pathlib import Path

import pymupdf

from app.types import PageData


def extract_pages(
    pdf_path: str,
    *,
    max_pages: int | None = None,
    max_page_chars: int | None = None,
    max_total_chars: int | None = None,
) -> list[PageData]:
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be greater than zero")
    if max_page_chars is not None and max_page_chars <= 0:
        raise ValueError("max_page_chars must be greater than zero")
    if max_total_chars is not None and max_total_chars <= 0:
        raise ValueError("max_total_chars must be greater than zero")

    path = Path(pdf_path)
    document = pymupdf.open(path)

    pages: list[PageData] = []
    total_chars = 0
    try:
        if max_pages is not None and len(document) > max_pages:
            raise ValueError(f"PDF exceeds the {max_pages}-page limit")
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text")
            if max_page_chars is not None and len(text) > max_page_chars:
                raise ValueError(f"PDF page {page_number} exceeds the {max_page_chars}-character limit")
            total_chars += len(text)
            if max_total_chars is not None and total_chars > max_total_chars:
                raise ValueError(f"PDF exceeds the {max_total_chars}-character text limit")

            pages.append(
                {
                    "document": path.name,
                    "page": page_number,
                    "text": text.strip(),
                }
            )
    finally:
        document.close()
    return pages
