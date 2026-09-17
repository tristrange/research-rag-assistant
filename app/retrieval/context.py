"""Build bounded context windows around ranked retrieval results.

The ``chunk_index`` on a returned source is the first stored chunk included in
that source's text.  A source may therefore represent several consecutive
chunks from one document page after overlap has been removed.
"""

from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import load_only

from app.db.database import SessionLocal
from app.db.models import Chunk
from app.types import ChunkData


MAX_CONTEXT_CHARS = 6000
NEIGHBOR_RADIUS = 2

# A tiny match (commonly punctuation or a short word) is not useful evidence
# that the indexed chunks overlap.  Normal indexed overlap is much longer.
_MIN_OVERLAP_CHARS = 8

type ChunkKey = tuple[str, int, int]
type PageKey = tuple[str, int]


@dataclass(frozen=True)
class _RankedChunk:
    chunk: Chunk
    priority: int


def _key(chunk: Chunk) -> ChunkKey:
    return (chunk.document, chunk.page, chunk.chunk_index)


def render_context(sources: list[ChunkData]) -> str:
    """Render exactly the evidence represented by ``sources`` for the prompt."""
    return "\n\n".join(
        f"[{source['document']}, page {source['page']}]\n{source['text']}"
        for source in sources
    )


def _merge_adjacent_text(left: str, right: str) -> str:
    """Join adjacent indexed chunks, removing only exact boundary overlap."""
    maximum = min(len(left), len(right))
    for overlap in range(maximum, _MIN_OVERLAP_CHARS - 1, -1):
        if left.endswith(right[:overlap]):
            return left + right[overlap:]
    separator = (
        ""
        if not left or not right or left[-1].isspace() or right[0].isspace()
        else " "
    )
    return left + separator + right


def _sources_for_chunks(chunks: dict[ChunkKey, _RankedChunk]) -> list[ChunkData]:
    """Merge consecutive selected chunks and order windows by seed priority."""
    by_page: dict[PageKey, list[_RankedChunk]] = {}
    for ranked_chunk in chunks.values():
        chunk = ranked_chunk.chunk
        by_page.setdefault((chunk.document, chunk.page), []).append(ranked_chunk)

    windows: list[tuple[int, ChunkData]] = []
    for (document, page), page_chunks in by_page.items():
        ordered = sorted(page_chunks, key=lambda item: item.chunk.chunk_index)
        current = ordered[0]
        start_index = current.chunk.chunk_index
        previous_index = start_index
        text = current.chunk.text
        priority = current.priority

        for item in ordered[1:]:
            index = item.chunk.chunk_index
            if index == previous_index + 1:
                text = _merge_adjacent_text(text, item.chunk.text)
                priority = min(priority, item.priority)
            else:
                windows.append((priority, {
                    "document": document,
                    "page": page,
                    "chunk_index": start_index,
                    "text": text,
                }))
                start_index = index
                text = item.chunk.text
                priority = item.priority
            previous_index = index

        windows.append((priority, {
            "document": document,
            "page": page,
            "chunk_index": start_index,
            "text": text,
        }))

    windows.sort(key=lambda item: (
        item[0], item[1]["document"], item[1]["page"], item[1]["chunk_index"],
    ))
    return [source for _, source in windows]


def _neighbor_offsets() -> list[int]:
    """Return closer neighbors before farther ones for budget fallback."""
    return [
        offset
        for distance in range(1, NEIGHBOR_RADIUS + 1)
        for offset in (-distance, distance)
    ]


def _neighbor_keys(seeds: list[Chunk]) -> list[ChunkKey]:
    seed_keys = {_key(seed) for seed in seeds}
    keys: set[ChunkKey] = set()
    for seed in seeds:
        for offset in _neighbor_offsets():
            index = seed.chunk_index + offset
            key = (seed.document, seed.page, index)
            if index >= 0 and key not in seed_keys:
                keys.add(key)
    return sorted(keys)


def _load_neighbors(seeds: list[Chunk]) -> dict[ChunkKey, Chunk]:
    """Load all bounded page-local neighbors using at most one DB query."""
    keys = _neighbor_keys(seeds)
    if not keys:
        return {}

    conditions = [
        and_(
            Chunk.document == document,
            Chunk.page == page,
            Chunk.chunk_index == chunk_index,
        )
        for document, page, chunk_index in keys
    ]
    statement = (
        select(Chunk)
        .options(load_only(
            Chunk.document, Chunk.page, Chunk.chunk_index, Chunk.text,
        ))
        .where(or_(*conditions))
    )

    db = SessionLocal()
    try:
        requested = set(keys)
        return {
            _key(chunk): chunk
            for chunk in db.scalars(statement)
            if _key(chunk) in requested
        }
    finally:
        db.close()


def _with_chunk(
    selected: dict[ChunkKey, _RankedChunk],
    chunk: Chunk,
    priority: int,
) -> dict[ChunkKey, _RankedChunk]:
    candidate = dict(selected)
    key = _key(chunk)
    existing = candidate.get(key)
    if existing is None or priority < existing.priority:
        candidate[key] = _RankedChunk(chunk=chunk, priority=priority)
    return candidate


def _fits(chunks: dict[ChunkKey, _RankedChunk], max_chars: int) -> bool:
    return len(render_context(_sources_for_chunks(chunks))) <= max_chars


def expand_chunks(
    seeds: list[Chunk],
    max_chars: int = MAX_CONTEXT_CHARS,
) -> list[ChunkData]:
    """Expand ranked seeds to page-local neighboring chunks within a hard cap.

    Ranked seeds receive budget before neighbors.  If the full expansion is too
    large, lower-priority seed windows are dropped whole and the remaining
    budget is spent on neighbors in seed rank order.
    """
    if max_chars < 0:
        raise ValueError("max_chars must be non-negative")
    if not seeds:
        return []

    neighbors = _load_neighbors(seeds)
    selected: dict[ChunkKey, _RankedChunk] = {}
    included_seeds: list[tuple[int, Chunk]] = []

    # Spend budget on every ranked seed first.  Stopping at the first seed that
    # does not fit preserves retrieval priority rather than skipping around it.
    for priority, seed in enumerate(seeds):
        candidate = _with_chunk(selected, seed, priority)
        if not _fits(candidate, max_chars):
            break
        selected = candidate
        included_seeds.append((priority, seed))

    # Add nearby chunks only after all seed evidence that fits.  A shared
    # neighbor is represented once, at its highest owning seed priority.
    for priority, seed in included_seeds:
        for offset in _neighbor_offsets():
            neighbor = neighbors.get((seed.document, seed.page, seed.chunk_index + offset))
            if neighbor is None:
                continue
            candidate = _with_chunk(selected, neighbor, priority)
            if _fits(candidate, max_chars):
                selected = candidate

    return _sources_for_chunks(selected)
