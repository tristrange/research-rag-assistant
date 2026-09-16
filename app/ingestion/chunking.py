import re

from app.types import ChunkData, PageData


# A sentence boundary is punctuation followed by whitespace or the end of the
# page. Requiring whitespace avoids treating the decimal point in values such
# as ``3.9%`` as a sentence boundary.
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*(?=\s|$)")
_ABBREVIATIONS = ("fig.", "e.g.", "i.e.", "dr.", "mr.", "mrs.", "vs.")


def _next_chunk_end(text: str, start: int, chunk_size: int, previous_end: int) -> int:
    """Choose a sentence boundary when possible, otherwise a whitespace one."""
    limit = min(start + chunk_size, len(text))
    if limit == len(text):
        return limit

    sentence_end = None
    for match in _SENTENCE_END.finditer(text, start, limit):
        before = text[max(start, match.start() - 4):match.start() + 1].lower()
        if any(before.endswith(abbreviation) for abbreviation in _ABBREVIATIONS):
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
        before = text[max(start, match.start() - 4):match.start() + 1].lower()
        if not any(before.endswith(abbreviation) for abbreviation in _ABBREVIATIONS):
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
    token_start = max(text.rfind(" ", 0, desired), text.rfind("\n", 0, desired), text.rfind("\t", 0, desired)) + 1
    token_end_candidates = [position for position in (text.find(" ", desired), text.find("\n", desired), text.find("\t", desired)) if position >= 0]
    token_end = min(token_end_candidates) if token_end_candidates else len(text)
    if token_end - token_start > chunk_size:
        return desired
    return end


def chunk_pages(
    pages: list[PageData],
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[ChunkData]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size - 1")

    chunks: list[ChunkData] = []

    for page in pages:
        text = page["text"]
        if not text.strip():
            continue

        start = 0
        previous_end = 0
        chunk_index = 0

        while start < len(text):
            end = _next_chunk_end(text, start, chunk_size, previous_end)
            if chunk_index > 0 and end <= previous_end:
                # The proposed overlap leaves too little room for new text.
                # Resume at the covered edge and recalculate without overlap.
                start = previous_end
                continue
            # Text is emitted as an exact page substring, without strip(), so
            # punctuation, numbers, and whitespace at either edge are retained.
            chunks.append(
                {
                    "document": page["document"],
                    "page": page["page"],
                    "chunk_index": chunk_index,
                    "text": text[start:end],
                }
            )
            if end == len(text):
                break

            next_start = _next_chunk_start(text, start, end, overlap, chunk_size)
            # Defensive progress guarantee for pathological inputs.
            start = max(start + 1, next_start)
            previous_end = end
            chunk_index += 1

    return chunks
