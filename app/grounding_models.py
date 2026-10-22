"""Immutable request/response contracts and evaluation-facing settings.

Extracted from :mod:`app.grounding`; that module re-exports every name here, so
existing imports keep working. Prompt text and validation rules live elsewhere.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.config import SETTINGS

INSUFFICIENT_EVIDENCE = (
    "I do not have enough evidence in the provided sources to answer this question."
)
GROUNDING_CONTRACT_VERSION = "claim-grounding-v44"
# Keep the existing evaluation-facing names, derived from the shared snapshot.
GROUNDING_MODEL = SETTINGS.grounding_model
DRAFT_THINK = SETTINGS.draft_think
VERIFIER_THINK = SETTINGS.verifier_think
GROUNDING_SAMPLING = SETTINGS.grounding_sampling
GROUNDING_OUTPUT_TOKENS = SETTINGS.grounding_output_tokens
GROUNDING_CONTEXT_TOKENS = SETTINGS.grounding_context_tokens
GROUNDING_DRAFT_TIMEOUT_SECONDS = SETTINGS.grounding_draft_timeout_seconds
GROUNDING_VERIFIER_TIMEOUT_SECONDS = SETTINGS.grounding_verifier_timeout_seconds
MAX_CLAIMS = 3
MAX_QUOTE_CHARS = 4000
_IDENTIFIER_TOKEN = re.compile(r"\w+")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ClaimCitation(StrictModel):
    """A source selected by the draft; evidence text is application-owned."""

    source_id: Annotated[StrictInt, Field(ge=1)]


class GroundedClaim(StrictModel):
    """One concise claim whose citation display is owned by the renderer."""

    text: str = Field(min_length=1, max_length=500)
    attribution: Literal[
        "this_document_authors", "external_publication", "non_study_context"
    ] = Field(
        description="Who performed the work: this document authors, a different external publication, or non-study context. Having a source citation does not imply external publication."
    )
    citations: list[ClaimCitation] = Field(min_length=1, max_length=6)


class GroundedDraft(StrictModel):
    answerable: bool = Field(
        description="Whether evidence answers the question, including a supported negative answer. False means insufficient evidence, not that the answer is no."
    )
    claims: list[GroundedClaim] = Field(max_length=MAX_CLAIMS)

    @model_validator(mode="after")
    def answerability_matches_claims(self) -> GroundedDraft:
        if self.answerable and not self.claims:
            raise ValueError("an answerable draft must contain at least one claim")
        if not self.answerable and self.claims:
            raise ValueError("an unanswerable draft must not contain claims")
        return self


class ClaimVerdict(StrictModel):
    claim_index: Annotated[StrictInt, Field(ge=1, le=MAX_CLAIMS)]
    supported: bool
    correct_attribution: bool
    relevant: bool
    reason: str = Field(min_length=1, max_length=300)
    supporting_evidence_ids: list[Annotated[StrictInt, Field(ge=1)]] = Field(
        max_length=12,
        description="The claim's displayed evidence: include every excerpt needed for its facts and requested scope, including separate scope and result excerpts. Evidence listed only under requirements or requested_answer is not displayed for this claim; include the relevant scope IDs here too.",
    )

    @model_validator(mode="after")
    def supported_claim_has_evidence(self) -> ClaimVerdict:
        if self.supported and not self.supporting_evidence_ids:
            raise ValueError("a supported claim verdict must cite exact evidence")
        return self


class QuestionRequirement(StrictModel):
    requirement: str = Field(
        min_length=1,
        max_length=200,
        description="An actual requested finding or qualifier needed to identify the question target; omit unasked dimensions.",
    )
    supported: bool = Field(
        description="Whether cited evidence establishes an answer to this requirement; a supported no or unchanged result can satisfy a yes/no question.",
    )
    reason: str = Field(min_length=1, max_length=300)
    supporting_evidence_ids: list[Annotated[StrictInt, Field(ge=1)]] = Field(
        max_length=12
    )

    @model_validator(mode="after")
    def supported_requirement_has_evidence(self) -> QuestionRequirement:
        if self.supported and not self.supporting_evidence_ids:
            raise ValueError(
                "a supported question requirement must cite exact evidence"
            )
        return self


class RequestedAnswerCoverage(StrictModel):
    status: Literal["supported", "unsupported"]
    question_excerpt: str = Field(
        min_length=1,
        max_length=2000,
        description="The entire original question, copied exactly apart from whitespace.",
    )
    supporting_evidence_ids: list[Annotated[StrictInt, Field(ge=1)]] = Field(
        max_length=12
    )
    reason: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def supported_answer_has_evidence(self) -> RequestedAnswerCoverage:
        if self.status == "supported" and not self.supporting_evidence_ids:
            raise ValueError("a supported requested answer must cite exact evidence")
        return self


class VerificationResult(StrictModel):
    requirements: list[QuestionRequirement] = Field(
        min_length=1,
        max_length=8,
        description="Only requirements of the actual question, not a checklist of every possible study attribute.",
    )
    answers_question: bool
    reason: str = Field(min_length=1, max_length=300)
    verdicts: list[ClaimVerdict] = Field(max_length=MAX_CLAIMS)
    requested_answer: RequestedAnswerCoverage


class ApprovedProof(StrictModel):
    supported: bool
    reason: str = Field(min_length=1, max_length=300)


DRAFT_SCHEMA: dict[str, object] = GroundedDraft.model_json_schema()
VERIFIER_SCHEMA: dict[str, object] = VerificationResult.model_json_schema()
PROOF_SCHEMA: dict[str, object] = ApprovedProof.model_json_schema()


class VerifierEvidence(TypedDict):
    evidence_id: int
    claim_indexes: list[int]
    source_id: int
    quote: str
