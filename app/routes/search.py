import logging

from fastapi import APIRouter, HTTPException

from app.models.search_models import SearchRequest, SearchResponse
from app.services.transcript_service import get_transcript_with_timestamps
from app.services.search_service import semantic_search

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/semantic-search",
    response_model=SearchResponse,
    summary="Semantic search over a YouTube lecture transcript",
    description=(
        "Fetches the transcript for the given YouTube URL, chunks it into "
        "semantic sections, and uses Gemini to find the top 5 sections most "
        "relevant to the user's natural-language query."
    ),
)
def search_transcript(request: SearchRequest) -> SearchResponse:
    """
    POST /semantic-search

    Body:
        youtube_url: Full YouTube video URL.
        query: Natural-language question or concept to search for.

    Returns:
        SearchResponse with a list of up to 5 ranked SearchResult objects,
        each containing timestamp, display_time, title, and content.
    """
    logger.info(
        "Semantic search request — URL: %r  Query: %r",
        request.youtube_url,
        request.query,
    )

    try:
        transcript_data = get_transcript_with_timestamps(request.youtube_url)
    except ValueError as exc:
        logger.error("Invalid YouTube URL: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to fetch transcript: %s", exc)
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

    results = semantic_search(transcript_data, request.query)

    return SearchResponse(results=results)
