import fitz  # PyMuPDF
import pdfplumber
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
from app.logger import get_logger

logger = get_logger("pdf_reader")


@dataclass
class PageContent:
    """Raw content extracted from a single PDF page."""
    page_number: int
    text: str
    has_tables: bool
    word_count: int


def read_pdf_with_pymupdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Reads a PDF using PyMuPDF (fitz).
    Fast and good for text-heavy PDFs.
    Returns list of page dicts.
    """
    pages = []
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        # Clean up the text
        text = text.strip()
        text = "\n".join(
            line for line in text.splitlines()
            if line.strip()  # remove blank lines
        )

        pages.append({
            "page_number": page_num + 1,
            "text": text,
            "word_count": len(text.split()),
        })

    doc.close()
    logger.info(f"PyMuPDF read {len(pages)} pages from {Path(pdf_path).name}")
    return pages


def read_pdf_with_pdfplumber(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Reads a PDF using pdfplumber.
    Better for PDFs with tables.
    Returns list of page dicts with table data.
    """
    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []

            # Convert tables to readable text
            table_text = ""
            for table in tables:
                for row in table:
                    clean_row = [
                        str(cell).strip() if cell else ""
                        for cell in row
                    ]
                    table_text += " | ".join(clean_row) + "\n"

            # Combine text and table content
            full_text = text
            if table_text:
                full_text += "\n\nTABLE DATA:\n" + table_text

            full_text = full_text.strip()

            pages.append({
                "page_number": page_num + 1,
                "text": full_text,
                "has_tables": len(tables) > 0,
                "word_count": len(full_text.split()),
            })

    logger.info(f"pdfplumber read {len(pages)} pages from {Path(pdf_path).name}")
    return pages


def read_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Main entry point for reading a PDF.
    Tries PyMuPDF first — falls back to pdfplumber if needed.
    Automatically picks the best result.
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")

    logger.info(f"Reading PDF: {path.name}")

    # Try PyMuPDF first
    try:
        pages_pymupdf = read_pdf_with_pymupdf(pdf_path)
        total_words = sum(p["word_count"] for p in pages_pymupdf)

        # If PyMuPDF extracted reasonable content use it
        if total_words > 100:
            logger.info(f"✅ Using PyMuPDF — {total_words} words extracted")
            return pages_pymupdf

    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e} — trying pdfplumber")

    # Fall back to pdfplumber
    try:
        pages_plumber = read_pdf_with_pdfplumber(pdf_path)
        total_words = sum(p["word_count"] for p in pages_plumber)
        logger.info(f"✅ Using pdfplumber — {total_words} words extracted")
        return pages_plumber

    except Exception as e:
        logger.error(f"Both PDF readers failed for {pdf_path}: {e}")
        raise RuntimeError(f"Could not read PDF: {pdf_path}")


def get_pdf_info(pdf_path: str) -> Dict[str, Any]:
    """
    Returns basic info about a PDF without reading all content.
    Useful for quick checks before processing.
    """
    doc = fitz.open(pdf_path)
    info = {
        "filename": Path(pdf_path).name,
        "page_count": len(doc),
        "metadata": doc.metadata,
        "file_size_kb": round(Path(pdf_path).stat().st_size / 1024, 1),
    }
    doc.close()
    return info