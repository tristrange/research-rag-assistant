"""Generate a small, clearly synthetic PDF for local demonstrations."""

from pathlib import Path

import pymupdf

DEFAULT_OUTPUT = Path("data/synthetic-portfolio-example.pdf")

BANNER = "SYNTHETIC EXAMPLE - NOT A REAL PAPER"
TITLE = "Synthetic Portfolio Example"
SUBTITLE = "A fictional study generated for local RAG demonstrations."
ABSTRACT = (
    "This document is entirely synthetic. It contains no real participants, "
    "data, or findings. It exists only to demonstrate PDF indexing, retrieval, "
    "and evidence inspection in the research assistant."
)
METHODS = (
    "The fictional example describes a four-week recall program with weekly "
    "practice sessions. No real experiment was conducted."
)
RESULTS = (
    "The fictional program improved recall by 12 percentage points after four weeks."
)
DISCUSSION = (
    "This result is illustrative and was written for the example. It is not "
    "evidence about any real intervention, population, or paper."
)


def add_block(
    page: pymupdf.Page,
    text: str,
    *,
    y: float,
    height: float,
    size: float,
    color: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    page.insert_textbox(
        pymupdf.Rect(72, y, 523, y + height),
        text,
        fontsize=size,
        fontname="helv",
        color=color,
    )


def add_page(
    document: pymupdf.Document,
    blocks: list[tuple[str, float, float]],
) -> None:
    page = document.new_page()
    page.insert_text((72, 48), BANNER, fontsize=9, fontname="helv", color=(0.65, 0, 0))
    y = 78.0
    for text, size, height in blocks:
        add_block(page, text, y=y, height=height, size=size)
        y += height


def generate_example_pdf(output: Path = DEFAULT_OUTPUT) -> Path:
    """Create the synthetic PDF, refusing to overwrite an existing file."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open()
    try:
        try:
            with output.open("xb"):
                pass
        except FileExistsError:
            raise FileExistsError(
                f"{output} already exists; refusing to overwrite it. "
                "Remove or rename the existing file and run the command again."
            ) from None

        try:
            document.set_metadata(
                {
                    "title": TITLE,
                    "author": "Synthetic example generator",
                    "subject": "Fictional document for a local RAG demonstration",
                    "keywords": "synthetic, example, not a real paper",
                    "creator": "research-rag-assistant",
                }
            )
            add_page(
                document,
                [
                    (TITLE, 20, 34),
                    (SUBTITLE, 11, 54),
                    ("Abstract", 14, 26),
                    (ABSTRACT, 11, 96),
                    ("Methods", 14, 26),
                    (METHODS, 11, 86),
                ],
            )
            add_page(
                document,
                [
                    ("Results", 14, 26),
                    (RESULTS, 11, 78),
                    ("Discussion", 14, 26),
                    (DISCUSSION, 11, 96),
                ],
            )
            document.save(output)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    finally:
        document.close()

    return output


def main() -> None:
    try:
        output = generate_example_pdf()
    except FileExistsError as error:
        raise SystemExit(str(error)) from None
    print(f"Created synthetic example: {output}")
    print(f"Index it with: uv run python -m scripts.index_pdf {output}")


if __name__ == "__main__":
    main()
