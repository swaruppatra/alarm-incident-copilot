from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


def chunk_markdown(doc_content, headers_to_split_on) -> list[Document]:
    """
    Chunk markdown content into smaller pieces based on specified headers.

    Args:
        doc_content (str): The markdown content to chunk (e.g. from load_markdown).
        headers_to_split_on (list): A list of (marker, name) tuples to split on
            (e.g., [("#", "Header 1"), ("##", "Header 2")]).

    Returns:
        list[Document]: One Document per header section, with page_content (the
            section text) and metadata (the Header 1/Header 2 path to that section).
    """
    # Initialize the MarkdownHeaderTextSplitter
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    # Split the content into chunks
    chunks = splitter.split_text(doc_content)

    return chunks

def chunk_text(text, chunk_size=1000, chunk_overlap=200)-> list[str]:
    """
    Chunk a text into smaller pieces based on specified chunk size and overlap.

    Args:
        text (str): The input text to be chunked.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of overlapping characters between chunks.

    Returns:
        list: A list of chunks, where each chunk is a string.
    """
    # Initialize the RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # Split the text into chunks
    chunks = splitter.split_text(text)

    return chunks
