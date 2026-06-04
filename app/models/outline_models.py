from pydantic import BaseModel
class OutlineRequest(BaseModel):
    youtube_url:str
    