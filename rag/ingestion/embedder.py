from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from rag.config import get_settings


def get_embeddings(text: str, model_name: str | None = None) -> list[float]:
    """
    Get embeddings for the given text using the configured OpenAI embedding model.

    Args:
        text (str): The input text to generate embeddings for.
        model_name (str | None): The OpenAI embedding model to use; defaults to settings.embedding_model.

    Returns:
        list[float]: The embeddings for the input text.
    """
    settings = get_settings()
    embeddings = OpenAIEmbeddings(model=model_name or settings.embedding_model, api_key=settings.llm_api_key)
    return embeddings.embed_query(text)


def get_embeddings_batch(texts: list[str], model_name: str | None = None) -> list[list[float]]:
    """
    Get embeddings for many texts in one batched call (embed_documents),
    instead of one API round-trip per text. Intended for ingestion, where
    all chunks are known upfront; use get_embeddings for single query-time lookups.

    Args:
        texts (list[str]): The input texts to generate embeddings for.
        model_name (str | None): The OpenAI embedding model to use; defaults to settings.embedding_model.

    Returns:
        list[list[float]]: One embedding per input text, same order as texts.
    """
    settings = get_settings()
    embeddings = OpenAIEmbeddings(model=model_name or settings.embedding_model, api_key=settings.llm_api_key)
    return embeddings.embed_documents(texts)


def get_qdrant_client() -> QdrantClient:
    """Build a QdrantClient pointed at the configured VECTOR_STORE_URL.

    Args:
        None

    Returns:
        QdrantClient: client connected to settings.vector_store_url.
    """
    settings = get_settings()
    return QdrantClient(url=settings.vector_store_url, api_key=settings.qdrant_api_key)


def store_embeddings_in_qdrant(
    embeddings: list[float], vector_id: str, content: str, metadata: dict, collection_name: str | None = None
) -> None:
    """
    Store an embedding, its chunk text, and its metadata in Qdrant, upserting
    by vector_id so re-running ingestion updates an existing point's payload/
    vector instead of creating a duplicate. Creates the collection (cosine
    distance) on first use if it doesn't exist yet.

    Args:
        embeddings (list[float]): The embedding vector to store.
        vector_id (str): The point's unique identifier (must be an unsigned int or UUID string).
        content (str): The chunk's text, stored in the payload under "content" so it
            can be returned at retrieval time.
        metadata (dict): Chunk metadata (source, headers, frontmatter, ...) stored
            alongside content in the point's payload.
        collection_name (str | None): Qdrant collection name; defaults to settings.qdrant_collection_name.

    Returns:
        None
    """
    settings = get_settings()
    collection_name = collection_name or settings.qdrant_collection_name
    client = get_qdrant_client()

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=len(embeddings), distance=Distance.COSINE),
        )

    client.upsert(
        collection_name=collection_name,
        points=[PointStruct(id=vector_id, vector=embeddings, payload={"content": content, **metadata})],
    )


def store_embeddings_in_qdrant_batch(
    embeddings: list[list[float]],
    vector_ids: list[str],
    contents: list[str],
    metadatas: list[dict],
    collection_name: str | None = None,
) -> None:
    """
    Store many embeddings, their chunk texts, and their metadata in Qdrant in
    one upsert call, instead of one round-trip per point. Same upsert-by-
    vector_id and create-if-missing (cosine distance) behavior as
    store_embeddings_in_qdrant.

    Args:
        embeddings (list[list[float]]): The embedding vectors to store.
        vector_ids (list[str]): One point ID per embedding, same order.
        contents (list[str]): One chunk text per embedding, same order; stored
            in each point's payload under "content" so it can be returned at
            retrieval time.
        metadatas (list[dict]): One metadata payload per embedding, same order.
        collection_name (str | None): Qdrant collection name; defaults to settings.qdrant_collection_name.

    Returns:
        None
    """
    settings = get_settings()
    collection_name = collection_name or settings.qdrant_collection_name
    client = get_qdrant_client()

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
        )

    client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(id=vector_id, vector=embedding, payload={"content": content, **metadata})
            for vector_id, embedding, content, metadata in zip(
                vector_ids, embeddings, contents, metadatas, strict=True
            )
        ],
    )
