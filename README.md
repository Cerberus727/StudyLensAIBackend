# StudyLens AI — Backend

> **FastAPI backend powering the StudyLens AI Chrome Extension.**
> Generates structured study notes, video outlines, and AI tutor responses from YouTube lecture transcripts using Google Gemini.

---

## Tech Stack

- **FastAPI** — REST API framework
- **Google Gemini 2.5 Flash** — Note generation & AI tutoring
- **youtube-transcript-api** — YouTube caption fetching
- **ReportLab** — PDF generation
- **Uvicorn** — ASGI server

---

## Project Structure

```
app/
├── main.py                  # FastAPI app entrypoint
├── config.py                # Loads environment variables
├── models/                  # Pydantic request & response schemas
│   ├── note_models.py
│   ├── outline_models.py
│   ├── search_models.py
│   └── tutor_models.py
├── routes/                  # API route handlers
│   ├── notes.py             # POST /generate-notes
│   ├── outline.py           # POST /generate-outline
│   ├── tutor.py             # POST /ask-lecture
│   ├── pdf.py               # POST /export-pdf
│   └── search.py            # POST /search-lecture
└── services/                # Business logic
    ├── llm_service.py       # Gemini prompts & JSON parsing
    ├── transcript_service.py
    ├── pdf_service.py       # Markdown-aware PDF renderer
    ├── tutor_service.py
    └── search_service.py
```

---

## Setup

### 1. Clone & create virtual environment

```bash
git clone https://github.com/Cerberus727/StudyLensAIBackend.git
cd StudyLensAIBackend

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Create `app/.env` from the example:

```bash
cp app/.env.example app/.env
```

Edit `app/.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

> Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey)

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Server runs at **http://localhost:8000**

Verify: [http://localhost:8000](http://localhost:8000) → `{"message": "StudyLens Backend Running"}`

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `GET` | `/` | — | Health check |
| `POST` | `/generate-notes` | `{"youtube_url": "..."}` | Full study pack (notes, concepts, definitions, etc.) |
| `POST` | `/generate-outline` | `{"youtube_url": "..."}` | Timestamped video outline |
| `POST` | `/ask-lecture` | `{"youtube_url": "...", "question": "..."}` | AI tutor Q&A grounded in transcript |
| `POST` | `/export-pdf` | `{"youtube_url": "..."}` | Download formatted study guide as PDF |
| `POST` | `/search-lecture` | `{"youtube_url": "...", "query": "..."}` | Semantic transcript search |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |

---

## License

MIT
