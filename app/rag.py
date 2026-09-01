from app.llm.ollama import generate
from app.retrieval.search import search_chunks


def answer_question(question: str, limit: int = 5) -> dict:
    chunks = search_chunks(question, limit=limit)

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

    sources = [
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
