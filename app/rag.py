from app.llm.ollama import generate
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
        # Preserve the existing retrieval baselines exactly.  The strict
        # rendered budget applies to expanded windows, whose size can multiply
        # after neighbor lookup.
        sources = [
            {
                "document": chunk.document,
                "page": chunk.page,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
            }
            for chunk in chunks
        ]

    context = render_context(sources)

    prompt = f"""
You are a research assistant.

Answer the question using only the provided context.

If the answer cannot be found in the context, say that you do not have enough information.

Context:
{context}

Question:
{question}

Answer:
"""

    answer = generate(prompt)

    return {
        "answer": answer,
        "sources": sources,
    }
