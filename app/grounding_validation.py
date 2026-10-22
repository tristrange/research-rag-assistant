"""Structural, attribution, coverage and identifier validation of model output."""

from __future__ import annotations

import re

from app.grounding_durations import validate_duration_evidence
from app.grounding_evidence import _normalize_whitespace, build_verifier_evidence
from app.grounding_models import (
    _IDENTIFIER_TOKEN,
    GroundedClaim,
    GroundedDraft,
    VerificationResult,
)
from app.types import ChunkData

_INLINE_CITATION = re.compile(
    r"\[|\]|\bpages?\b|\.pdf\b|\bpp?\.\s*\d+\b|\b(?:source|document|doc)\s*(?:#|no\.?|:)?\s*\d+\b",
    re.IGNORECASE,
)
_QUESTION_COPY_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"
_QUESTION_COPY_TRANSLATION = str.maketrans(
    _QUESTION_COPY_DASHES, "-" * len(_QUESTION_COPY_DASHES)
)
_QUESTION_COPY_RULE = (
    "requested_answer.question_excerpt must equal the entire original question after "
    "whitespace normalization and translation of these typographic dashes to ASCII "
    "hyphen-minus: "
    + ", ".join(f"U+{ord(character):04X}" for character in _QUESTION_COPY_DASHES)
    + "; all other characters remain exact"
)


def _normalize_question_copy(text: str) -> str:
    """Ignore whitespace and typographic dash differences in a copied question."""
    return _normalize_whitespace(text.translate(_QUESTION_COPY_TRANSLATION))


def _is_reference_source(source: ChunkData) -> bool:
    section = _normalize_whitespace(source.get("section", "")).casefold()
    return section in {"reference", "references", "bibliography"}


def _validate_draft(draft: GroundedDraft, sources: list[ChunkData]) -> None:
    for claim in draft.claims:
        if not claim.text.strip():
            raise ValueError("claim text is empty")
        if _INLINE_CITATION.search(claim.text):
            raise ValueError("claim text contains an application-owned citation marker")
        for citation in claim.citations:
            if citation.source_id > len(sources):
                raise ValueError("citation source ID is outside the source catalogue")
            source = sources[citation.source_id - 1]
            if not _normalize_whitespace(source["text"]):
                raise ValueError("citation source is empty")
            if claim.attribution == "this_document_authors" and _is_reference_source(
                source
            ):
                raise ValueError("a current-study claim cites a reference entry")


def validate_verification_structure(
    question: str,
    result: VerificationResult,
    claims: list[GroundedClaim],
    sources: list[ChunkData],
) -> None:
    """Validate exact question/evidence bindings without requiring approval.

    Explicit unsupported coverage, rejected claims, and answers_question=false are
    complete negative verdicts and therefore pass this structural validation.
    """
    claim_count = len(claims)
    indexes = [verdict.claim_index for verdict in result.verdicts]
    if len(indexes) != claim_count or set(indexes) != set(range(1, claim_count + 1)):
        raise ValueError("verifier must return one unique verdict for each claim")

    evidence = build_verifier_evidence(claims, sources)
    evidence_by_id = {entry["evidence_id"]: entry for entry in evidence}

    def validate_evidence_ids(
        ids: list[int], *, claim_index: int | None = None
    ) -> None:
        if len(ids) != len(set(ids)):
            raise ValueError("supporting evidence IDs must be unique")
        for evidence_id in ids:
            entry = evidence_by_id.get(evidence_id)
            if entry is None:
                raise ValueError("verifier cited an unknown evidence ID")
            if claim_index is not None and claim_index not in entry["claim_indexes"]:
                raise ValueError(
                    "claim verdict cited evidence from a source it did not cite"
                )

    requested_answer = result.requested_answer
    if _normalize_question_copy(
        requested_answer.question_excerpt
    ) != _normalize_question_copy(question):
        raise ValueError("requested_answer must quote the entire question")
    validate_evidence_ids(requested_answer.supporting_evidence_ids)
    for requirement in result.requirements:
        validate_evidence_ids(requirement.supporting_evidence_ids)

    for verdict in result.verdicts:
        validate_evidence_ids(
            verdict.supporting_evidence_ids,
            claim_index=verdict.claim_index,
        )


