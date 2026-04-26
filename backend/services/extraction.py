"""Text extraction from PDF and DOCX resume files."""
import io
from pathlib import Path


def extract_pdf(data: bytes) -> str:
    """Extract text from a PDF file using pdfminer.six."""
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams

    output = io.StringIO()
    extract_text_to_fp(io.BytesIO(data), output, laparams=LAParams())
    return output.getvalue()


def extract_docx(data: bytes) -> str:
    """Extract text from a DOCX file — paragraphs then table cells."""
    import docx

    doc = docx.Document(io.BytesIO(data))
    parts: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            parts.append(text)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if text:
                    parts.append(text)

    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    """Dispatch to the correct extractor based on file extension.

    Raises ValueError for unsupported file types.
    Raises ValueError if the extracted text is under 50 characters
    (likely a scanned/image-only PDF with no selectable text).
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        text = extract_pdf(data)
    elif suffix == ".docx":
        text = extract_docx(data)
    else:
        raise ValueError(
            f"Unsupported file type: {suffix!r}. Only .pdf and .docx are supported."
        )

    if len(text.strip()) < 50:
        raise ValueError(
            "Extracted text is too short — the file may be a scanned or image-only PDF "
            "with no selectable text. Please upload a text-based PDF or DOCX."
        )

    return text
