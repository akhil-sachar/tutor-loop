from pydantic import BaseModel


class SemanticSearchResult(BaseModel):
    id: str
    collection: str
    content_type: str
    title: str
    subject: str | None = None
    score: float
    snippet: str
    metadata: dict = {}