def _validate_question_identifiers(
    question: str, evidence_quotes: list[str], *, label: str = "approved evidence"
) -> None:
    """Require explicit alphanumeric question identifiers in displayed evidence.

    This is a necessary lexical condition, not proof of experiment identity.
    Acronyms, aliases and word-only qualifiers still need semantic verification.
    """
    identifiers = {
        match.group().casefold(): match.group()
        for match in _IDENTIFIER_TOKEN.finditer(question)
        if match.group().isascii()
        and match.group()[0].isalpha()
        and match.group().isalnum()
        and any(character.isdigit() for character in match.group())
    }
    observed = {
        match.group().casefold()
        for quote in evidence_quotes
        for match in _IDENTIFIER_TOKEN.finditer(quote)
    }
    missing = [
        label for identifier, label in identifiers.items() if identifier not in observed
    ]
    if missing:
        raise ValueError(
            f"{label} does not contain question identifier(s): {', '.join(missing)}. "
            + (
                "Preserve named question qualifiers in the answer; evidence cannot repair omitted claim wording."
                if label == "answer text"
                else "Select exact scope excerpts as well as result excerpts; question text, claims, metadata and unselected source context cannot supply the missing identifiers."
            )
        )


_STRENGTH_NEGATION = re.compile(r"\b(?:not|never|no|[a-z]+n['’]t)\s+$", re.IGNORECASE)
_STRENGTH_PATTERNS = (
    (
        "absence of effect",
        re.compile(
            r"\b(?:no (?:effects?|changes?)|un[-‐‑]?\s*changed|un[-‐‑]?\s*affected|did not (?:affect|alter|change))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "complete restoration",
        re.compile(
            r"\b(?:(?:fully|completely) (?:rescued?|restored?)|(?:full|complete) (?:rescue|restoration))\b",
            re.IGNORECASE,
        ),
    ),
)


def _validate_effect_strength(claim: str, quotes: list[str]) -> None:
    """Require explicit strength wording; semantic support is still checked separately."""

    def asserted(pattern: re.Pattern[str], text: str) -> bool:
        text = _normalize_whitespace(text)
        return any(
            not _STRENGTH_NEGATION.search(text[: match.start()])
            for match in pattern.finditer(text)
        )

    for label, pattern in _STRENGTH_PATTERNS:
        if asserted(pattern, claim) and not any(asserted(pattern, q) for q in quotes):
            raise ValueError(
                f"approved evidence lacks explicit {label} wording; preserve the source's result strength"
            )


def _validate_verification(
    question: str,
    result: VerificationResult,
    claims: list[GroundedClaim],
    sources: list[ChunkData],
) -> None:
    validate_verification_structure(question, result, claims, sources)
    if result.requested_answer.status != "supported":
        raise ValueError(
            "cited evidence does not establish an answer to the whole question"
        )
    if any(not requirement.supported for requirement in result.requirements):
        raise ValueError("cited evidence does not establish every question requirement")
    if not result.answers_question:
        raise ValueError("verified claims do not answer the question")
    if any(
        not (verdict.supported and verdict.correct_attribution and verdict.relevant)
        for verdict in result.verdicts
    ):
        raise ValueError("verifier rejected at least one claim")
    claim_evidence_ids = {
        evidence_id
        for verdict in result.verdicts
        for evidence_id in verdict.supporting_evidence_ids
    }
    if not set(result.requested_answer.supporting_evidence_ids).issubset(
        claim_evidence_ids
    ):
        raise ValueError(
            "whole-question coverage cites evidence absent from approved claims"
        )
    for requirement in result.requirements:
        if not set(requirement.supporting_evidence_ids).issubset(
            claim_evidence_ids,
        ):
            raise ValueError(
                "question requirement cites evidence absent from approved claims"
            )
    evidence_by_id = {
        entry["evidence_id"]: entry
        for entry in build_verifier_evidence(claims, sources)
    }
    failures: list[str] = []
    try:
        _validate_question_identifiers(
            question, [claim.text for claim in claims], label="answer text"
        )
    except ValueError as error:
        failures.append(str(error))
    try:
        _validate_question_identifiers(
            question,
            [
                evidence_by_id[evidence_id]["quote"]
                for evidence_id in sorted(claim_evidence_ids)
            ],
        )
    except ValueError as error:
        failures.append(str(error))
    for verdict in result.verdicts:
        try:
            _validate_effect_strength(
                claims[verdict.claim_index - 1].text,
                [
                    evidence_by_id[evidence_id]["quote"]
                    for evidence_id in verdict.supporting_evidence_ids
                ],
            )
            validate_duration_evidence(
                claims[verdict.claim_index - 1].text,
                [
                    evidence_by_id[evidence_id]["quote"]
                    for evidence_id in verdict.supporting_evidence_ids
                ],
            )
        except ValueError as error:
            failures.append(f"Claim {verdict.claim_index}: {error}")
    if failures:
        raise ValueError("\n".join(failures))
