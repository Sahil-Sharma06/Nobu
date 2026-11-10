"""Plain-text extraction from resume files (PDF, DOCX, TXT)."""

import io
from pathlib import Path

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}


class UnsupportedResume(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        text = data.decode("utf-8", errors="replace")
    elif suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix == ".docx":
        import docx

        document = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in document.paragraphs)
    else:
        raise UnsupportedResume(f"unsupported file type {suffix!r}; use PDF, DOCX or TXT")
    text = text.strip()
    if not text:
        raise UnsupportedResume("no text could be extracted (is the PDF a scanned image?)")
    return text
