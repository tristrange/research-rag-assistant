"""Typed dictionary contracts shared across the RAG pipeline."""

from typing import Literal, NotRequired, TypedDict


class PageData(TypedDict):
    document: str
    page: int
    text: str
    section: NotRequired[str]


class ChunkData(PageData):
    chunk_index: int


class EvidenceQuote(TypedDict):
    source_index: int
    quote: str


class AnswerClaim(TypedDict):
    text: str
    attribution: Literal["this_document_authors", "external_publication", "non_study_context"]
    citations: list[EvidenceQuote]


type AnswerOutcome = Literal["answered", "partial", "insufficient_evidence"]


class AnswerResult(TypedDict):
    answer: str
    sources: list[ChunkData]
    claim_evidence: NotRequired[list[AnswerClaim]]
    outcome: NotRequired[AnswerOutcome]


class RetrievalTestCase(TypedDict):
    question: str
    expected_pages: list[int]
