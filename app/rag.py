from typing import Literal

from app.grounding import INSUFFICIENT_EVIDENCE, grounded_answer
from app.llm.ollama import generate
from app.prompts import answer_prompt
from app.retrieval import CANDIDATE_COUNT, default_top_k
from app.retrieval.context import expand_chunks, render_context
from app.retrieval.rerank import rerank_chunks, with_vector_reserve
from app.retrieval.search import search_chunks
from app.types import AnswerResult, ChunkData


def answer_question(
    question: str,
    limit: int | None = None,
    *,
    use_reranking: bool = True,
    expand_context: bool = False,
    reserve_vector_candidate: bool = False,
    answer_mode: Literal["plain", "verified"] = "plain",
    document: str | None = None,
) -> AnswerResult:
    limit = default_top_k(expand_context) if limit is None else limit
    if limit < 1:
        raise ValueError("limit must be positive")
    if reserve_vector_candidate and (not use_reranking or expand_context):
        raise ValueError("vector reserve requires unexpanded reranking")
    if reserve_vector_candidate and limit >= CANDIDATE_COUNT:
        raise ValueError(f"vector reserve requires limit below {CANDIDATE_COUNT}")
    candidates = search_chunks(
        question,
        limit=max(CANDIDATE_COUNT, limit) if use_reranking else limit,
        document=document,
    )
    if not candidates:
        return {
            "answer": INSUFFICIENT_EVIDENCE,
            "sources": [],
        }

    chunks = rerank_chunks(question, candidates, limit=limit) if use_reranking else candidates
    if reserve_vector_candidate:
        chunks = with_vector_reserve(chunks, candidates)

    sources: list[ChunkData]
    if expand_context:
        sources = expand_chunks(chunks)
    else:
        # Preserve unexpanded retrieval selection. The strict
        # rendered budget applies to expanded windows, whose size can multiply
        # after neighbor lookup.
        sources = [
            {
                "document": chunk.document,
                "page": chunk.page,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "section": chunk.section or "unknown",
            }
            for chunk in chunks
        ]

    if answer_mode == "verified":
        answer = grounded_answer(question, sources)
    else:
        context = render_context(sources)
        answer = generate(answer_prompt(question, context))

    return {
        "answer": answer,
        "sources": sources,
    }
