import logging
import re
from collections.abc import Awaitable, Callable
from ipaddress import ip_address
from pathlib import Path
from threading import Lock
from typing import Literal, Self

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError

from app.embeddings import EMBEDDING_MODEL, OLLAMA_EMBED_URL
from app.llm.ollama import OLLAMA_URL, OllamaOutputLimitError
from app.rag import answer_each_document, answer_question
from app.retrieval.search import list_documents
from app.service_checks import ServiceStatus, service_status


app = FastAPI(docs_url=None, redoc_url=None)
_query_gate = Lock()
_LOCAL_HOST = re.compile(r"(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?", re.IGNORECASE)
UI_DIR = Path(__file__).resolve().parent / "ui"
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")
logger = logging.getLogger(__name__)


def service_error(status: int, code: str, message: str) -> JSONResponse:
    # Do not include exception text, upstream bodies, SQL or connection credentials.
    logger.warning("Service request failed: %s", code)
    return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}})


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
    return service_error(503, "database_error", "The database request failed. Check that PostgreSQL is running, load your .env settings, and run uv run python -m scripts.init_db.")


@app.exception_handler(OllamaOutputLimitError)
async def output_limit_error(request: Request, error: OllamaOutputLimitError) -> JSONResponse:
    return service_error(502, "model_output_limit", "The model exhausted its output budget before completing the answer check. Try a narrower question; if this repeats, review RAG_GROUNDING_OUTPUT_TOKENS.")


@app.exception_handler(httpx.HTTPError)
async def dependency_error(request: Request, error: httpx.HTTPError) -> JSONResponse:
    ollama_request = False
    embedding_request = False
    if isinstance(error, (httpx.RequestError, httpx.HTTPStatusError)):
        try:
            embedding_request = error.request.url == httpx.URL(OLLAMA_EMBED_URL)
            ollama_request = embedding_request or error.request.url == httpx.URL(OLLAMA_URL)
        except RuntimeError:
            pass
    if not ollama_request:
        return service_error(503, "dependency_error", "A required dependency request failed. Check local services and model downloads, then try again.")
    if isinstance(error, httpx.TimeoutException):
        if embedding_request:
            return service_error(504, "model_timeout", "Ollama did not finish embedding the question within the time limit. Check Ollama's activity and available memory, then try again. The grounding timeout setting does not control embeddings.")
        return service_error(504, "model_timeout", "Ollama did not finish within the time limit. Wait for any model activity to finish, then try a narrower question. If this repeats, review RAG_GROUNDING_TIMEOUT_SECONDS.")
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 404:
            if embedding_request:
                return service_error(503, "embedding_model_not_found", f"Ollama could not find the embedding model. Install it with ollama pull {EMBEDDING_MODEL}, then try again.")
            return service_error(503, "model_not_found", "Ollama could not find the configured answer model. Check RAG_GROUNDING_MODEL and install that model with ollama pull.")
        return service_error(502, "model_service_error", "Ollama could not complete the model request. Check Ollama's logs and available memory, then try again.")
    return service_error(503, "model_unavailable", "Could not communicate with Ollama. Open the Ollama app or start ollama serve, then try again.")


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


class EvidenceQuote(BaseModel):
    source_index: int = Field(ge=0)
    quote: str


class AnswerClaimEvidence(BaseModel):
    text: str
    attribution: Literal["this_document_authors", "external_publication", "non_study_context"]
    citations: list[EvidenceQuote]


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    claim_evidence: list[AnswerClaimEvidence] = Field(default_factory=list)


@app.get("/", response_class=FileResponse)
def home() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/docs", response_class=FileResponse, include_in_schema=False)
def api_docs() -> FileResponse:
    return FileResponse(UI_DIR / "api-docs.html")


@app.get("/documents", response_model=list[str])
def documents() -> list[str]:
    return list_documents()


@app.get("/status", response_model=ServiceStatus)
def status() -> ServiceStatus:
    return service_status()


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
            claim_evidence=[AnswerClaimEvidence.model_validate(claim) for claim in result.get("claim_evidence", [])],
        )
    finally:
        _query_gate.release()
