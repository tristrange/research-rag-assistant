from app.retrieval.search import search_chunks


query = "What problem are the authors trying to solve?"

results = search_chunks(query)

for i, chunk in enumerate(results, start=1):
    print(
        f"\n--- Result {i} "
        f"| {chunk.document} "
        f"| page {chunk.page} "
        f"| chunk {chunk.chunk_index} ---"
    )
    print(chunk.text[:500])
