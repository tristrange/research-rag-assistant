import re

from app.ingestion.sections import UNKNOWN_SECTION, section_ranges
from app.types import ChunkData, PageData


# A sentence boundary is punctuation followed by whitespace or the end of the
# page. Requiring whitespace avoids treating the decimal point in values such
# as ``3.9%`` as a sentence boundary.
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*(?=\s|$)")
_ABBREVIATION_PERIOD = re.compile(
    r"(?:\bet\s+al|\b(?:fig|e\.g|i\.e|dr|mr|mrs|vs))\.$",
    re.IGNORECASE,
)
_ABBREVIATION_LOOKBEHIND = 64


def _is_abbreviation_period(text: str, match: re.Match[str]) -> bool:
    """Return whether a sentence-ending period belongs to a known abbreviation."""
    # et al. permits any whitespace (including extracted PDF line breaks)
    # between its tokens. Search against the full prefix so token boundaries
    # cannot be fabricated by trimming the text.
    # Search only the local suffix. A full-prefix search at every punctuation
    # mark makes punctuation-heavy pages quadratic in length.
    return _ABBREVIATION_PERIOD.search(
        text, max(0, match.start() + 1 - _ABBREVIATION_LOOKBEHIND), match.start() + 1,
    ) is not None


def _next_chunk_end(text: str, start: int, chunk_size: int, previous_end: int) -> int:
    """Choose a sentence boundary when possible, otherwise a whitespace one."""
    limit = min(start + chunk_size, len(text))
    if limit == len(text):
        return limit

    sentence_end = None
    for match in _SENTENCE_END.finditer(text, start, limit):
        if _is_abbreviation_period(text, match):
            continue
        if match.end() > previous_end:
            sentence_end = match.end()
    if sentence_end is not None and sentence_end > start:
        return sentence_end

    # For a long sentence, break at the last whitespace before the limit. If
    # there is no whitespace (a long token), the hard limit guarantees progress.
    whitespace = text.rfind(" ", start + 1, limit)
    newline = text.rfind("\n", start + 1, limit)
    tab = text.rfind("\t", start + 1, limit)
    boundary = max(whitespace, newline, tab)
    if boundary > start:
        return boundary + 1
    return limit


def _next_chunk_start(text: str, start: int, end: int, overlap: int, chunk_size: int) -> int:
    """Choose a useful overlap start, preferring sentence and whitespace edges."""
    desired = max(start + 1, end - overlap)
    if desired >= end:
        return end

    # Starting at whitespace keeps words intact. This can produce more than
    # the requested overlap when the nearest useful boundary is farther back.
    # Prefer a sentence boundary at or before the desired overlap start.
    sentence_starts = []
    for match in _SENTENCE_END.finditer(text, start + 1, desired + 1):
        if not _is_abbreviation_period(text, match):
            sentence_starts.append(match.end())
    if sentence_starts:
        return sentence_starts[-1]

    whitespace = text.rfind(" ", start + 1, desired + 1)
    newline = text.rfind("\n", start + 1, desired + 1)
    tab = text.rfind("\t", start + 1, desired + 1)
    boundary = max(whitespace, newline, tab)
    if boundary >= start + 1:
        return boundary + 1

    # Do not cut an ordinary word just to satisfy overlap. Hard splitting is
    # useful only when the word itself exceeds the configured chunk size.
    # Include the delimiters around a token of exactly chunk_size characters.
    window_start = max(0, desired - chunk_size - 1)
    window_end = min(len(text), desired + chunk_size + 1)
    last_separator = max(
        text.rfind(" ", window_start, desired),
        text.rfind("\n", window_start, desired),
        text.rfind("\t", window_start, desired),
    )
    if last_separator < 0 and window_start > 0:
        return desired
    token_start = last_separator + 1
    token_end_candidates = [
        position for position in (
            text.find(" ", desired, window_end),
            text.find("\n", desired, window_end),
            text.find("\t", desired, window_end),
        ) if position >= 0
    ]
    if not token_end_candidates and window_end < len(text):
        return desired
    token_end = min(token_end_candidates) if token_end_candidates else len(text)
    if token_end - token_start > chunk_size:
        return desired
    return end


def chunk_pages(
    pages: list[PageData],
    chunk_size: int = 1000,
    overlap: int = 200,
    *,
    max_chunks: int | None = None,
) -> list[ChunkData]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size - 1")
    if max_chunks is not None and max_chunks <= 0:
        raise ValueError("max_chunks must be greater than zero")

    chunks: list[ChunkData] = []
    current_document: str | None = None
    current_section = UNKNOWN_SECTION

    for page in pages:
        text = page["text"]
        if not text.strip():
            continue

        if page["document"] != current_document:
            current_document = page["document"]
            current_section = UNKNOWN_SECTION
        if "section" in page:
            current_section = page["section"]

        ranges, ending_section = section_ranges(text, current_section)
        chunk_index = 0

        for range_start, range_end, section in ranges:
            section_text = text[range_start:range_end]
            start = 0
            previous_end = 0

            while start < len(section_text):
                end = _next_chunk_end(section_text, start, chunk_size, previous_end)
                if start > 0 and end <= previous_end:
                    # The proposed overlap leaves too little room for new text.
                    # Resume at the covered edge and recalculate without overlap.
                    start = previous_end
                    continue
                # Text is emitted as an exact page substring, without strip(), so
                # punctuation, numbers, and whitespace at either edge are retained.
                if max_chunks is not None and len(chunks) >= max_chunks:
                    raise ValueError(f"PDF exceeds the {max_chunks}-chunk limit")
                chunks.append(
                    {
                        "document": page["document"],
                        "page": page["page"],
                        "chunk_index": chunk_index,
                        "text": section_text[start:end],
                        "section": section,
                    }
                )
                chunk_index += 1
                if end == len(section_text):
                    break

                next_start = _next_chunk_start(
                    section_text, start, end, overlap, chunk_size,
                )
                # Defensive progress guarantee for pathological inputs.
                start = max(start + 1, next_start)
                previous_end = end

        current_section = ending_section

    return chunks
