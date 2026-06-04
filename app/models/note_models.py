from pydantic import BaseModel
class NoteRequest(BaseModel):
    youtube_url:str
class NoteResponse(BaseModel):
    notes:str

class Definition(BaseModel):
    term: str
    definition: str


class StudyPackResponse(BaseModel):
    overview: str
    key_concepts: list[str]
    definitions: list[Definition]
    detailed_notes: str
    common_mistakes: list[str]
    revision_sheet: list[str]
    key_takeaways: list[str]