"""Deterministic evidence selection, approved-claim assembly and rendering."""

from __future__ import annotations

import re

from app.grounding_models import (
    MAX_QUOTE_CHARS,
    GroundedClaim,
    GroundedDraft,
    VerificationResult,
    VerifierEvidence,
)
from app.ingestion.chunking import _SENTENCE_END, _is_abbreviation_period
from app.types import AnswerClaim, ChunkData, EvidenceQuote


def build_verifier_evidence(
    claims: list[GroundedClaim],
    sources: list[ChunkData],
) -> list[VerifierEvidence]:
    """Give each cited source span one ID and retain its eligible claim indexes."""
    claims_by_source: dict[int, list[int]] = {}
    for claim_index, claim in enumerate(claims, start=1):
        seen_sources: set[int] = set()
        for citation in claim.citations:
            source_id = citation.source_id
            if source_id > len(sources):
                raise ValueError("citation source ID is outside the source catalogue")
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            claims_by_source.setdefault(source_id, []).append(claim_index)
    catalogue: list[VerifierEvidence] = []
    for source_id in sorted(claims_by_source):
        for quote in _evidence_spans(sources[source_id - 1]["text"]):
            catalogue.append(
                {
                    "evidence_id": len(catalogue) + 1,
                    "claim_indexes": claims_by_source[source_id],
                    "source_id": source_id,
                    "quote": quote,
                }
            )
    return catalogue


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_POSSIBLE_SENTENCE_START = re.compile(r"\s+[\"'“‘(]*[A-Z][a-z]")


def _evidence_spans(text: str) -> list[str]:
    """Extract deterministic quote choices after the validator's normalization."""
    normalized = _normalize_whitespace(text)
    if not normalized:
        return []
    spans: list[str] = []
    seen: set[str] = set()
    boundaries: list[int] = []
    possible_boundaries: list[int] = []
    for match in _SENTENCE_END.finditer(normalized):
        if not _is_abbreviation_period(normalized, match):
            boundaries.append(match.end())
            possible_boundaries.append(match.end())
        elif _POSSIBLE_SENTENCE_START.match(normalized, match.end()):
            possible_boundaries.append(match.end())
    # ponytail: title-case continuations are ambiguous; offer both quote choices.
    for ends in (boundaries, possible_boundaries):
        start = 0
        for end in [*ends, len(normalized)]:
            sentence = normalized[start:end].strip()
            start = end
            for offset in range(0, len(sentence), MAX_QUOTE_CHARS):
                span = sentence[offset : offset + MAX_QUOTE_CHARS]
                if span and span not in seen:
                    seen.add(span)
                    spans.append(span)
    return spans


def _join_adjacent_citations(
    citations: list[EvidenceQuote], sources: list[ChunkData]
) -> list[EvidenceQuote]:
    """Join only selected, unambiguous, touching spans; never fill a context gap."""
    joined: list[EvidenceQuote] = []
    for citation in citations:
        if joined and joined[-1]["source_index"] == citation["source_index"]:
            text = _normalize_whitespace(sources[citation["source_index"]]["text"])
            quotes = [joined[-1]["quote"], citation["quote"]]
            positions = [text.find(quote) for quote in quotes]
            if all(
                start >= 0 and text.find(quote, start + 1) == -1
                for quote, start in zip(quotes, positions)
            ):
                (left, start), (right, end_start) = sorted(
                    zip(quotes, positions), key=lambda item: item[1]
                )
                end = end_start + len(right)
                if (
                    start + len(left) <= end_start
                    and not text[start + len(left) : end_start].strip()
                    and end - start <= MAX_QUOTE_CHARS
                ):
                    joined[-1] = {
                        "source_index": citation["source_index"],
                        "quote": text[start:end],
                    }
                    continue
        joined.append(citation)
    return joined


def _record_accepted_evidence(
    draft: GroundedDraft,
    sources: list[ChunkData],
    feedback: list[dict[str, object]],
    claim_evidence: list[AnswerClaim] | None,
) -> None:
    """Expose only the final approved verifier's source-bound evidence selections."""
    if claim_evidence is None:
        return
    verification = VerificationResult.model_validate(feedback[0]["output"])
    catalogue = {
        entry["evidence_id"]: entry
        for entry in build_verifier_evidence(draft.claims, sources)
    }
    verdicts = {verdict.claim_index: verdict for verdict in verification.verdicts}
    for index, claim in enumerate(draft.claims, start=1):
        claim_evidence.append(
            {
                "text": claim.text,
                "attribution": claim.attribution,
                "citations": _join_adjacent_citations(
                    [
                        {
                            "source_index": catalogue[evidence_id]["source_id"] - 1,
                            "quote": catalogue[evidence_id]["quote"],
                        }
                        for evidence_id in verdicts[index].supporting_evidence_ids
                    ],
                    sources,
                ),
            }
        )


def _render_claims(claims: list[AnswerClaim], sources: list[ChunkData]) -> str:
    rendered: list[str] = []
    labels = {
        "this_document_authors": "",
        "external_publication": "Cited literature: ",
        "non_study_context": "Context: ",
    }
    for claim in claims:
        locations: list[str] = []
        for citation in claim["citations"]:
            source = sources[citation["source_index"]]
            location = f"{source['document']}, page {source['page']}"
            if location not in locations:
                locations.append(location)
        rendered.append(
            f"{labels[claim['attribution']]}{claim['text']} ({'; '.join(locations)})"
        )
    return "\n".join(rendered)
