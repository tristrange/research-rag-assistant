import re
from collections.abc import Awaitable, Callable
from ipaddress import ip_address
from pathlib import Path
from threading import Lock
from typing import Literal, Self

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from app.rag import answer_each_document, answer_question
from app.retrieval.search import list_documents


app = FastAPI(docs_url=None, redoc_url=None)
_query_gate = Lock()
_LOCAL_HOST = re.compile(r"(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?", re.IGNORECASE)
UI_DIR = Path(__file__).resolve().parent / "ui"
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.middleware("http")
async def local_only(
    request: Request, call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Reject accidental network exposure of this unauthenticated local app."""
    try:
        if request.client is None or not ip_address(request.client.host).is_loopback:
            return JSONResponse({"detail": "Local access only"}, status_code=403)
    except ValueError:
        return JSONResponse({"detail": "Local access only"}, status_code=403)
    if not _LOCAL_HOST.fullmatch(request.headers.get("host", "")):
        return JSONResponse({"detail": "Invalid host header"}, status_code=400)
    return await call_next(request)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer_mode: Literal["verified"] = "verified"
    scope: Literal["relevant", "each", "each_query"] = "relevant"
    document: str | None = None

    @field_validator("question")
    @classmethod
    def valid_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must contain non-whitespace text")
        return value.strip()

    @field_validator("document")
    @classmethod
    def valid_document(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "/" in value or "\\" in value):
            raise ValueError("document must be an exact indexed filename")
        return value

    @model_validator(mode="after")
    def valid_scope(self) -> Self:
        if self.scope in ("each", "each_query") and self.document is not None:
            raise ValueError("each-paper scope cannot select one document")
        return self


class Source(BaseModel):
    document: str
    page: int
    chunk_index: int
    text: str
    section: str = "unknown"


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.get("/", response_class=FileResponse)
def home() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/docs", response_class=FileResponse, include_in_schema=False)
def api_docs() -> FileResponse:
    return FileResponse(UI_DIR / "api-docs.html")


@app.get("/documents", response_model=list[str])
def documents() -> list[str]:
    return list_documents()


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    if not _query_gate.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Another query is already running")
    try:
        if request.scope == "each":
            result = answer_each_document(
                request.question, answer_mode=request.answer_mode, overview=True,
            )
        elif request.scope == "each_query":
            result = answer_each_document(
                request.question, answer_mode=request.answer_mode, overview=False,
            )
        else:
            result = answer_question(
                request.question, answer_mode=request.answer_mode, document=request.document,
            )
        return QueryResponse(
            answer=result["answer"],
            sources=[Source(**source) for source in result["sources"]],
        )
    finally:
        _query_gate.release()
