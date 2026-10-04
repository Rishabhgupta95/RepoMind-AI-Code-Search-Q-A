import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .indexer import index_repository
from .llm import answer_from_context
from .repository import repository_key
from .retriever import search_code


app = FastAPI(
    title="Code RAG",
    description="Index repositories and ask questions grounded in their source code.",
    version="0.1.0",
)


class IndexRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=2048)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    repository: str | None = Field(default=None, max_length=2048)
    limit: int = Field(default=5, ge=1, le=50)


class AskRequest(SearchRequest):
    pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/index")
def index(request: IndexRequest) -> dict:
    try:
        return index_repository(request.repository)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/search")
def search(request: SearchRequest) -> dict:
    repository = (
        repository_key(request.repository) if request.repository else None
    )
    results = search_code(
        request.query,
        limit=request.limit,
        repository=repository,
    )
    return {"query": request.query, "results": results}


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    repository = (
        repository_key(request.repository) if request.repository else None
    )
    sources = search_code(
        request.query,
        limit=request.limit,
        repository=repository,
    )
    try:
        answer = answer_from_context(request.query, sources)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"question": request.query, "answer": answer, "sources": sources}


def main() -> None:
    uvicorn.run("code_rag.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
