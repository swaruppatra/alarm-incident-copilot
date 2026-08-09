import logging
import re

from rag.retrieval.models import RetrievedChunk

logger = logging.getLogger("rag.retrieval")

# Small and deliberately non-exhaustive -- this is an audit trail, not the
# defense. Known common injection phrasings; extend as new ones show up in logs.
SUSPICIOUS_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)?\s*instructions", re.IGNORECASE),
    re.compile(r"system note", re.IGNORECASE),
    re.compile(r"do not (disclose|mention|reveal)", re.IGNORECASE),
    re.compile(r"disregard (the )?(above|previous)", re.IGNORECASE),
    re.compile(r"new instructions\s*:", re.IGNORECASE),
]


def flag_suspicious_patterns(text: str) -> list[str]:
    """
    Check text for known prompt-injection phrasings, for observability only.

    This never alters or drops content -- wrap_chunk_for_prompt's delimiters
    plus the system-prompt instruction (Phase 4) are the actual defense. This
    just gives an audit trail of which chunks tripped a known pattern, so
    injection attempts show up in logs instead of passing through silently.

    Args:
        text (str): the chunk text to scan.

    Returns:
        list[str]: the matched pattern strings (empty if none matched).
    """
    return [pattern.pattern for pattern in SUSPICIOUS_PATTERNS if pattern.search(text)]


def wrap_chunk_for_prompt(chunk: RetrievedChunk) -> str:
    """
    Wrap a retrieved chunk's content in explicit delimiters for prompt assembly.

    Any literal occurrence of the delimiter token inside the chunk's own
    content is neutralized first, so an adversarial document can't forge a
    fake "<<<END_RETRIEVED_DOCUMENT_DATA>>>" to break out of the data block
    early and have its own trailing text read as being outside it.

    Args:
        chunk (RetrievedChunk): the chunk to wrap.

    Returns:
        str: the chunk framed as untrusted data, delimited on both sides.
    """
    safe_content = chunk.content.replace("<<<", "< < <")
    return (
        f'<<<RETRIEVED_DOCUMENT_DATA source="{chunk.metadata.source}" section="{chunk.metadata.section}">>>\n'
        f"{safe_content}\n"
        f"<<<END_RETRIEVED_DOCUMENT_DATA>>>"
    )
