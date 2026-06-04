import logging

from fastapi import APIRouter, HTTPException

from app.models.tutor_models import TutorRequest, TutorResponse
from app.services.transcript_service import get_transcript_with_timestamps
from app.services.search_service import semantic_search
from app.services.tutor_service import answer_question

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/ask-lecture",
    response_model=TutorResponse,
    summary="Ask the AI Lecture Tutor a question about a YouTube lecture",
    description=(
        "Fetches the lecture transcript, semantically retrieves the most relevant "
        "sections for the question, then uses Gemini to generate a structured "
        "tutor-style answer that references the lecture and adds educational context."
    ),
)
def ask_lecture(request: TutorRequest) -> TutorResponse:
    """
    POST /ask-lecture

    Body:
        youtube_url: Full YouTube video URL.
        question:    The student's natural-language question.

    Returns:
        TutorResponse with direct_answer, lecture_explanation,
        additional_context, covered_in_lecture flag, and relevant_sections.
    """
    logger.info(
        "Tutor request — URL: %r | question: %r",
        request.youtube_url,
        request.question,
    )

    # ── Step 1: Fetch transcript ──────────────────────────────────────────────
    try:
        transcript_data = get_transcript_with_timestamps(request.youtube_url)
    except ValueError as exc:
        logger.error("Invalid YouTube URL: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Transcript fetch failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not fetch YouTube transcript. "
            "The video may not have captions enabled.",
        )

    if not transcript_data:
        raise HTTPException(
            status_code=404,
            detail="No transcript content found for this video.",
        )

    # ── Step 2: Semantic retrieval (reuse existing search layer) ──────────────
    retrieved_chunks = semantic_search(
        transcript_data,
        request.question,
        top_k=5,
    )

    # ── Step 3: Generate tutor answer from retrieved context ──────────────────
    response = answer_question(
        question=request.question,
        retrieved_chunks=retrieved_chunks,
    )

    return response
