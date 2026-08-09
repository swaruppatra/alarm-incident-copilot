import uuid
from pathlib import Path

from rag.ingestion.chunker import chunk_markdown, chunk_text
from rag.ingestion.embedder import (
    get_embeddings_batch,
    store_embeddings_in_qdrant_batch,
)
from rag.ingestion.loader import load_markdown

DOCUMENTS_DIR = Path("./rag/documents")

SKIP_SECTIONS = {"Related Documents"}  # navigational, not knowledge content


def ingest_documents(documents_dir, chunk_size=1000, chunk_overlap=200) -> list[dict]:
    """
    Ingest documents from the specified directory and chunk them.

    Each document is first split on markdown headers. Sections in
    SKIP_SECTIONS (e.g. "Related Documents") are dropped entirely -- they're
    navigational cross-references, not knowledge content worth embedding. A
    remaining header section is only run through the character-based
    splitter when it's still too big for one chunk (>= chunk_size) --
    sections already under that size are kept as-is, so content isn't
    chunked twice and duplicated.

    Args:
        documents_dir (str | Path): The path to the directory containing the documents.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of overlapping characters between chunks.
    Returns:
        list[dict]: Chunks as {"content": str, "metadata": dict}, where metadata
            combines the document's frontmatter, its source path, and the
            header path (Header 1/Header 2) the chunk came from.
    """
    documents_dir = Path(documents_dir)
    chunks = []
    for file_path in documents_dir.glob("**/*.md"):
        # Frontmatter-stripped content + metadata for this document.
        doc_content, doc_metadata = load_markdown(file_path)

        # Split on headers first, these are the natural semantic boundaries.
        header_chunks = chunk_markdown(doc_content, headers_to_split_on=[("#", "Header 1"), ("##", "Header 2")])

        for header_chunk in header_chunks:
            if header_chunk.metadata.get("Header 2") in SKIP_SECTIONS:
                continue

            chunk_metadata = {**doc_metadata, **header_chunk.metadata, "source": str(file_path)}

            if len(header_chunk.page_content) >= chunk_size:
                # Section too large for one chunk, split it further.
                for sub_chunk in chunk_text(header_chunk.page_content, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
                    chunks.append({"content": sub_chunk, "metadata": chunk_metadata})
            else:
                chunks.append({"content": header_chunk.page_content, "metadata": chunk_metadata})

    return chunks


def embed_and_store_documents(documents_dir, chunk_size=1000, chunk_overlap=200) -> int:
    """
    Chunk, embed, and upsert all documents into Qdrant.

    Each chunk's vector_id is deterministic (uuid5 of its source path + its
    position within that source), so re-running ingestion after a document
    edit updates the existing point's vector/metadata in place instead of
    creating a duplicate.

    Args:
        documents_dir (str | Path): The path to the directory containing the documents.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of overlapping characters between chunks.

    Returns:
        int: the number of chunks embedded and stored.
    """
    chunks = ingest_documents(documents_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        return 0

    chunk_index_by_source: dict[str, int] = {}
    vector_ids = []
    for chunk in chunks:
        source = chunk["metadata"]["source"]
        index = chunk_index_by_source.get(source, 0)
        chunk_index_by_source[source] = index + 1
        vector_ids.append(str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}#{index}")))

    contents = [chunk["content"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    embeddings = get_embeddings_batch(contents)
    store_embeddings_in_qdrant_batch(embeddings, vector_ids, contents, metadatas)

    return len(chunks)


if __name__ == "__main__":
    count = embed_and_store_documents(DOCUMENTS_DIR)
    print(f"Embedded and stored {count} chunks in Qdrant.")
