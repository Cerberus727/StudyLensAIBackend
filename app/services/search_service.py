import json
import logging
import math
from typing import List, Dict, Any

from google import genai

from app.config import GEMINI_API_KEY
from app.models.search_models import SearchResult

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)

# Number of transcript snippets to group into one chunk
_CHUNK_SIZE = 15


def _format_display_time(seconds: float) -> str:
    """Convert raw seconds to MM:SS display format."""
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def _chunk_transcript(
    transcript_data: List[Dict[str, Any]],
    chunk_size: int = _CHUNK_SIZE,
) -> List[Dict[str, Any]]:
    """
    Group transcript snippets into larger semantic chunks.

    Each chunk carries the start timestamp of its first snippet and
    the concatenated text of all snippets in the group.
    """
    chunks = []
    total = len(transcript_data)

    for i in range(0, total, chunk_size):
        group = transcript_data[i : i + chunk_size]
        combined_text = " ".join(item["text"] for item in group)
        start_time = group[0]["start"]
        chunks.append(
            {
                "chunk_index": len(chunks),
                "start": start_time,
                "display_time": _format_display_time(start_time),
                "text": combined_text,
            }
        )

    return chunks


def semantic_search(
    transcript_data: List[Dict[str, Any]],
    query: str,
    top_k: int = 5,
) -> List[SearchResult]:
    """
    Use Gemini as a semantic retrieval engine to find the most relevant
    transcript chunks for the given natural-language query.

    Args:
        transcript_data: List of {text, start} dicts from transcript_service.
        query: The user's natural-language question or concept.
        top_k: Maximum number of results to return.

    Returns:
        List of SearchResult objects sorted by relevance (best first).
    """
    if not transcript_data:
        logger.warning("semantic_search called with empty transcript_data")
        return []

    chunks = _chunk_transcript(transcript_data)

    # Build a compact JSON representation of all chunks to embed in the prompt
    chunks_for_prompt = [
        {
            "chunk_index": c["chunk_index"],
            "start": c["start"],
            "display_time": c["display_time"],
            "text": c["text"],
        }
        for c in chunks
    ]

    prompt = f"""You are an expert semantic search engine for lecture transcripts.

A student asked:
"{query}"

Below is a JSON array of transcript chunks. Each chunk has:
- chunk_index: unique id
- start: timestamp in seconds
- display_time: human-readable timestamp (MM:SS)
- text: the spoken content

Your task:
1. Understand the INTENT and CONCEPT behind the student's query — not just the keywords.
2. Handle synonyms, paraphrasing, and concept-level similarity.
   Example: "speed up database access" → look for caching, indexing, Redis, query optimization, etc.
3. Identify the top {top_k} most relevant chunks.
4. For each match, generate a short descriptive title (5–8 words) for that lecture section.
5. Write a concise 1–2 sentence explanation of WHY this section is relevant to the query.

Return ONLY a valid JSON array. No markdown, no extra text.

Schema for each result object:
{{
  "chunk_index": <integer>,
  "timestamp": <float, seconds>,
  "display_time": "<MM:SS>",
  "title": "<short section title>",
  "content": "<concise relevance explanation>"
}}

Rules:
- Return at most {top_k} results.
- Order results by relevance (most relevant first).
- If fewer than {top_k} chunks are relevant, return only the truly relevant ones.
- Never return irrelevant chunks just to fill the quota.
- Return ONLY valid JSON — no markdown fences, no prose outside the array.

Transcript chunks:
{json.dumps(chunks_for_prompt, ensure_ascii=False)}
"""

    try:
        logger.info(
            "Sending semantic search prompt to Gemini. "
            "Query: %r  |  Chunks: %d",
            query,
            len(chunks),
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        raw = response.text.strip()
        parsed = json.loads(raw)

        if not isinstance(parsed, list):
            logger.error(
                "Gemini returned non-list JSON for semantic search: %s", raw[:200]
            )
            return []

        results: List[SearchResult] = []
        for item in parsed[:top_k]:
            try:
                results.append(
                    SearchResult(
                        timestamp=float(item["timestamp"]),
                        display_time=str(item["display_time"]),
                        title=str(item["title"]),
                        content=str(item["content"]),
                    )
                )
            except (KeyError, ValueError, TypeError) as parse_err:
                logger.warning(
                    "Skipping malformed search result item: %s — %s",
                    item,
                    parse_err,
                )

        logger.info("Semantic search returned %d results.", len(results))
        return results

    except json.JSONDecodeError as json_err:
        logger.error("Failed to parse Gemini JSON response: %s", json_err)
        return []
    except Exception as exc:
        logger.exception("Unexpected error during semantic_search: %s", exc)
        return []
