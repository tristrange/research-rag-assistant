def chunk_pages(
    pages: list[dict],
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[dict]:
    chunks = []

    for page in pages:
        text = page["text"]

        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    {
                        "document": page["document"],
                        "page": page["page"],
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                    }
                )

            start += chunk_size - overlap
            chunk_index += 1

    return chunks
