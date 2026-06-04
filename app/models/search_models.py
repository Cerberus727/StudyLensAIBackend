from pydantic import BaseModel
from typing import List


class SearchRequest(BaseModel):
    youtube_url: str
    query: str


class SearchResult(BaseModel):
    timestamp: float
    display_time: str
    title: str
    content: str


class SearchResponse(BaseModel):
    results: List[SearchResult]
