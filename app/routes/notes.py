from fastapi import APIRouter

from app.models.note_models import (
    NoteRequest,
    NoteResponse
)

from app.services.transcript_service import (
    get_transcript
)

from app.services.llm_service import (
    generate_notes
)

router = APIRouter()

@router.post(
    "/generate-notes"
)
def create_notes(
    request: NoteRequest
):

    transcript = get_transcript(
        request.youtube_url
    )

    notes = generate_notes(
        transcript
    )

    return notes
    transcript = get_transcript(
        request.youtube_url
    )

    notes = generate_notes(
        transcript
    )

    return {
        "notes": notes
    }