from fastapi import FastAPI
from pydantic import BaseModel

from app.llm.ollama import generate


app = FastAPI()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    answer = generate(request.question)
    return QueryResponse(answer=answer)
