import json
import logging
from typing import List

from google import genai

from app.config import GEMINI_API_KEY
from app.models.search_models import SearchResult
from app.models.tutor_models import TutorResponse, RelevantSection

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)


def _build_context_block(chunks: List[SearchResult]) -> str:
    """
    Serialise the retrieved SearchResult objects into a readable
    context string to embed inside the Gemini prompt.
    """
    if not chunks:
        return "No relevant lecture sections were found for this question."

    lines = []
    for i, chunk in enumerate(chunks, start=1):
        lines.append(
            f"[Section {i}] "
            f"Timestamp {chunk.display_time} — "
            f"{chunk.title}\n"
            f"{chunk.content}"
        )
    return "\n\n".join(lines)


def answer_question(
    question: str,
    retrieved_chunks: List[SearchResult],
) -> TutorResponse:
    """
    Use Gemini to answer the student's question acting as a lecture tutor.

    Args:
        question:          The student's natural-language question.
        retrieved_chunks:  Top relevant sections from the semantic search layer.

    Returns:
        A TutorResponse with a direct answer, lecture explanation,
        additional context, coverage flag, and relevant section timestamps.
    """
    context_block = _build_context_block(retrieved_chunks)
    has_context = bool(retrieved_chunks)

    # Build the relevant_sections JSON template for Gemini to fill in
    sections_hint = json.dumps(
        [
            {
                "timestamp": c.timestamp,
                "display_time": c.display_time,
                "title": c.title,
            }
            for c in retrieved_chunks
        ],
        ensure_ascii=False,
    )

    prompt = f"""You are an expert AI Lecture Tutor helping a student understand educational content.

The student asked:
"{question}"

---

RETRIEVED LECTURE SECTIONS (from semantic search over the video transcript):

{context_block}

---

INSTRUCTIONS:

You must respond as a knowledgeable, friendly tutor. Follow these rules strictly:

1. DIRECT ANSWER:
   - Answer the student's question clearly and directly.
   - Use your own knowledge freely — do not limit yourself to the lecture.
   - Be concise but thorough.

2. LECTURE EXPLANATION:
   - Explain how the lecture covers this topic based on the retrieved sections above.
   - Quote or paraphrase only from the retrieved sections provided.
   - If the retrieved sections are NOT relevant to the question, set covered_in_lecture to false
     and leave lecture_explanation as an empty string "".
   - NEVER fabricate or invent lecture content that does not appear in the retrieved sections.

3. ADDITIONAL CONTEXT:
   - Provide 2-3 sentences of extra educational context, real-world examples, or related concepts
     that would genuinely help the student understand the topic better.
   - This can come from your general knowledge.

4. COVERAGE FLAG:
   - Set covered_in_lecture to true ONLY if the retrieved sections genuinely address the question.
   - Set it to false if the sections are off-topic or empty.

5. RELEVANT SECTIONS:
   - If covered_in_lecture is true, include the most relevant sections from this list:
     {sections_hint}
   - If covered_in_lecture is false, return an empty array [].
   - Never include a section that is not in the list above.

---

Return ONLY valid JSON. No markdown. No text outside the JSON object.

Schema:
{{
  "direct_answer": "<clear, direct answer to the question>",
  "lecture_explanation": "<how the lecture covers this, or empty string if not covered>",
  "additional_context": "<extra educational context from your knowledge>",
  "covered_in_lecture": <true or false>,
  "relevant_sections": [
    {{
      "timestamp": <float>,
      "display_time": "<MM:SS>",
      "title": "<section title>"
    }}
  ]
}}
"""

    try:
        logger.info(
            "Tutor request — question: %r | retrieved chunks: %d",
            question,
            len(retrieved_chunks),
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        raw = response.text.strip()
        parsed = json.loads(raw)

        # Validate and coerce relevant_sections into RelevantSection objects
        raw_sections = parsed.get("relevant_sections", [])
        sections: List[RelevantSection] = []
        for sec in raw_sections:
            try:
                sections.append(
                    RelevantSection(
                        timestamp=float(sec["timestamp"]),
                        display_time=str(sec["display_time"]),
                        title=str(sec["title"]),
                    )
                )
            except (KeyError, ValueError, TypeError) as sec_err:
                logger.warning("Skipping malformed section: %s — %s", sec, sec_err)

        tutor_response = TutorResponse(
            direct_answer=str(parsed.get("direct_answer", "")),
            lecture_explanation=str(parsed.get("lecture_explanation", "")),
            additional_context=str(parsed.get("additional_context", "")),
            covered_in_lecture=bool(parsed.get("covered_in_lecture", False)),
            relevant_sections=sections,
        )

        logger.info(
            "Tutor answer generated. covered_in_lecture=%s | sections=%d",
            tutor_response.covered_in_lecture,
            len(tutor_response.relevant_sections),
        )
        return tutor_response

    except json.JSONDecodeError as json_err:
        logger.error("Failed to parse Gemini tutor response as JSON: %s", json_err)
        return TutorResponse(
            direct_answer="Sorry, I was unable to generate an answer at this time.",
            lecture_explanation="",
            additional_context="",
            covered_in_lecture=False,
            relevant_sections=[],
        )
    except Exception as exc:
        logger.exception("Unexpected error in tutor_service.answer_question: %s", exc)
        return TutorResponse(
            direct_answer="An unexpected error occurred. Please try again.",
            lecture_explanation="",
            additional_context="",
            covered_in_lecture=False,
            relevant_sections=[],
        )
