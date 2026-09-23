from pathlib import Path
from typing import Literal, Self

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator, model_validator

from app.rag import answer_each_document, answer_question
from app.retrieval.search import list_documents


app = FastAPI()
UI_DIR = Path(__file__).resolve().parent / "ui"
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


class QueryRequest(BaseModel):
    question: str
    answer_mode: Literal["plain", "verified"] = "plain"
    scope: Literal["relevant", "each"] = "relevant"
    document: str | None = None

    @field_validator("document")
    @classmethod
    def valid_document(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "/" in value or "\\" in value):
            raise ValueError("document must be an exact indexed filename")
        return value

    @model_validator(mode="after")
    def valid_scope(self) -> Self:
        if self.scope == "each" and self.document is not None:
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


@app.get("/documents", response_model=list[str])
def documents() -> list[str]:
    return list_documents()


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    if request.scope == "each":
        result = answer_each_document(request.question, answer_mode=request.answer_mode)
    else:
        result = answer_question(
            request.question, answer_mode=request.answer_mode, document=request.document,
        )

    return QueryResponse(
        answer=result["answer"],
        sources=[Source(**source) for source in result["sources"]],
    )
