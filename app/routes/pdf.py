import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.transcript_service import get_transcript
from app.services.llm_service import generate_notes
from app.services.pdf_service import generate_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


class PDFRequest(BaseModel):
    youtube_url: str


def _safe_filename(url: str) -> str:
    """
    Derive a filesystem-safe base name from the YouTube URL.
    Falls back to a UUID if nothing useful can be extracted.
    """
    # Try to pull the video ID out of the URL
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    video_id = match.group(1) if match else uuid.uuid4().hex[:11]
    return f"studylens_{video_id}.pdf"


@router.post(
    "/export-pdf",
    summary="Export a StudyLens AI study pack as a downloadable PDF",
    description=(
        "Fetches the YouTube transcript, generates structured study notes via "
        "Gemini, renders them into a professional PDF with ReportLab, and "
        "returns the file as a binary download."
    ),
    response_class=FileResponse,
)
def export_pdf(request: PDFRequest) -> FileResponse:
    """
    POST /export-pdf

    Body:
        youtube_url: Full YouTube video URL.

    Returns:
        A PDF file download (application/pdf).
    """
    logger.info("PDF export request — URL: %r", request.youtube_url)

    # Step 1: Fetch transcript
    try:
        transcript = get_transcript(request.youtube_url)
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

    if not transcript or not transcript.strip():
        raise HTTPException(
            status_code=404,
            detail="No transcript content found for this video.",
        )

    # Step 2: Generate structured notes (reuse existing service)
    try:
        notes = generate_notes(transcript)
    except Exception as exc:
        logger.exception("Note generation failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate study notes from transcript.",
        )

    if "error" in notes:
        logger.warning("generate_notes returned error key: %s", notes["error"])

    # Step 3: Render PDF
    filename = _safe_filename(request.youtube_url)
    try:
        pdf_path = generate_pdf(notes, filename)
    except Exception as exc:
        logger.exception("PDF generation failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to render PDF. Please try again.",
        )

    logger.info("Serving PDF: %s", pdf_path)

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
