from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.rag import answer_question


app = FastAPI()


class QueryRequest(BaseModel):
    question: str
    answer_mode: Literal["plain", "verified"] = "plain"


class Source(BaseModel):
    document: str
    page: int
    chunk_index: int
    text: str
    section: str = "unknown"


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    result = answer_question(request.question, answer_mode=request.answer_mode)

    return QueryResponse(
        answer=result["answer"],
        sources=[Source(**source) for source in result["sources"]],
    )
