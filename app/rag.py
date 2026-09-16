from app.llm.ollama import generate
from app.retrieval.rerank import rerank_chunks
from app.retrieval.search import search_chunks
from app.types import AnswerResult, ChunkData


def answer_question(
    question: str, limit: int = 3, *, use_reranking: bool = True,
) -> AnswerResult:
    candidates = search_chunks(question, limit=10 if use_reranking else limit)

    chunks = rerank_chunks(question, candidates, limit=limit) if use_reranking else candidates

    context_parts = []

    for chunk in chunks:
        context_parts.append(
            f"[{chunk.document}, page {chunk.page}]\n{chunk.text}"
        )

    context = "\n\n".join(context_parts)

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

    sources: list[ChunkData] = [
        {
            "document": chunk.document,
            "page": chunk.page,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
        }
        for chunk in chunks
    ]

    return {
        "answer": answer,
        "sources": sources,
    }
