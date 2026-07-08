import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    window_id: str
    page_start: int
    page_end: int
    text: str
    technicality_score: float
    product_names: List[str] = field(default_factory=list)
    technical_entities: List[str] = field(default_factory=list)
    functional_properties: List[str] = field(default_factory=list)
    standards: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    performance_characteristics: List[str] = field(default_factory=list)
    object_names: List[str] = field(default_factory=list)


def load_chunks(json_path: str) -> List[Chunk]:
    """
    Reads the historical_certification_data.json file.
    Returns a clean list of Chunk objects.
    """
    raw = json.loads(Path(json_path).read_text())
    chunks = []

    for item in raw:
        meta = item.get("metadata", {})
        chunk = Chunk(
            chunk_id=item["chunk_id"],
            doc_id=item["doc_id"],
            window_id=item["window_id"],
            page_start=item["page_start"],
            page_end=item["page_end"],
            text=item["text"],
            technicality_score=float(item.get("technicality_score", 0.0)),
            product_names=meta.get("product_name", []),
            technical_entities=meta.get("technical_entities", []),
            functional_properties=meta.get("functional_properties", []),
            standards=meta.get("standards", []),
            constraints=meta.get("constraints", []),
            performance_characteristics=meta.get("performance_characteristics", []),
            object_names=meta.get("object_name", []),
        )
        chunks.append(chunk)

    print(f"✅ Loaded {len(chunks)} chunks from {len(set(c.doc_id for c in chunks))} documents")
    return chunks