from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SearchRequest(BaseModel):
    """
    Body of a POST /search request.
    Only 'query' is required. Everything else is optional.
    """
    query: str = Field(
        ...,
        description="The user's question in plain English",
        example="fire resistance requirements for K Rend on blockwork"
    )
    top_k: int = Field(
        default=5,
        description="How many results to return",
        ge=1,
        le=20
    )
    min_technicality: float = Field(
        default=0.3,
        description="Minimum technicality score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    doc_ids: Optional[List[str]] = Field(
        default=None,
        description="Filter to specific document IDs only",
        example=["3428ps8i2-K-Rend-K1-Spray"]
    )
    standards_contain: Optional[str] = Field(
        default=None,
        description="Filter to chunks mentioning this standard",
        example="BS EN"
    )

class ChunkResult(BaseModel):
    """A single retrieved chunk with all its metadata."""
    chunk_id: str
    doc_id: str
    text: str
    page_start: int
    page_end: int
    vector_score: float
    technicality_score: float
    fused_score: float
    confidence: str
    source: str
    standards: List[str]
    product_names: List[str]
    constraints: List[str]
    functional_properties: List[str]

class SearchResponse(BaseModel):
    """Full response from POST /search"""
    query: str
    total_raw: int
    count: int
    results: List[ChunkResult]

class HealthResponse(BaseModel):
    """Response from GET /health"""
    status: str
    chunks_indexed: int
    message: str
