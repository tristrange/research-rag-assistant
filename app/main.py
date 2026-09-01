from fastapi import FastAPI
from pydantic import BaseModel

from app.rag import answer_question


app = FastAPI()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    answer = answer_question(request.question)
    return QueryResponse(answer=answer)
