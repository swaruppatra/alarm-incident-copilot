from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    title: str = Field(..., description="The source document's title, from its frontmatter.")
    doc_type: str = Field(..., description="The source document's type, from its frontmatter (e.g. troubleshooting_manual).")
    source: str = Field(..., description="Path to the source document this chunk came from.")
    section: str | None = Field(
        None, description="The section heading this chunk belongs to (Header 2, falling back to Header 1)."
    )
    assets: list[str] = Field(default_factory=list, description="Asset IDs the source document is relevant to.")
    sites: list[str] = Field(default_factory=list, description="Sites the source document is relevant to.")
    tags: list[str] = Field(default_factory=list, description="Free-form tags from the source document's frontmatter.")
    adversarial: bool = Field(
        False, description="Whether this chunk was flagged as containing a potential prompt-injection pattern."
    )

class RetrievalQuery(BaseModel):
    query: str = Field(..., description="The query string to search for relevant documents.")
    top_k: int = Field(5, description="The number of top relevant documents to retrieve.")
    asset_id: str | None = Field(None, description="Restrict retrieval to documents relevant to this asset_id.")
    doc_type: str | None = Field(None, description="Restrict retrieval to documents of this doc_type.")

class RetrievedChunk(BaseModel):
    chunk_id: str = Field(..., description="The retrieved chunk's unique identifier (its Qdrant point id).")
    content: str = Field(..., description="The content of the retrieved chunk.")
    metadata: ChunkMetadata = Field(..., description="Typed metadata associated with the retrieved chunk.")
    score: float = Field(..., description="The chunk's similarity score for this query (higher is more relevant).")

class Citation(BaseModel):
    chunk_id: str = Field(..., description="The chunk this citation corresponds to.")
    source: str = Field(..., description="The source document path this citation is drawn from.")
    section: str | None = Field(None, description="The section heading within the source document.")
    score: float = Field(..., description="The relevance score for this citation.")
    snippet: str = Field("", description="A short preview of the cited chunk's content, for display.")

class RetrievalResult(BaseModel):
    query: str = Field(..., description="The original query string.")
    chunks: list[RetrievedChunk] = Field(default_factory=list, description="The retrieved chunks for this query.")
    citations: list[Citation] = Field(default_factory=list, description="Citations derived from the retrieved chunks.")
    confident: bool = Field(..., description="Whether retrieval found results meeting the confidence threshold.")
    message: str | None = Field(
        None, description="Human-readable message, e.g. explaining low-confidence or no-result retrieval."
    )
