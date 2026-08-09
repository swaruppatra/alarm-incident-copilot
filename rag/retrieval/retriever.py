import logging

from qdrant_client.http.models import ScoredPoint
from qdrant_client.models import FieldCondition, Filter, MatchValue

from rag.config import get_settings
from rag.ingestion.embedder import get_embeddings, get_qdrant_client
from rag.retrieval.models import (
    ChunkMetadata,
    Citation,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
)
from rag.retrieval.sanity_check import flag_suspicious_patterns

logger = logging.getLogger("rag.retrieval")

CITATION_SNIPPET_CHARS = 240


def _build_filter(query: RetrievalQuery) -> Filter | None:
    """Build a Qdrant Filter from asset_id/doc_type, against the assets/doc_type payload fields.

    Args:
        query (RetrievalQuery): the query whose asset_id/doc_type become filter conditions.

    Returns:
        Filter | None: the filter to apply, or None if neither field was set.
    """
    conditions = []
    if query.asset_id is not None:
        # assets is a list payload field; MatchValue checks list membership.
        conditions.append(FieldCondition(key="assets", match=MatchValue(value=query.asset_id)))
    if query.doc_type is not None:
        conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=query.doc_type)))
    return Filter(must=conditions) if conditions else None


def _point_to_chunk(point: ScoredPoint) -> RetrievedChunk:
    """Map a Qdrant ScoredPoint to a typed RetrievedChunk.

    Args:
        point (ScoredPoint): a scored point, payload holding "content" plus the flat metadata fields.

    Returns:
        RetrievedChunk: the typed chunk, with metadata built from the point's payload.
    """
    payload = dict(point.payload or {})
    content = payload.get("content", "")

    matched_patterns = flag_suspicious_patterns(content)
    if matched_patterns:
        logger.warning(
            "suspicious_chunk_content",
            extra={"chunk_id": str(point.id), "source": payload.get("source"), "matched_patterns": matched_patterns},
        )

    metadata = ChunkMetadata(
        title=payload.get("title", ""),
        doc_type=payload.get("doc_type", ""),
        source=payload.get("source", ""),
        section=payload.get("Header 2") or payload.get("Header 1"),
        assets=payload.get("assets", []),
        sites=payload.get("sites", []),
        tags=payload.get("tags", []),
        adversarial=bool(matched_patterns),
    )
    return RetrievedChunk(chunk_id=str(point.id), content=content, metadata=metadata, score=point.score)


def _snippet(content: str) -> str:
    """Collapse whitespace and truncate chunk content to a short display preview.

    Args:
        content (str): the chunk's full content.

    Returns:
        str: the first CITATION_SNIPPET_CHARS characters of content, whitespace-collapsed,
            with a trailing ellipsis if it was truncated.
    """
    collapsed = " ".join(content.split())
    if len(collapsed) <= CITATION_SNIPPET_CHARS:
        return collapsed
    return collapsed[:CITATION_SNIPPET_CHARS].rstrip() + "..."


def retrieve(query: RetrievalQuery) -> RetrievalResult:
    """
    Retrieve relevant document chunks for a query, with an explicit confidence check.

    Args:
        query (RetrievalQuery): the query text plus top_k/asset_id/doc_type filters.

    Returns:
        RetrievalResult: confident=True with chunks/citations when the best match
            clears RETRIEVAL_SCORE_THRESHOLD; confident=False with an explanatory
            message and no chunks otherwise -- callers never have to guess.
    """
    settings = get_settings()
    query_embedding = get_embeddings(query.query)
    client = get_qdrant_client()

    response = client.query_points(
        collection_name=settings.qdrant_collection_name,
        query=query_embedding,
        query_filter=_build_filter(query),
        limit=query.top_k,
        with_payload=True,
    )
    points = response.points

    best_score = points[0].score if points else None
    if best_score is None or best_score < settings.retrieval_score_threshold:
        message = (
            "No documents matched this query."
            if best_score is None
            else (
                f"Best match score {best_score:.2f} is below the confidence threshold "
                f"({settings.retrieval_score_threshold}); no reliable evidence found."
            )
        )
        return RetrievalResult(query=query.query, chunks=[], citations=[], confident=False, message=message)

    chunks = [_point_to_chunk(point) for point in points]
    citations = [
        Citation(
            chunk_id=chunk.chunk_id,
            source=chunk.metadata.source,
            section=chunk.metadata.section,
            score=chunk.score,
            snippet=_snippet(chunk.content),
        )
        for chunk in chunks
    ]
    return RetrievalResult(query=query.query, chunks=chunks, citations=citations, confident=True, message=None)


if __name__ == "__main__":
    # Example usage
    result = retrieve(RetrievalQuery(query="high vibration bearing wear boiler feed pump", top_k=5))
    print(f"Query: {result.query}")
    print(f"Confident: {result.confident}")
    if result.message:
        print(f"Message: {result.message}")

    for i, chunk in enumerate(result.chunks):
        print(f"\nChunk {i + 1} (score={chunk.score:.4f}, section={chunk.metadata.section!r}, source={chunk.metadata.source}):")
        print(chunk.content[:200])

    print(f"\nCitations: {len(result.citations)}")
    for citation in result.citations:
        print(f" - {citation.source} | {citation.section} | score={citation.score:.4f}")
