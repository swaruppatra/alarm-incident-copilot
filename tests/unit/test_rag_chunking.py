"""Unit tests for rag/ingestion/chunker.py's pure splitting functions --
no filesystem, no embeddings. Complements rag/tests/eval_retrieval.py, which
tests retrieval quality against a live Qdrant collection; these test the
chunking logic in isolation.
"""

from rag.ingestion.chunker import chunk_markdown, chunk_text

SAMPLE_DOC = """# Troubleshooting Manual — High Vibration Alarm

## Symptom

A High Vibration alarm fires when bearing vibration exceeds threshold.

## Likely Causes

Bearing wear or misalignment is the most common cause.

## Related Documents

- Engineering Standard — Vibration Severity Limits
"""


class TestChunkMarkdown:
    def test_splits_on_h1_and_h2_headers(self):
        chunks = chunk_markdown(SAMPLE_DOC, headers_to_split_on=[("#", "Header 1"), ("##", "Header 2")])
        # One chunk per section: Symptom, Likely Causes, Related Documents.
        assert len(chunks) == 3
        headers = [c.metadata.get("Header 2") for c in chunks]
        assert headers == ["Symptom", "Likely Causes", "Related Documents"]

    def test_header1_is_carried_as_metadata_on_every_chunk(self):
        chunks = chunk_markdown(SAMPLE_DOC, headers_to_split_on=[("#", "Header 1"), ("##", "Header 2")])
        for chunk in chunks:
            assert chunk.metadata.get("Header 1") == "Troubleshooting Manual — High Vibration Alarm"

    def test_chunk_content_does_not_include_the_header_line_itself(self):
        chunks = chunk_markdown(SAMPLE_DOC, headers_to_split_on=[("#", "Header 1"), ("##", "Header 2")])
        symptom_chunk = next(c for c in chunks if c.metadata.get("Header 2") == "Symptom")
        assert "## Symptom" not in symptom_chunk.page_content
        assert "bearing vibration exceeds threshold" in symptom_chunk.page_content

    def test_document_with_no_headers_returns_one_chunk(self):
        chunks = chunk_markdown("Just plain text, no headers at all.", headers_to_split_on=[("#", "Header 1")])
        assert len(chunks) == 1


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        chunks = chunk_text("A short sentence.", chunk_size=1000, chunk_overlap=200)
        assert chunks == ["A short sentence."]

    def test_long_text_is_split_into_multiple_chunks(self):
        long_text = "word " * 500  # ~2500 chars, well over chunk_size
        chunks = chunk_text(long_text, chunk_size=1000, chunk_overlap=200)
        assert len(chunks) > 1
        assert all(len(c) <= 1000 for c in chunks)

    def test_consecutive_chunks_overlap(self):
        long_text = "".join(f"sentence{i}. " for i in range(200))
        chunks = chunk_text(long_text, chunk_size=500, chunk_overlap=100)
        assert len(chunks) > 1
        # With overlap > 0, the same content is duplicated across chunk
        # boundaries, so the chunks' combined length exceeds the original
        # text -- a robust way to prove overlap happened without depending
        # on the splitter's exact boundary-placement behavior.
        assert sum(len(c) for c in chunks) > len(long_text)
