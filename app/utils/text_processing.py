import re
import unicodedata
from pathlib import Path


def clean_text(raw: str) -> str:
    """Normalise and clean raw OCR text."""
    # Normalise unicode to NFC form
    text = unicodedata.normalize("NFC", raw)
    # Replace common OCR artefacts: form-feed, null bytes
    text = text.replace("\f", "\n").replace("\x00", "")
    # Collapse runs of blank lines into a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.splitlines()]
    # Remove lines that are purely noise (dashes, underscores, etc.)
    lines = [line for line in lines if not re.fullmatch(r"[-_=|*]{3,}", line)]
    return "\n".join(lines).strip()


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks of approximately `chunk_size` characters.

    Tries to split on sentence boundaries (period + whitespace) when possible.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Try to find a sentence boundary within the last 20% of the chunk
        boundary_search_start = start + int(chunk_size * 0.8)
        boundary = _find_sentence_boundary(text, boundary_search_start, end)

        if boundary and boundary > start:
            chunks.append(text[start:boundary].strip())
            start = boundary - overlap
        else:
            # Fall back to hard cut on whitespace
            cut = text.rfind(" ", start, end)
            if cut == -1 or cut <= start:
                cut = end
            chunks.append(text[start:cut].strip())
            start = cut - overlap

        start = max(start, 0)

    return [c for c in chunks if c]


def _find_sentence_boundary(text: str, search_start: int, search_end: int) -> int | None:
    """Return the position just after the last sentence-ending punctuation in the range."""
    segment = text[search_start:search_end]
    matches = list(re.finditer(r"[.!?]\s+", segment))
    if not matches:
        return None
    last = matches[-1]
    return search_start + last.end()


def sanitize_filename(filename: str) -> str:
    """Return a safe filename without path components or special characters."""
    name = Path(filename).name
    name = re.sub(r"[^\w.\-]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name[:200] or "upload"
