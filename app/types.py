"""Typed dictionary contracts shared across the RAG pipeline."""

from typing import TypedDict


class PageData(TypedDict):
    document: str
    page: int
    text: str


class ChunkData(PageData):
    chunk_index: int


class AnswerResult(TypedDict):
    answer: str
    sources: list[ChunkData]


class RetrievalTestCase(TypedDict):
    question: str
    expected_pages: list[int]
