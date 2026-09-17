from app.llm.ollama import generate
from app.prompts import answer_prompt
from app.retrieval.context import expand_chunks, render_context
from app.retrieval.rerank import rerank_chunks
from app.retrieval.search import search_chunks
from app.types import AnswerResult, ChunkData


def answer_question(
    question: str,
    limit: int = 3,
    *,
    use_reranking: bool = True,
    expand_context: bool = False,
) -> AnswerResult:
    candidates = search_chunks(question, limit=10 if use_reranking else limit)

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

    context = render_context(sources)

    prompt = answer_prompt(question, context)

    answer = generate(prompt)

    return {
        "answer": answer,
        "sources": sources,
    }
