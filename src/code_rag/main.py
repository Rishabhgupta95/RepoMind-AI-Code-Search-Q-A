import logging
import uuid

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .indexer import index_repository
from .llm import answer_from_context
from .repository import repository_key
from .retriever import search_code
from .task_tracker import create_task, get_task, update_task
from fastapi.middleware.cors import CORSMiddleware


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Code RAG",
    description="Index repositories and ask questions grounded in their source code.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*",  # during development, later restrict to frontend origin
    ],
    allow_credentials=False,
    allow_methods=["*"],  # or list: ["GET", "POST", "OPTIONS"]
    allow_headers=["*"],
)


class IndexRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=2048)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    repository: str | None = Field(default=None, max_length=2048)
    limit: int = Field(default=5, ge=1, le=50)


class AskRequest(SearchRequest):
    pass


def run_indexing_task(task_id: str, source: str) -> None:
    """Run repository indexing and update task progress."""

    update_task(
        task_id,
        status="indexing",
        stage="starting",
    )

    try:
        def report_progress(**progress) -> None:
            update_task(task_id, **progress)

        result = index_repository(
            source,
            progress_callback=report_progress,
        )

        update_task(
            task_id,
            **result,
            status="completed",
            stage="completed",
            percent=100,
            error=None,
        )

        logger.info(
            "Indexing completed successfully for task %s",
            task_id,
        )

    except Exception:
        logger.exception(
            "Repository indexing failed for task %s",
            task_id,
        )

        update_task(
            task_id,
            status="failed",
            stage="failed",
            error="Repository indexing failed. Check server logs.",
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/index", status_code=202)
def index(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Schedule repository indexing in the background."""

    task_id = str(uuid.uuid4())

    create_task(task_id)

    background_tasks.add_task(
        run_indexing_task,
        task_id,
        request.repository,
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Repository indexing has been scheduled.",
    }


@app.get("/index/{task_id}")
def index_status(task_id: str) -> dict:
    """Return the status and progress of an indexing task."""

    task = get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Indexing task not found.",
        )

    return task


@app.post("/search")
def search(request: SearchRequest) -> dict:
    repository = (
        repository_key(request.repository)
        if request.repository
        else None
    )

    results = search_code(
        request.query,
        limit=request.limit,
        repository=repository,
    )

    return {
        "query": request.query,
        "results": results,
    }


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    repository = (
        repository_key(request.repository)
        if request.repository
        else None
    )

    sources = search_code(
        request.query,
        limit=request.limit,
        repository=repository,
    )

    try:
        answer = answer_from_context(
            request.query,
            sources,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return {
        "question": request.query,
        "answer": answer,
        "sources": sources,
    }


def main() -> None:
    uvicorn.run(
        "code_rag.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()