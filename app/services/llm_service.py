from google import genai

from app.config import GEMINI_API_KEY
import json
import re

client = genai.Client(
    api_key=GEMINI_API_KEY
)


def _parse_llm_json(text: str) -> dict:
    """
    Robustly parse JSON from an LLM response.
    Handles: raw JSON, JSON wrapped in ```json fences,
    and responses with trailing garbage (Extra data error).
    """
    text = text.strip()

    # 1. Try a clean parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences and retry
    cleaned = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```\s*$', '', cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. raw_decode: reads exactly ONE JSON object, ignores any trailing content
    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned)
        return obj
    except json.JSONDecodeError:
        pass

    # 4. Find the first '{' and raw_decode from there
    start = cleaned.find('{')
    if start >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            return obj
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse LLM response as JSON. Raw response: {text[:200]}")

def generate_notes(transcript: str):

    prompt = f"""
You are an expert educator creating professional, in-depth study material for students.

Convert this lecture transcript into comprehensive study notes.

Return ONLY valid JSON matching this exact structure — no extra keys, no markdown outside the fields listed below:

{{
  "overview": "2–3 sentence plain-text summary of what this lecture covers and why it matters.",
  "key_concepts": ["Short concept name", "Another concept", "..."],
  "definitions": [
    {{"term": "Term Name", "definition": "Clear, student-friendly plain-text definition."}}
  ],
  "detailed_notes": "## COMPREHENSIVE MARKDOWN NOTES GO HERE — see rules below",
  "common_mistakes": ["Specific mistake students make", "Another common pitfall"],
  "revision_sheet": ["Concise revision point", "Another checkable item"],
  "key_takeaways": ["Key insight worth remembering", "Another important point"]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES FOR detailed_notes (most important field):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Write in MARKDOWN format (headings, lists, code fences, bold, italic)
- Use ## for major sections, ### for subsections
- For EACH major concept explain: what it is, why it matters, how it works, a concrete example, and a common pitfall
- Include code snippets in fenced blocks (```python, ```js, etc.) where relevant
- Use **bold** for key terms; use bullet lists for multiple items
- Target 600–900 words — educational but focused. NEVER exceed 1200 words.
- Write so a student can revise the topic WITHOUT rewatching the video
- Avoid padding — every sentence must add value

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES FOR ALL OTHER FIELDS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- overview: plain text only, 2–3 sentences
- key_concepts: 5–10 single terms or short phrases, no markdown
- definitions: 3–8 items, plain text only
- common_mistakes: 3–6 items, plain text, one mistake per item
- revision_sheet: 5–10 concise checkable points, plain text
- key_takeaways: 3–7 items, plain text, one insight per item

CRITICAL: You MUST complete the entire JSON object. The response must end with }}.
Return ONLY the JSON object. No text before or after it.

Transcript:

{transcript}
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "max_output_tokens": 16384,
            }
        )

        return _parse_llm_json(response.text)

    except Exception as e:

        return {
            "overview": "",
            "key_concepts": [],
            "definitions": [],
            "detailed_notes": "",
            "common_mistakes": [],
            "revision_sheet": [],
            "key_takeaways": [],
            "error": str(e)
        }
def generate_outline(
    transcript_data
):
    transcript_text = ""

    for item in transcript_data:

        transcript_text += (
            f"[{item['start']}] "
            f"{item['text']}\n"
        )

    prompt = f"""
You are generating a lecture outline.

Create 5-15 major sections.

Return ONLY JSON.

Format:

[
 {{
   "timestamp": 0,
   "title": "Introduction"
 }}
]

Transcript:

{transcript_text}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    cleaned = (
        response.text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return json.loads(cleaned)