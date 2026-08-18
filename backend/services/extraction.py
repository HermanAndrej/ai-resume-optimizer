import io
from pathlib import Path


def extract_text(file_content: bytes, filename: str) -> str:
    """Extract plain text from a resume file (PDF, DOCX, or TEX/TXT)."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(file_content)
    elif suffix in (".docx", ".doc"):
        return _extract_docx(file_content)
    elif suffix in (".tex", ".txt"):
        return file_content.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use PDF, DOCX, or TEX.")


def _extract_pdf(content: bytes) -> str:
    from pdfminer.high_level import extract_text as pdf_extract

    text = pdf_extract(io.BytesIO(content))
    if not text or len(text.strip()) < 50:
        return _ocr_pdf(content)
    return text


def _extract_docx(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _ocr_pdf(content: bytes) -> str:
    """OCR fallback for image-based PDFs. Requires tesseract and poppler."""
    try:
        import pytesseract
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(content)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as exc:
        raise RuntimeError(
            "PDF appears to be image-based and OCR failed. "
            "Install tesseract and poppler, or use a text-based PDF."
        ) from exc
