from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    tenant_id: str = Field(default="shagara", min_length=1, max_length=80)
    access_levels: list[str] = Field(default_factory=lambda: ["all"])
    use_ollama: bool = False


class Source(BaseModel):
    marker: str
    document: str
    page: int
    section: str
    score: float
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    query_type: Literal["document", "analytical", "chitchat", "unsupported", "multi_hop"] = "document"
    confidence: float = 0
    grounded: bool = True
    abstained: bool = False
    flags: list[str] = Field(default_factory=list)



