from fastapi import APIRouter

from app.models.outline_models import (
    OutlineRequest
)

from app.services.transcript_service import (
    get_transcript_with_timestamps
)

from app.services.llm_service import (
    generate_outline
)

router = APIRouter()


@router.post(
    "/generate-outline"
)
def create_outline(
    request: OutlineRequest
):

    transcript = (
        get_transcript_with_timestamps(
            request.youtube_url
        )
    )

    outline = generate_outline(
        transcript
    )

    return {
        "outline": outline
    }