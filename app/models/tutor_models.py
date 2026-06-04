from pydantic import BaseModel
from typing import List


class TutorRequest(BaseModel):
    youtube_url: str
    question: str


class RelevantSection(BaseModel):
    timestamp: float
    display_time: str
    title: str


class TutorResponse(BaseModel):
    direct_answer: str
    lecture_explanation: str
    additional_context: str
    covered_in_lecture: bool
    relevant_sections: List[RelevantSection]
