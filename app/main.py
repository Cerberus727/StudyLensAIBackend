import logging

from fastapi import FastAPI

from app.routes.notes import (
    router as notes_router
)
from app.routes.outline import (
    router as outline_router
)
from app.routes.search import (
    router as search_router
)
from app.routes.pdf import (
    router as pdf_router
)
from app.routes.tutor import (
    router as tutor_router
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)




app = FastAPI(
    title="StudyLens AI"
)

app.include_router(
    outline_router
)
app.include_router(
    notes_router
)
app.include_router(
    search_router
)
app.include_router(
    pdf_router
)
app.include_router(
    tutor_router
)


@app.get("/")
def root():
    return {
        "message":
        "StudyLens Backend Running"
    }