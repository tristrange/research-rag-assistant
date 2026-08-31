from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages


pages = extract_pages("data/sample.pdf")
chunks = chunk_pages(pages)

print(f"Extracted {len(pages)} pages")
print(f"Created {len(chunks)} chunks")

for chunk in chunks[:3]:
    print(
        f"\n--- {chunk['document']} "
        f"| page {chunk['page']} "
        f"| chunk {chunk['chunk_index']} ---\n"
    )
    print(chunk["text"][:500])
    