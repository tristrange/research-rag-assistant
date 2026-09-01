from fastapi import FastAPI
from pydantic import BaseModel

from app.rag import answer_question


app = FastAPI()


class QueryRequest(BaseModel):
    question: str


class Source(BaseModel):
    document: str
    page: int
    chunk_index: int
    text: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    result = answer_question(request.question)

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
    )
