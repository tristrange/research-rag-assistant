from app.embeddings import embed_text
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages


pages = extract_pages("data/sample.pdf")
chunks = chunk_pages(pages)

embedding = embed_text(chunks[0]["text"])

print(f"Chunk text: {chunks[0]['text'][:200]}")
print(f"Embedding dimensions: {len(embedding)}")
