from typing import Literal

from app.grounding import grounded_answer
from app.llm.ollama import generate
from app.prompts import answer_prompt
from app.retrieval import CANDIDATE_COUNT, default_top_k
from app.retrieval.context import expand_chunks, render_context
from app.retrieval.rerank import rerank_chunks
from app.retrieval.search import search_chunks
from app.types import AnswerResult, ChunkData


def answer_question(
    question: str,
    limit: int | None = None,
    *,
    use_reranking: bool = True,
    expand_context: bool = False,
    answer_mode: Literal["plain", "verified"] = "plain",
) -> AnswerResult:
    limit = default_top_k(expand_context) if limit is None else limit
    if limit < 1:
        raise ValueError("limit must be positive")
    candidates = search_chunks(question, limit=max(CANDIDATE_COUNT, limit) if use_reranking else limit)

    chunks = rerank_chunks(question, candidates, limit=limit) if use_reranking else candidates

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
