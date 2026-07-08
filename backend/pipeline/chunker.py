import re
from typing import List, Dict, Any
from app.logger import get_logger

logger = get_logger("chunker")


# ── STRUCTURAL PATTERNS ────────────────────────────────────────────────────
# These regex patterns detect document structure in certification PDFs

HEADING_PATTERNS = [
    r"^\d+\.\s+[A-Z][A-Za-z\s]+$",           # 1. Introduction
    r"^\d+\.\d+\s+[A-Z][A-Za-z\s]+$",         # 1.1 Technical Data
    r"^\d+\.\d+\.\d+\s+[A-Za-z\s]+$",         # 1.1.1 Sub section
    r"^[A-Z][A-Z\s]{4,}$",                     # ALL CAPS HEADING
    r"^(Section|SECTION|Part|PART)\s+\d+",     # Section 1
    r"^(Clause|CLAUSE)\s+\d+",                 # Clause 1
    r"^(Appendix|APPENDIX)\s+[A-Z0-9]+",       # Appendix A
]

SECTION_BREAK_PATTERNS = [
    r"^-{3,}$",           # --- dividers
    r"^={3,}$",           # === dividers
    r"^\*{3,}$",          # *** dividers
    r"^\s*Page\s+\d+",    # Page numbers
]


def is_heading(line: str) -> bool:
    """Returns True if a line looks like a section heading."""
    line = line.strip()
    if not line:
        return False
    for pattern in HEADING_PATTERNS:
        if re.match(pattern, line):
            return True
    return False


def is_section_break(line: str) -> bool:
    """Returns True if a line is a section divider."""
    line = line.strip()
    for pattern in SECTION_BREAK_PATTERNS:
        if re.match(pattern, line):
            return True
    return False


def clean_text(text: str) -> str:
    """
    Cleans extracted PDF text.
    Removes excessive whitespace and page artifacts.
    """
    # Remove page headers/footers patterns
    text = re.sub(r"Page \d+ of \d+", "", text)

    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


def chunk_by_structure(
    pages: List[Dict[str, Any]],
    doc_id: str,
    min_chunk_words: int = 30,
    max_chunk_words: int = 400,
    window_size: int = 2,
) -> List[Dict[str, Any]]:
    """
    Splits PDF pages into structural chunks.

    Strategy:
    1. Join pages into a full document
    2. Split on headings and section breaks
    3. Merge tiny chunks with neighbours
    4. Split chunks that are too large
    5. Add sliding window context (overlap)

    Returns list of chunk dicts ready for extraction.
    """
    logger.info(f"Chunking {len(pages)} pages for doc: {doc_id}")

    # ── STEP 1: JOIN ALL PAGES ─────────────────────────────────────────────
    full_text = ""
    page_boundaries = {}  # track which page each character starts on

    for page in pages:
        page_start_pos = len(full_text)
        page_text = clean_text(page["text"])
        full_text += page_text + "\n\n"
        page_boundaries[page_start_pos] = page["page_number"]

    # ── STEP 2: SPLIT ON STRUCTURE ─────────────────────────────────────────
    lines = full_text.splitlines()
    raw_chunks = []
    current_chunk_lines = []
    current_heading = ""

    for line in lines:
        if is_heading(line) or is_section_break(line):
            # Save current chunk if it has content
            if current_chunk_lines:
                chunk_text = "\n".join(current_chunk_lines).strip()
                if chunk_text:
                    raw_chunks.append({
                        "heading": current_heading,
                        "text": chunk_text,
                    })
            # Start new chunk
            current_heading = line.strip() if is_heading(line) else current_heading
            current_chunk_lines = [line] if is_heading(line) else []
        else:
            current_chunk_lines.append(line)

    # Don't forget the last chunk
    if current_chunk_lines:
        chunk_text = "\n".join(current_chunk_lines).strip()
        if chunk_text:
            raw_chunks.append({
                "heading": current_heading,
                "text": chunk_text,
            })

    # ── STEP 3: MERGE TINY CHUNKS ──────────────────────────────────────────
    merged_chunks = []
    buffer = ""
    buffer_heading = ""

    for chunk in raw_chunks:
        word_count = len(chunk["text"].split())

        if word_count < min_chunk_words:
            # Too small — merge with buffer
            buffer += "\n\n" + chunk["text"]
            if not buffer_heading:
                buffer_heading = chunk["heading"]
        else:
            if buffer:
                merged_chunks.append({
                    "heading": buffer_heading,
                    "text": buffer.strip(),
                })
                buffer = ""
                buffer_heading = ""
            merged_chunks.append(chunk)

    if buffer:
        merged_chunks.append({
            "heading": buffer_heading,
            "text": buffer.strip(),
        })

    # ── STEP 4: SPLIT LARGE CHUNKS ────────────────────────────────────────
    final_chunks = []

    for chunk in merged_chunks:
        words = chunk["text"].split()

        if len(words) <= max_chunk_words:
            final_chunks.append(chunk)
        else:
            # Split into sub-chunks of max_chunk_words
            for i in range(0, len(words), max_chunk_words):
                sub_words = words[i:i + max_chunk_words]
                final_chunks.append({
                    "heading": chunk["heading"],
                    "text": " ".join(sub_words),
                })

    # ── STEP 5: ASSIGN PAGE NUMBERS & IDS ─────────────────────────────────
    result = []
    total_pages = len(pages)

    for idx, chunk in enumerate(final_chunks):
        # Estimate page number based on chunk position
        estimated_page = min(
            max(1, (idx * total_pages) // max(len(final_chunks), 1) + 1),
            total_pages
        )

        chunk_id = f"{doc_id}_chunk_{idx:04d}"
        window_start = max(0, idx - window_size)
        window_end = min(len(final_chunks) - 1, idx + window_size)

        result.append({
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "window_id": f"{doc_id}_w{window_start}-{window_end}",
            "page_start": estimated_page,
            "page_end": min(estimated_page + 1, total_pages),
            "heading": chunk["heading"],
            "text": chunk["text"],
            "word_count": len(chunk["text"].split()),
        })

    logger.info(f"✅ Created {len(result)} structural chunks from {len(pages)} pages")
    return result