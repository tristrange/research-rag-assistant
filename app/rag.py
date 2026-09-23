from typing import Literal

from app.grounding import INSUFFICIENT_EVIDENCE, grounded_answer
from app.llm.ollama import generate
from app.prompts import answer_prompt
from app.retrieval import CANDIDATE_COUNT, default_top_k
from app.retrieval.context import expand_chunks, merge_selected_chunks, render_context
from app.retrieval.rerank import rerank_chunks, with_vector_reserve
from app.retrieval.search import list_documents, search_chunks
from app.types import AnswerResult, ChunkData


OVERVIEW_SECTION_PRIORITY = (
    ("conclusion",),
    ("abstract",),
    ("discussion",),
    ("results",),
)


def answer_question(
    question: str,
    limit: int | None = None,
    *,
    use_reranking: bool = True,
    expand_context: bool = False,
    reserve_vector_candidate: bool = False,
    answer_mode: Literal["plain", "verified"] = "plain",
    document: str | None = None,
    overview: bool = False,
) -> AnswerResult:
    limit = default_top_k(expand_context) if limit is None else limit
    if limit < 1:
        raise ValueError("limit must be positive")
    if reserve_vector_candidate and (not use_reranking or expand_context):
        raise ValueError("vector reserve requires unexpanded reranking")
    if reserve_vector_candidate and limit >= CANDIDATE_COUNT:
        raise ValueError(f"vector reserve requires limit below {CANDIDATE_COUNT}")
    candidate_limit = max(CANDIDATE_COUNT, limit) if use_reranking else limit
    if overview:
        if document is None:
            raise ValueError("a paper overview requires a document")
        candidates = []
        for sections in OVERVIEW_SECTION_PRIORITY:
            candidates = search_chunks(
                question, limit=candidate_limit, document=document,
                sections=sections,
            )
            if candidates:
                break
        if not candidates:
            candidates = search_chunks(
                question, limit=candidate_limit, document=document,
            )
    else:
        candidates = search_chunks(question, limit=candidate_limit, document=document)
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
    elif overview:
        sources = merge_selected_chunks(chunks)
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
        answer = generate(answer_prompt(question, context, overview=overview))

    return {
        "answer": answer,
        "sources": sources,
    }


def answer_each_document(
    question: str,
    *,
    answer_mode: Literal["plain", "verified"] = "plain",
) -> AnswerResult:
    """Answer independently for every indexed paper, preserving attribution."""
    documents = list_documents()
    if not documents:
        return {"answer": INSUFFICIENT_EVIDENCE, "sources": []}

    sections = ["Answers by paper, based on retrieved passages:"]
    sources: list[ChunkData] = []
    for document in documents:
        result = answer_question(
            question, document=document, answer_mode=answer_mode, overview=True,
        )
        sections.append(f"{document}:\n{result['answer']}")
        sources.extend(result["sources"])

    return {"answer": "\n\n".join(sections), "sources": sources}
