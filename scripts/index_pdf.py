"""Terminal interface for the application's PDF indexing workflow."""

import argparse
from pathlib import Path

from app.ingestion.indexing import PDF_PATH, index_pdf as index_pdf
from app.llm.errors import OllamaResponseError


def print_progress(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index a PDF, atomically replacing chunks with the same filename. Use distinct filenames for distinct papers."
    )
    parser.add_argument("pdf", type=Path, nargs="?", default=Path(PDF_PATH),
                        help="PDF path (default: data/sample.pdf)")
    args = parser.parse_args()
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        parser.error("PDF must be an existing regular file with a .pdf extension")
    try:
        count = index_pdf(str(args.pdf), progress=print_progress)
    except OllamaResponseError as error:
        parser.exit(status=1, message=f"{error}\nThe existing index was not replaced.\n")
    print(f"Indexed {count} chunks from {args.pdf.name}", flush=True)


if __name__ == "__main__":
    main()
